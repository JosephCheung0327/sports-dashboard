import requests
import time
from datetime import datetime, timedelta
from config import API_URL
from database.db_utils import get_connection

# --- CONFIG ---
# Valid User-Agent is crucial to avoid 403/429s
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
    # 2019: Changed end date to March 11 (last day of play) to avoid empty API response on Mar 12
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
    
    # 1. Fetch Daily Standings (Weekly intervals)
    print("--- Fetching Historical Standings ---")
    
    for start_year, start_date, end_date in SEASONS:
        print(f"Processing Season {start_year}...")
        current = start_date
        season_id = int(f"{start_year}{start_year + 1}")
        
        while current <= end_date:
            date_str = current.strftime("%Y-%m-%d")
            
            # --- CRITICAL: Respect Rate Limits ---
            time.sleep(0.2)  # Sleep 0.2s between requests to avoid 429s
            
            try:
                resp = requests.get(f"{API_URL}/standings/{date_str}", headers=HEADERS, timeout=10)
                
                if resp.status_code == 200:
                    data = resp.json().get("standings", [])
                    for t in data:
                        # Safe Insert with Subquery for ID
                        # Note: We use t["teamAbbrev"]["default"] because historical standings usually nest it.
                        abbrev = t["teamAbbrev"]["default"] if isinstance(t.get("teamAbbrev"), dict) else t.get("teamAbbrev")
                        
                        # Apply mapping for relocated teams
                        if abbrev in TEAM_MAPPINGS:
                            abbrev = TEAM_MAPPINGS[abbrev]
                        
                        sql = """
                            INSERT INTO daily_standings 
                            (date, season_id, team_id, games_played, wins, losses, ot_losses, points, goals_for, goals_against)
                            VALUES (%s, %s, (SELECT team_id FROM teams WHERE abbrev = %s LIMIT 1), %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (date, team_id) DO NOTHING;
                        """
                        cur.execute(sql, (
                            date_str, season_id, abbrev,
                            t.get("gamesPlayed", 0), t.get("wins", 0), t.get("losses", 0),
                            t.get("otLosses", 0), t.get("points", 0), 
                            t.get("goalFor", 0), t.get("goalAgainst", 0)
                        ))
                    conn.commit()
                elif resp.status_code == 429:
                    print(f"  Hit Rate Limit (429) on {date_str}. Sleeping 10s...")
                    time.sleep(10)
                else:
                    print(f"  Failed {date_str}: Status {resp.status_code}")
                    
            except Exception as e:
                print(f"  Error on {date_str}: {e}")
                conn.rollback()
            
            current += timedelta(days=7) # Jump 7 days
            
    # 2. Fetch Outcomes (End of Season Labels)
    print("--- Fetching Season Outcomes ---")
    MAX_RETRIES = 5
    BACKOFF_FACTOR = 2

    for start_year, _, end_date in SEASONS:
        season_id = int(f"{start_year}{start_year + 1}")
        date_str = end_date.strftime("%Y-%m-%d")
        url = f"{API_URL}/standings/{date_str}"

        resp = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Add HEADERS here too
                resp = requests.get(url, headers=HEADERS, timeout=10)
            except Exception as e:
                print(f"  Warning: request error for {season_id} {date_str}: {e}")
                resp = None

            if resp and resp.status_code == 200:
                break

            if resp and resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                try:
                    wait = int(retry_after) if retry_after else BACKOFF_FACTOR ** attempt
                except (ValueError, TypeError):
                    wait = BACKOFF_FACTOR ** attempt
                
                # Cap wait time to 60s max
                wait = min(wait, 60)
                
                print(f"  Rate limited (429) for {season_id}. Sleeping {wait}s (attempt {attempt})")
                time.sleep(wait)
                continue

            if resp is None:
                wait = BACKOFF_FACTOR ** attempt
                time.sleep(wait)
                continue

            # Non-retryable error
            print(f"  Warning: API returned {resp.status_code} for {season_id}")
            resp = None
            break

        if not resp or resp.status_code != 200:
            print(f"  Skipping {season_id} due to API failure.")
            continue

        try:
            data = resp.json().get("standings", [])
            inserted_count = 0
            
            for t in data:
                # Normalize abbrev
                abbrev = None
                ta = t.get("teamAbbrev")
                if isinstance(ta, dict):
                    abbrev = ta.get("default")
                else:
                    abbrev = ta or t.get("teamAbbrevDisplay") or t.get("teamTricode") or t.get("abbrev")

                if not abbrev:
                    continue

                # Apply mapping for relocated teams
                if abbrev in TEAM_MAPPINGS:
                    abbrev = TEAM_MAPPINGS[abbrev]

                # Find team_id
                cur.execute("SELECT team_id FROM teams WHERE abbrev = %s LIMIT 1", (abbrev,))
                row = cur.fetchone()
                if not row:
                    print(f"  Warning: Team '{abbrev}' not found in DB for {season_id}")
                    continue
                team_id = row[0]

                # Determine playoffs
                # 'clinchIndicator' is usually present if they made it (e.g. 'x', 'y', 'p')
                made_playoffs = t.get("clinchIndicator") is not None
                points = t.get("points", 0)

                sql = """
                    INSERT INTO season_outcomes (season_id, team_id, made_playoffs, points)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (season_id, team_id) DO UPDATE
                      SET made_playoffs = EXCLUDED.made_playoffs,
                          points = EXCLUDED.points
                    RETURNING 1;
                """
                cur.execute(sql, (season_id, team_id, made_playoffs, points))
                if cur.fetchone():
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
