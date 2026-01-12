import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, roc_auc_score, classification_report
from xgboost import XGBClassifier
import joblib
import warnings
import sys
import os

# Ensure we can import from database
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from database.db_utils import get_connection

# Suppress warnings
warnings.filterwarnings('ignore')

def get_training_data():
    conn = get_connection()
    # Fetch historical stats linked to outcomes
    query = """
        SELECT 
            ds.games_played,
            ds.wins,
            ds.points,
            ds.goals_for,
            ds.goals_against,
            so.made_playoffs
        FROM daily_standings ds
        JOIN season_outcomes so ON ds.season_id = so.season_id AND ds.team_id = so.team_id
        WHERE ds.games_played > 0
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
        print("No training data found. Run 'python -m etl.update_history' first.")
        return

    # --- Feature Engineering ---
    df['win_pct'] = df['wins'] / df['games_played']
    df['goal_diff'] = df['goals_for'] - df['goals_against']
    
    features = ['games_played', 'points', 'win_pct', 'goal_diff']
    
    X = df[features].copy()
    X.fillna(0, inplace=True)
    X.replace([np.inf, -np.inf], 0, inplace=True)
    
    y = df['made_playoffs'].astype(int)

    print(f"Data Loaded: {len(df)} records.")

    # --- Train/Test Split ---
    # We split 80/20 to evaluate how the models perform on "unseen" data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    # --- Define Models ---
    models = {
        "Logistic Regression": LogisticRegression(random_state=42),
        "Random Forest": RandomForestClassifier(n_estimators=100, random_state=42),
        "XGBoost": XGBClassifier(use_label_encoder=False, eval_metric='logloss', random_state=42)
    }

    print("\n--- 2. Training & Evaluating Models ---")
    results = {}
    best_model_name = None
    best_score = -1

    print(f"{'Model':<25} | {'Accuracy':<10} | {'ROC AUC':<10}")
    print("-" * 50)

    for name, model in models.items():
        # Train on the 80% split
        model.fit(X_train, y_train)
        
        # Test on the 20% split
        y_pred = model.predict(X_test)
        
        # Calculate metrics
        acc = accuracy_score(y_test, y_pred)
        try:
            # Some models might need predict_proba for ROC
            y_prob = model.predict_proba(X_test)[:, 1]
            roc = roc_auc_score(y_test, y_prob)
        except:
            roc = 0.0

        print(f"{name:<25} | {acc:.4f}     | {roc:.4f}")
        
        results[name] = model

        # Logic to pick the winner
        if acc > best_score:
            best_score = acc
            best_model_name = name

    print("-" * 50)
    print(f"🏆 Winner: {best_model_name} (Accuracy: {best_score:.2%})")

    # --- Save Best Model ---
    print(f"\n--- 3. Retraining Best Model on Full Data ---")
    final_model = models[best_model_name]
    
    # We retrain on the FULL dataset (X, y) so the model learns from every bit of history available
    final_model.fit(X, y)
    
    save_path = os.path.join(parent_dir, 'models', 'playoff_predictor.pkl')
    joblib.dump(final_model, save_path)
    print(f"Saved {best_model_name} to {save_path}")

if __name__ == "__main__":
    train_and_compare()
