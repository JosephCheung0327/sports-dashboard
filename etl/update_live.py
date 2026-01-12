import requests
from datetime import datetime, timedelta
from config import API_URL
from database.db_utils import get_connection

def update_live():
    print("--- Updating Live Season (2025-2026) ---")
    conn = get_connection()
    cur = conn.cursor()
    
    # From start of season to Yesterday
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
                    sql = """
                        INSERT INTO daily_standings 
                        (date, season_id, team_id, games_played, wins, losses, ot_losses, points, goals_for, goals_against)
                        VALUES (%s, 20252026, (SELECT team_id FROM teams WHERE abbrev = %s LIMIT 1), %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (date, team_id) DO UPDATE SET
                            games_played = EXCLUDED.games_played,
                            wins = EXCLUDED.wins,
                            points = EXCLUDED.points;
                    """
                    cur.execute(sql, (
                        date_str, t["teamAbbrev"]["default"],
                        t.get("gamesPlayed", 0), t.get("wins", 0), t.get("losses", 0),
                        t.get("otLosses", 0), t.get("points", 0), 
                        t.get("goalFor", 0), t.get("goalAgainst", 0)
                    ))
            conn.commit()
        except Exception as e:
            print(f"Skipping {date_str}: {e}")
            conn.rollback()
        
        current += timedelta(days=7) # Weekly updates
        
    conn.close()
    print("Live update complete.")

if __name__ == "__main__":
    update_live()
