import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, GridSearchCV, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.metrics import accuracy_score, roc_auc_score
import joblib
import warnings
import sys
import os

# Try importing XGBoost safely
try:
    from xgboost import XGBClassifier
    XGB_AVAILABLE = True
except ImportError as e:
    XGB_AVAILABLE = False
    print(f"⚠️ Warning: XGBoost could not be imported ({e}). Skipping.")
except Exception as e:
    XGB_AVAILABLE = False
    print(f"⚠️ Warning: XGBoost library error ({e}). Skipping.")

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from database.db_utils import get_connection

warnings.filterwarnings('ignore')

def get_training_data():
    conn = get_connection()
    # Fetch new columns l10_points and streak info
    query = """
        SELECT 
            ds.games_played,
            ds.wins,
            ds.points,
            ds.goals_for,
            ds.goals_against,
            ds.l10_points,
            ds.streak_code,
            ds.streak_count,
            so.made_playoffs
        FROM daily_standings ds
        JOIN season_outcomes so ON ds.season_id = so.season_id AND ds.team_id = so.team_id
        WHERE ds.games_played > 10  -- Filter out very early season noise
    """
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()
    return df

def train_and_compare():
    print("--- 1. Fetching Data ---")
    df = get_training_data()
    
    if df.empty:
        print("No training data found. Run 'python -m database.reset_db' then 'python -m etl.update_history'.")
        return

    # Feature Engineering
    df['win_pct'] = df['wins'] / df['games_played']
    df['goal_diff'] = df['goals_for'] - df['goals_against']
    df['points_win_interaction'] = df['points'] * df['win_pct']
    
    # Normalize L10 Points (Max is 20 points in 10 games)
    df['l10_pct'] = df['l10_points'] / 20.0

    # Calculate Numeric Streak
    # W = Positive, L/OT = Negative
    def calculate_streak(row):
        code = row['streak_code']
        count = row['streak_count']
        if code == 'W': return count
        if code in ['L', 'OT']: return -count
        return 0
    
    df['streak_numeric'] = df.apply(calculate_streak, axis=1)

    # Updated Feature List
    features = ['games_played', 'points', 'win_pct', 'goal_diff', 'points_win_interaction', 'l10_pct', 'streak_numeric']
    
    X = df[features].copy()
    X.fillna(0, inplace=True)
    X.replace([np.inf, -np.inf], 0, inplace=True)
    
    y = df['made_playoffs'].astype(int)

    print(f"Data Loaded: {len(df)} records.")

    # Train/Test Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    print("\n--- 2. Tuning & Training Models ---")
    
    # Logistic Regression
    pipe_lr = Pipeline([
        ('scaler', StandardScaler()),
        ('clf', LogisticRegression(C=1.0, penalty='l2', solver='lbfgs', max_iter=1000, random_state=42))
    ])
    
    # Random Forest (Expanded Grid)
    rf = RandomForestClassifier(random_state=42)
    param_grid_rf = {
        'n_estimators': [100, 200, 300],
        'max_depth': [None, 10, 15, 20],
        'min_samples_leaf': [1, 2, 4],
        'min_samples_split': [2, 5]
    }
    grid_rf = GridSearchCV(rf, param_grid_rf, cv=5, scoring='accuracy', n_jobs=-1)
    grid_rf.fit(X_train, y_train)
    best_rf = grid_rf.best_estimator_

    models = {
        "Logistic Regression": pipe_lr,
        "Random Forest (Tuned)": best_rf,
    }
    estimators_list = [('lr', pipe_lr), ('rf', best_rf)]

    # XGBoost (Expanded Grid)
    if XGB_AVAILABLE:
        xgb = XGBClassifier(use_label_encoder=False, eval_metric='logloss', random_state=42)
        param_grid_xgb = {
            'n_estimators': [100, 200, 300],
            'learning_rate': [0.01, 0.05, 0.1],
            'max_depth': [3, 4, 5, 6],
            'subsample': [0.8, 1.0]
        }
        grid_xgb = GridSearchCV(xgb, param_grid_xgb, cv=5, scoring='accuracy', n_jobs=-1)
        grid_xgb.fit(X_train, y_train)
        best_xgb = grid_xgb.best_estimator_
        models["XGBoost (Tuned)"] = best_xgb
        estimators_list.append(('xgb', best_xgb))

    # Ensemble with dynamic weights based on best accuracy
    # We will simply try a balanced weight and a tree-heavy weight
    ensemble_balanced = VotingClassifier(estimators=estimators_list, voting='soft')
    models["Ensemble (Balanced)"] = ensemble_balanced
    
    # If XGB is available, try a version that trusts it more
    if XGB_AVAILABLE:
        weights_xgb = [1, 1, 2] # Favor XGBoost
        ensemble_xgb_heavy = VotingClassifier(estimators=estimators_list, voting='soft', weights=weights_xgb)
        models["Ensemble (XGB-Heavy)"] = ensemble_xgb_heavy


    print(f"\n{'Model':<25} | {'Accuracy':<10} | {'ROC AUC':<10}")
    print("-" * 50)

    best_model_name = None
    best_score = -1

    for name, model in models.items():
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        
        acc = accuracy_score(y_test, y_pred)
        try:
            y_prob = model.predict_proba(X_test)[:, 1]
            roc = roc_auc_score(y_test, y_prob)
        except:
            roc = 0.0

        print(f"{name:<25} | {acc:.4f}     | {roc:.4f}")
        
        if acc > best_score:
            best_score = acc
            best_model_name = name
        elif acc == best_score and "Ensemble" in name:
            best_model_name = name

    print("-" * 50)
    print(f"Winner: {best_model_name} (Accuracy: {best_score:.2%})")

    final_model = models[best_model_name]
    final_model.fit(X, y)
    save_path = os.path.join(parent_dir, 'models', 'playoff_predictor.pkl')
    joblib.dump(final_model, save_path)
    print(f"Saved {best_model_name} to {save_path}")

if __name__ == "__main__":
    train_and_compare()
