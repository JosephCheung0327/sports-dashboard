import pandas as pd
import numpy as np
import psycopg2
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss
import pickle

# --- CONFIG ---
DB_CONFIG = {
    "dbname": "nhl_analytics",
    "user": "postgres",
    "password": "nhldb0112"
}

def get_data():
    """
    Fetch all historical data and join it with the 'Truth' (Labels).
    """
    conn = psycopg2.connect(**DB_CONFIG)
    
    # We join 'daily_standings' (Features) with 'season_outcomes' (Labels)
    # We only want rows where we know the outcome (Completed seasons).
    query = """
    SELECT 
        d.season_id,
        d.team_id,
        d.date,
        d.games_played,
        d.wins,
        d.losses,
        d.ot_losses,
        d.points,
        d.goals_for,
        d.goals_against,
        o.made_playoffs
    FROM daily_standings d
    JOIN season_outcomes o ON d.season_id = o.season_id AND d.team_id = o.team_id
    WHERE d.games_played > 0 -- Ignore preseason/empty rows
    ORDER BY d.date ASC;
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def feature_engineering(df):
    """
    Transform RAW stats (Points) into RATES (Point %).
    This makes the model work for Game 20 and Game 80 equally well.
    """
    # 1. Point Percentage (The most important stat in hockey)
    # Max points possible = Games Played * 2
    df['point_pct'] = df['points'] / (df['games_played'] * 2)

    # 2. Goal Differential per Game
    df['goal_diff_per_game'] = (df['goals_for'] - df['goals_against']) / df['games_played']

    # 3. Regulation Win Percentage (Tie-breaker)
    # (Assuming we fetched RW, but if not, Win% is a good proxy)
    df['win_pct'] = df['wins'] / df['games_played']

    return df

def train_and_evaluate():
    print("Fetching data from Postgres...")
    df = get_data()
    
    print(f"Loaded {len(df)} rows. Generating features...")
    df = feature_engineering(df)
    
    # Define Features (X) and Target (y)
    features = ['point_pct', 'goal_diff_per_game', 'win_pct']
    target = 'made_playoffs'
    
    # --- WALK-FORWARD VALIDATION ---
    # We will simulate the last 3 completed seasons.
    seasons = sorted(df['season_id'].unique())
    validation_seasons = seasons[-3:] # Last 3 years
    
    metrics = []
    
    print(f"\n--- Starting Walk-Forward Validation ---")
    
    for test_season in validation_seasons:
        # Train on ALL history before this season
        train_data = df[df['season_id'] < test_season]
        test_data = df[df['season_id'] == test_season]
        
        if len(train_data) == 0 or len(test_data) == 0:
            continue
            
        X_train = train_data[features]
        y_train = train_data[target].astype(int) # Convert Boolean to 1/0
        
        X_test = test_data[features]
        y_test = test_data[target].astype(int)
        
        # Train Logistic Regression
        model = LogisticRegression()
        model.fit(X_train, y_train)
        
        # Predict Probabilities
        probs = model.predict_proba(X_test)[:, 1] # Probability of class "1" (Playoffs)
        
        # Evaluate
        score = brier_score_loss(y_test, probs) # Lower is better (0.0 is perfect)
        acc = accuracy_score(y_test, probs > 0.5)
        
        print(f"Season {test_season}: Accuracy = {acc:.2%}, Brier Score = {score:.4f}")
        metrics.append(score)

    print(f"\nAverage Brier Score: {np.mean(metrics):.4f} (Lower is better)")
    
    # --- FINAL TRAINING ---
    # Now we train on EVERYTHING to make the final model for the website.
    print("\nTraining final model on full history...")
    final_model = LogisticRegression()
    final_model.fit(df[features], df[target].astype(int))
    
    # Save the model
    with open('playoff_model.pkl', 'wb') as f:
        pickle.dump(final_model, f)
    print("Success! Model saved to 'playoff_model.pkl'")

if __name__ == "__main__":
    train_and_evaluate()
