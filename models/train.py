import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
import joblib
import warnings
from database.db_utils import get_connection

# Suppress the specific pandas/SQLAlchemy warning about DBAPI connection
warnings.filterwarnings('ignore', category=UserWarning, module='pandas')

def train_model():
    print("--- Training Model ---")
    conn = get_connection()
    
    # Fetch historical stats linked to their final outcomes
    # Filter games_played > 0 to avoid immediate division-by-zero issues
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

    if df.empty:
        print("No training data found. Run 'python -m etl.update_history' first.")
        return

    # Feature Engineering
    # Calculate Win Percentage
    # We use numpy to safely handle division; although the SQL filter > 0 helps, this is safer
    df['win_pct'] = df['wins'] / df['games_played']
    
    # Calculate Goal Differential
    df['goal_diff'] = df['goals_for'] - df['goals_against']
    
    # Select features for the model
    features = ['games_played', 'points', 'win_pct', 'goal_diff']
    
    # Create a clean copy of the features
    X = df[features].copy()
    
    # --- CRITICAL FIX: CLEANING DATA ---
    # 1. Fill any NaNs with 0 (e.g. if a stat is missing)
    X.fillna(0, inplace=True)
    
    # 2. Replace Infinite values if any (rare but possible with division)
    X.replace([np.inf, -np.inf], 0, inplace=True)
    
    # Target variable
    y = df['made_playoffs'].astype(int) # Convert boolean to 1/0

    print(f"Training on {len(df)} records...")

    # Initialize and Train
    model = LogisticRegression()
    model.fit(X, y)

    # Save
    joblib.dump(model, 'models/playoff_predictor.pkl')
    print("Model saved to models/playoff_predictor.pkl")

if __name__ == "__main__":
    train_model()
    