import requests
import psycopg2
from datetime import datetime, timedelta

# --- CONFIG ---
DB_CONFIG = {
    "dbname": "nhl_analytics",
    "user": "postgres",
    "password": "nhldb0112"
}

# --- SEASON DEFINITIONS ---
# Format: (Start Year, Start Date, End Date)
# Note: We stop scraping at the end of the Regular Season.
SEASONS_TO_FETCH = [
    (2014, datetime(2014, 10, 8),  datetime(2015, 4, 11)),
    (2015, datetime(2015, 10, 7),  datetime(2016, 4, 10)),
    (2016, datetime(2016, 10, 12), datetime(2017, 4, 9)),
    (2017, datetime(2017, 10, 4),  datetime(2018, 4, 8)),
    (2018, datetime(2018, 10, 3),  datetime(2019, 4, 6)),
    (2019, datetime(2019, 10, 2),  datetime(2020, 3, 12)), # COVID Shortened
    (2020, datetime(2021, 1, 13),  datetime(2021, 5, 8)),  # Shortened 56 games
    (2021, datetime(2021, 10, 12), datetime(2022, 4, 29)),
    (2022, datetime(2022, 10, 7),  datetime(2023, 4, 13)),
    (2023, datetime(2023, 10, 10), datetime(2024, 4, 18)),
    (2024, datetime(2024, 10, 4),  datetime(2025, 4, 17)),
    # CURRENT SEASON (2025-2026) - Up to Yesterday
    (2025, datetime(2025, 10, 4),  datetime.now() - timedelta(days=1)) 
]

def fetch_and_store_data():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    total_inserted = 0

    for year_start, start_date, end_date in SEASONS_TO_FETCH:
        season_id = int(f"{year_start}{year_start + 1}")
        print(f"--- Processing Season {season_id} ---")
        
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            
            # Hit the API
            url = f"https://api-web.nhle.com/v1/standings/{date_str}"
            try:
                resp = requests.get(url)
                if resp.status_code == 200:
                    data = resp.json().get("standings", [])
                    
                    for team in data:
                        abbrev = team["teamAbbrev"]["default"]
                        
                        # Safe extraction of stats
                        # Note: Some fields might be missing in very old data, using .get() for safety
                        gp = team.get("gamesPlayed", 0)
                        wins = team.get("wins", 0)
                        losses = team.get("losses", 0)
                        otl = team.get("otLosses", 0)
                        pts = team.get("points", 0)
                        rw = team.get("regulationWins", 0)
                        gf = team.get("goalFor", 0)
                        ga = team.get("goalAgainst", 0)
                        
                        sql = """
                            INSERT INTO daily_standings 
                            (date, season_id, team_id, games_played, wins, losses, ot_losses, points, regulation_wins, goals_for, goals_against)
                            VALUES (%s, %s, (SELECT team_id FROM teams WHERE abbrev = %s), %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (date, team_id) DO NOTHING;
                        """
                        cursor.execute(sql, (date_str, season_id, abbrev, gp, wins, losses, otl, pts, rw, gf, ga))
                        total_inserted += 1
                        
            except Exception as e:
                print(f"Error on {date_str}: {e}")

            # Jump 7 days
            current_date += timedelta(days=7)
            
    conn.commit()
    conn.close()
    print(f"Done! Inserted approx {total_inserted} rows of historical data.")

if __name__ == "__main__":
    fetch_and_store_data()
