import sys
import os
import requests
from datetime import datetime, timedelta

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from config import API_URL
from database.db_utils import get_connection

def update_live():
    print("--- Updating Live Season (2025-2026) ---")
    conn = get_connection()
    cur = conn.cursor()
    
    start_date = datetime(2025, 10, 4)
    end_date = datetime.now() - timedelta(days=1)
    current = start_date
    
    while current <= end_date:
        date_str = current.strftime("%Y-%m-%d")
        try:
            resp = requests.get(f"{API_URL}/standings/{date_str}")
            if resp.status_code == 200:
                data = resp.json().get("standings", [])
                for t in data:
                    # New Extract Logic
                    l10 = t.get("l10Pts", 0)
                    streak_info = t.get("streak", {})
                    s_code = streak_info.get("code", "N") if streak_info else "N"
                    s_count = streak_info.get("count", 0) if streak_info else 0

                    sql = """
                        INSERT INTO daily_standings 
                        (date, season_id, team_id, games_played, wins, losses, ot_losses, points, goals_for, goals_against, l10_points, streak_code, streak_count)
                        VALUES (%s, 20252026, (SELECT team_id FROM teams WHERE abbrev = %s LIMIT 1), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (date, team_id) DO UPDATE SET
                            games_played = EXCLUDED.games_played,
                            wins = EXCLUDED.wins,
                            points = EXCLUDED.points,
                            l10_points = EXCLUDED.l10_points,
                            streak_code = EXCLUDED.streak_code,
                            streak_count = EXCLUDED.streak_count;
                    """
                    cur.execute(sql, (
                        date_str, t["teamAbbrev"]["default"],
                        t.get("gamesPlayed", 0), t.get("wins", 0), t.get("losses", 0),
                        t.get("otLosses", 0), t.get("points", 0), 
                        t.get("goalFor", 0), t.get("goalAgainst", 0),
                        l10, s_code, s_count
                    ))
            conn.commit()
        except Exception as e:
            print(f"Skipping {date_str}: {e}")
            conn.rollback()
        
        current += timedelta(days=7)
        
    conn.close()
    print("Live update complete.")

if __name__ == "__main__":
    update_live()
