import requests
import time
from datetime import datetime, timedelta
from config import API_URL
from database.db_utils import get_connection

# CONFIG
HEADERS = {
    "User-Agent": "SportsDashboard/1.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
}

# Map historical/relocated franchises to current DB codes
TEAM_MAPPINGS = {
    "ARI": "UTA",  # Arizona Coyotes -> Utah Hockey Club
    "PHX": "UTA"   # Phoenix Coyotes -> Utah Hockey Club
}

SEASONS = [
    (2014, datetime(2014, 10, 8), datetime(2015, 4, 11)),
    (2015, datetime(2015, 10, 7), datetime(2016, 4, 10)),
    (2016, datetime(2016, 10, 12), datetime(2017, 4, 9)),
    (2017, datetime(2017, 10, 4), datetime(2018, 4, 8)),
    (2018, datetime(2018, 10, 3), datetime(2019, 4, 6)),
    (2019, datetime(2019, 10, 2), datetime(2020, 3, 11)),
    (2020, datetime(2021, 1, 13), datetime(2021, 5, 8)),
    (2021, datetime(2021, 10, 12), datetime(2022, 4, 29)),
    (2022, datetime(2022, 10, 7), datetime(2023, 4, 13)),
    (2023, datetime(2023, 10, 10), datetime(2024, 4, 18)),
    (2024, datetime(2024, 10, 4), datetime(2025, 4, 17))
]

def update_history():
    conn = get_connection()
    cur = conn.cursor()
    
    # Fetch Daily Standings (Weekly intervals)
    print("--- Fetching Historical Standings ---")
    
    for start_year, start_date, end_date in SEASONS:
        print(f"Processing Season {start_year}...")
        current = start_date
        season_id = int(f"{start_year}{start_year + 1}")
        
        while current <= end_date:
            date_str = current.strftime("%Y-%m-%d")
            time.sleep(0.1) 
            
            try:
                resp = requests.get(f"{API_URL}/standings/{date_str}", headers=HEADERS, timeout=10)
                
                if resp.status_code == 200:
                    data = resp.json().get("standings", [])
                    for t in data:
                        # Extract Team Abbreviation
                        abbrev = t["teamAbbrev"]["default"] if isinstance(t.get("teamAbbrev"), dict) else t.get("teamAbbrev")
                        if abbrev in TEAM_MAPPINGS:
                            abbrev = TEAM_MAPPINGS[abbrev]
                        
                        # Extract New Stats
                        l10 = t.get("l10Pts", 0)
                        streak_info = t.get("streak", {})
                        s_code = streak_info.get("code", "N") if streak_info else "N"
                        s_count = streak_info.get("count", 0) if streak_info else 0

                        sql = """
                            INSERT INTO daily_standings 
                            (date, season_id, team_id, games_played, wins, losses, ot_losses, points, goals_for, goals_against, l10_points, streak_code, streak_count)
                            VALUES (%s, %s, (SELECT team_id FROM teams WHERE abbrev = %s LIMIT 1), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (date, team_id) DO NOTHING;
                        """
                        cur.execute(sql, (
                            date_str, season_id, abbrev,
                            t.get("gamesPlayed", 0), t.get("wins", 0), t.get("losses", 0),
                            t.get("otLosses", 0), t.get("points", 0), 
                            t.get("goalFor", 0), t.get("goalAgainst", 0),
                            l10, s_code, s_count
                        ))
                    conn.commit()
                elif resp.status_code == 429:
                    print(f"  Hit Rate Limit (429) on {date_str}. Sleeping 5s...")
                    time.sleep(5)
                else:
                    # Often happens in off-season or breaks, ignore silent failure
                    pass
                    
            except Exception as e:
                print(f"  Error on {date_str}: {e}")
                conn.rollback()
            
            current += timedelta(days=7) 
            
    # Fetch Outcomes
    print("--- Fetching Season Outcomes ---")
    MAX_RETRIES = 3
    BACKOFF_FACTOR = 2

    for start_year, _, end_date in SEASONS:
        season_id = int(f"{start_year}{start_year + 1}")
        
        # Try end_date, then end_date - 1 day, etc. to find valid data
        valid_resp = None
        for day_offset in range(3):
            check_date = end_date - timedelta(days=day_offset)
            date_str = check_date.strftime("%Y-%m-%d")
            url = f"{API_URL}/standings/{date_str}"
            
            try:
                resp = requests.get(url, headers=HEADERS, timeout=10)
                if resp.status_code == 200:
                    data = resp.json().get("standings", [])
                    if data: # Ensure we actually got standings
                        valid_resp = resp
                        break 
            except:
                pass
            time.sleep(0.5)

        if not valid_resp:
            print(f"  Skipping {season_id}: Could not find final standings data around {end_date.strftime('%Y-%m-%d')}.")
            continue

        try:
            data = valid_resp.json().get("standings", [])
            inserted_count = 0
            
            for t in data:
                ta = t.get("teamAbbrev")
                abbrev = ta.get("default") if isinstance(ta, dict) else (ta or t.get("abbrev"))
                
                if not abbrev: 
                    continue
                if abbrev in TEAM_MAPPINGS: abbrev = TEAM_MAPPINGS[abbrev]

                # Ensure team exists
                cur.execute("SELECT team_id FROM teams WHERE abbrev = %s LIMIT 1", (abbrev,))
                row = cur.fetchone()
                if not row:
                    continue
                team_id = row[0]

                # "clinchIndicator" usually exists for playoff teams (e.g. 'x', 'y', 'p')
                # If it is missing or None, they missed playoffs.
                clinch = t.get("clinchIndicator")
                made_playoffs = clinch is not None and clinch != ""
                points = t.get("points", 0)

                sql = """
                    INSERT INTO season_outcomes (season_id, team_id, made_playoffs, points)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (season_id, team_id) DO UPDATE
                      SET made_playoffs = EXCLUDED.made_playoffs,
                          points = EXCLUDED.points;
                """
                cur.execute(sql, (season_id, team_id, made_playoffs, points))
                inserted_count += 1

            conn.commit()
            print(f"  Saved outcomes for {season_id} ({inserted_count} teams).")
            
        except Exception as e:
            print(f"  Error processing outcomes for {season_id}: {e}")
            conn.rollback()

    conn.close()
    print("History load complete.")

if __name__ == "__main__":
    update_history()
