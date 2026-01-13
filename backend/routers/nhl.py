from fastapi import APIRouter, HTTPException
import pandas as pd
import joblib
import os
import sys
import numpy as np
from database.db_utils import get_connection

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.append(project_root)

router = APIRouter()
_model = None

def get_model():
    """Singleton pattern to load model only once."""
    global _model
    if _model is None:
        model_path = os.path.join(project_root, 'models', 'playoff_predictor.pkl')
        try:
            _model = joblib.load(model_path)
            print(f"Model loaded from {model_path}")
        except FileNotFoundError:
            print(f"Error: Model not found at {model_path}")
            return None
    return _model

@router.get("/standings")
def get_nhl_standings():
    """
    Fetches current standings, calculates stats (including advanced leading indicators),
    and applies the ML model to predict playoff chances.
    """
    conn = get_connection()
    try:
        # Fetch Data (Latest available date for current season)
        query = """
        WITH LatestDate AS (
            SELECT max(date) as max_date 
            FROM daily_standings 
            WHERE season_id = 20252026
        )
        SELECT
            t.name,
            t.abbrev,
            t.conference,
            t.division,
            t.logo_url,
            ds.games_played,
            ds.wins,
            ds.losses,
            ds.ot_losses,
            ds.points,
            ds.goals_for,
            ds.goals_against,
            ds.l10_points,
            ds.streak_code,
            ds.streak_count
        FROM daily_standings ds
        JOIN teams t ON ds.team_id = t.team_id
        JOIN LatestDate ld ON ds.date = ld.max_date
        WHERE ds.season_id = 20252026;
        """
        df = pd.read_sql(query, conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        conn.close()

    if df.empty:
        return []

    # Feature Engineering
    df['goal_diff'] = df['goals_for'] - df['goals_against']
    # Avoid division by zero
    df['win_pct'] = df.apply(lambda x: x['wins'] / x['games_played'] if x['games_played'] > 0 else 0, axis=1)
    
    # Interaction Term
    df['points_win_interaction'] = df['points'] * df['win_pct']

    # Normalize L10 Points (Max is 20 points in 10 games)
    df['l10_pct'] = df['l10_points'] / 20.0

    # Calculate Numeric Streak
    def calculate_streak(row):
        code = row.get('streak_code', 'N')
        count = row.get('streak_count', 0)
        if code == 'W': return count
        if code in ['L', 'OT']: return -count
        return 0
    
    df['streak_numeric'] = df.apply(calculate_streak, axis=1)

    # Prepare Feature Matrix for Prediction
    # Match order of these columns in models/train.py
    features = ['games_played', 'points', 'win_pct', 'goal_diff', 'points_win_interaction', 'l10_pct', 'streak_numeric']
    
    # Handle NaNs
    df[features] = df[features].fillna(0)

    # Predict
    model = get_model()
    if model:
        try:
            X = df[features]
            if hasattr(model, "predict_proba"):
                # predict_proba returns [prob_class_0, prob_class_1]
                # We want prob_class_1 (Probability of making playoffs)
                probs = model.predict_proba(X)[:, 1]
            else:
                probs = model.predict(X).astype(float)
            
            df['playoff_prob'] = np.clip(probs, 0.0, 1.0)
        except Exception as e:
            print(f"Prediction error: {e}")
            df['playoff_prob'] = 0.0
    else:
        df['playoff_prob'] = 0.0 # Default if model fails

    # Format for Frontend (Return all original cols + prediction)
    result = df.to_dict(orient="records")
    return result
