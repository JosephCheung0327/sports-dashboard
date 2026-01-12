import requests
import psycopg2

DB_CONFIG = {
    "dbname": "nhl_analytics",
    "user": "postgres",
    "password": "nhldb0112"
}

# End dates of regular seasons (The "Truth" Check)
COMPLETED_SEASONS = [
    {"id": 20142015, "end_date": "2015-04-11"},
    {"id": 20152016, "end_date": "2016-04-10"},
    {"id": 20162017, "end_date": "2017-04-09"},
    {"id": 20172018, "end_date": "2018-04-08"},
    {"id": 20182019, "end_date": "2019-04-06"},
    {"id": 20192020, "end_date": "2020-05-26"},
    {"id": 20202021, "end_date": "2021-05-19"},
    {"id": 20212022, "end_date": "2022-04-29"},
    {"id": 20222023, "end_date": "2023-04-13"},
    {"id": 20232024, "end_date": "2024-04-18"},
    {"id": 20242025, "end_date": "2025-04-17"}
]

def setup_outcomes():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    total_inserted = 0

    for season in COMPLETED_SEASONS:
        print(f"Processing outcomes for Season {season['id']}...")
        
        url = f"https://api-web.nhle.com/v1/standings/{season['end_date']}"
        try:
            resp = requests.get(url)
            # If the date is wrong/API fails, skip to next season instead of crashing
            if resp.status_code != 200:
                print(f"  Warning: API returned {resp.status_code} for {season['id']}")
                continue
                
            data = resp.json().get("standings", [])
            
            for team in data:
                # TRY/EXCEPT INSIDE THE LOOP
                # This ensures that if one team fails, others still get processed.
                try:
                    # normalize abbrev (API sometimes nests it)
                    abbrev = None
                    ta = team.get("teamAbbrev")
                    if isinstance(ta, dict):
                        abbrev = ta.get("default")
                    else:
                        abbrev = ta or team.get("teamAbbrevDisplay") or team.get("teamTricode") or team.get("abbrev")

                    if not abbrev:
                        print(f"  Warning: could not determine abbrev for team entry: {team}")
                        continue

                    points = team.get("points", 0)

                    # find team_id first to avoid inserting NULL or failing silently
                    cursor.execute("SELECT team_id FROM teams WHERE abbrev = %s", (abbrev,))
                    row = cursor.fetchone()
                    if not row:
                        print(f"  Warning: team abbrev '{abbrev}' not found in teams table for season {season['id']}")
                        continue
                    team_id = row[0]

                    # Logic: 'clinchIndicator' exists = Playoffs (x, y, p)
                    clinch_status = team.get("clinchIndicator", None)
                    made_playoffs = clinch_status is not None

                    sql = """
                        INSERT INTO season_outcomes (season_id, team_id, made_playoffs, points)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (season_id, team_id) DO NOTHING;
                    """
                    cursor.execute(sql, (season['id'], team_id, made_playoffs, points))

                    # Only count successful inserts
                    if cursor.rowcount and cursor.rowcount > 0:
                        total_inserted += 1

                except Exception as inner_e:
                    # surface the error so you can fix missing data / schema issues
                    print(f"  Failed to insert {abbrev if 'abbrev' in locals() else 'unknown'}: {inner_e}")
                    continue

        except Exception as e:
            print(f"Critical error fetching season {season['id']}: {e}")

    conn.commit()
    conn.close()
    print(f"Success! Inserted {total_inserted} outcome labels.")

if __name__ == "__main__":
    setup_outcomes()