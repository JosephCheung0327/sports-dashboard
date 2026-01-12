import requests
import psycopg2
from datetime import datetime, timedelta

# --- CONFIG ---
DB_CONFIG = {
    "dbname": "nhl_analytics",
    "user": "postgres",
    "password": "yourpassword" # <--- UPDATE THIS
}

def update_2025():
    print("--- FETCHING LIVE SEASON (2025-2026) ---")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        start_date = datetime(2025, 10, 4)
        end_date = datetime.now() - timedelta(days=1)
        
        current_date = start_date
        total_inserted = 0
        
        print(f"Scraping from {start_date.date()} to {end_date.date()}...")

        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            url = f"https://api-web.nhle.com/v1/standings/{date_str}"
            
            try:
                resp = requests.get(url)
                if resp.status_code == 200:
                    data = resp.json().get("standings", [])
                    
                    for team in data:
                        abbrev = team["teamAbbrev"]["default"]
                        # Stats
                        gp = team.get("gamesPlayed", 0)
                        wins = team.get("wins", 0)
                        losses = team.get("losses", 0)
                        otl = team.get("otLosses", 0)
                        pts = team.get("points", 0)
                        rw = team.get("regulationWins", 0)
                        gf = team.get("goalFor", 0)
                        ga = team.get("goalAgainst", 0)
                        
                        # --- THE FIX IS HERE ---
                        # 1. Added 'LIMIT 1' to the subquery to handle duplicate team entries safely.
                        sql = """
                            INSERT INTO daily_standings 
                            (date, season_id, team_id, games_played, wins, losses, ot_losses, points, regulation_wins, goals_for, goals_against)
                            VALUES (%s, 20252026, (SELECT team_id FROM teams WHERE abbrev = %s LIMIT 1), %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (date, team_id) DO UPDATE SET
                                games_played = EXCLUDED.games_played,
                                wins = EXCLUDED.wins,
                                points = EXCLUDED.points;
                        """
                        cursor.execute(sql, (date_str, abbrev, gp, wins, losses, otl, pts, rw, gf, ga))
                        total_inserted += 1
                    
                    # Commit weekly to save progress
                    conn.commit()
                        
            except Exception as e:
                # 2. Added ROLLBACK to reset the connection if a week fails
                conn.rollback()
                print(f"Skipping {date_str}: {e}")

            current_date += timedelta(days=7)

        conn.close()
        print(f"Success! Inserted {total_inserted} rows for the 2025-2026 season.")

    except Exception as e:
        print(f"Connection Failed: {e}")

if __name__ == "__main__":
    update_2025()
