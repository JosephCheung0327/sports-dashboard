import pandas as pd
import pickle
import psycopg2
import sys

# --- CONFIG (Socket Connection) ---
DB_CONFIG = {
    "dbname": "nhl_analytics",
    "user": "postgres",
    "password": "nhldb0112"
}

def get_latest_stats():
    """
    Fetch the MOST RECENT stats for every team in the current season (20252026).
    """
    conn = psycopg2.connect(**DB_CONFIG)
    
    # We want the max date for the current season
    query = """
    WITH LatestDate AS (
        SELECT max(date) as max_date 
        FROM daily_standings 
        WHERE season_id = 20252026
    )
    SELECT 
        t.name, 
        d.games_played, 
        d.wins, 
        d.points, 
        d.goals_for, 
        d.goals_against
    FROM daily_standings d
    JOIN teams t ON d.team_id = t.team_id
    JOIN LatestDate ld ON d.date = ld.max_date
    WHERE d.season_id = 20252026;
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def feature_engineering(df):
    """
    Apply the EXACT same transformations we used in training.
    """
    df['point_pct'] = df['points'] / (df['games_played'] * 2)
    df['goal_diff_per_game'] = (df['goals_for'] - df['goals_against']) / df['games_played']
    df['win_pct'] = df['wins'] / df['games_played']
    return df

def main():
    print("--- NHL PLAYOFF PREDICTOR (2025-2026) ---")
    
    # 1. Load Model
    try:
        with open('playoff_model.pkl', 'rb') as f:
            model = pickle.load(f)
    except FileNotFoundError:
        print("Error: 'playoff_model.pkl' not found. Run train_model.py first.")
        sys.exit(1)

    # 2. Get Data
    df = get_latest_stats()
    if df.empty:
        print("No data found for the 2025-2026 season!")
        print("Did you run etl_history.py to fetch the latest stats?")
        sys.exit(1)
        
    print(f"Stats loaded for {len(df)} teams.")

    # 3. Prepare Features
    # We must pass the columns in the exact same order as training
    feature_cols = ['point_pct', 'goal_diff_per_game', 'win_pct']
    X = feature_engineering(df.copy())[feature_cols]

    # 4. Predict
    # predict_proba returns [Prob of False, Prob of True] -> we want column 1
    probs = model.predict_proba(X)[:, 1]
    
    # 5. Display Results
    df['Playoff_Prob'] = probs
    df['Playoff_Prob'] = df['Playoff_Prob'].apply(lambda x: f"{x:.1%}")
    
    # Sort by Probability (High to Low)
    results = df[['name', 'games_played', 'points', 'Playoff_Prob']].sort_values(
        by='Playoff_Prob', ascending=False
    ).reset_index(drop=True)

    print("\nCURRENT PLAYOFF PROBABILITIES:")
    print(results.to_string(index=False))

if __name__ == "__main__":
    main()
