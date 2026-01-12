import requests
import psycopg2

DB_CONFIG = {
    "dbname": "nhl_analytics",
    "user": "postgres",
    "password": "nhldb0112",
    "host": "localhost",
    "port": "5432"
}

def setup_teams_table():
    url = "https://api.nhle.com/stats/rest/en/team"
    print(f"Fetching teams from {url}...")

    try:
        resp = requests.get(url)
        data = resp.json().get("data", [])

    except Exception as e:
        print(f"Error: {e}")
        return
    
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    print(f"Found {len(data)} teams. Inserting...")

    for team in data:
        t_id = team.get("id")
        t_name = team.get("fullName")
        t_abbrev = team.get("triCode")
        
        # Insert or Skip if exists
        sql = """
            INSERT INTO teams (team_id, name, abbrev, conference)
            VALUES (%s, %s, %s, 'Unknown')
            ON CONFLICT (team_id) DO NOTHING;
        """
        cursor.execute(sql, (t_id, t_name, t_abbrev))

    conn.commit()
    conn.close()
    print("Success! Teams table populated.")

if __name__ == "__main__":
    setup_teams_table()
