import requests
import psycopg2

DB_CONFIG = {
    "dbname": "nhl_analytics",
    "user": "postgres",
    "password": "nhldb0112",
    "host": "localhost",
    "port": "5432"
}

# Only COMPLETED seasons where we know the result
COMPLETED_SEASONS = [
    {"id": 20142015, "end_date": "2015-04-11"},
    {"id": 20152016, "end_date": "2016-04-10"},
    {"id": 20162017, "end_date": "2017-04-09"},
    {"id": 20172018, "end_date": "2018-04-08"},
    {"id": 20182019, "end_date": "2019-04-06"},
    {"id": 20192020, "end_date": "2020-05-26"}, # COVID special date
    {"id": 20202021, "end_date": "2021-05-19"}, # COVID Shortened
    {"id": 20212022, "end_date": "2022-04-29"},
    {"id": 20222023, "end_date": "2023-04-13"},
    {"id": 20232024, "end_date": "2024-04-18"},
    {"id": 20242025, "end_date": "2025-04-17"}  # Last Completed Season
]

def setup_outcomes():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    for season in COMPLETED_SEASONS:
        print(f"Processing outcomes for Season {season['id']}...")
        
        url = f"https://api-web.nhle.com/v1/standings/{season['end_date']}"
        try:
            resp = requests.get(url)
            data = resp.json().get("standings", [])
            
            for team in data:
                abbrev = team["teamAbbrev"]["default"]
                points = team["points"]
                
                # Check for Clinch Indicator (x, y, p, etc.)
                # If the field 'clinchIndicator' exists, they made it.
                clinch_status = team.get("clinchIndicator", None)
                made_playoffs = clinch_status is not None

                sql = """
                    INSERT INTO season_outcomes (season_id, team_id, made_playoffs, points)
                    VALUES (%s, (SELECT team_id FROM teams WHERE abbrev = %s), %s, %s)
                    ON CONFLICT (season_id, team_id) DO NOTHING;
                """
                cursor.execute(sql, (season['id'], abbrev, made_playoffs, points))
                
        except Exception as e:
            print(f"Error fetching season {season['id']}: {e}")

    conn.commit()
    conn.close()
    print("Success! Outcomes (Labels) populated for 2014-2025.")

if __name__ == "__main__":
    setup_outcomes()