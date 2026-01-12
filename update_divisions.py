import requests
import psycopg2

DB_CONFIG = {
    "dbname": "nhl_analytics",
    "user": "postgres",
    "password": "nhldb0112"
}

def update_divisions():
    print("--- UPDATING DIVISIONS ---")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 1. Add the column if it doesn't exist
        print("Ensuring 'division' column exists...")
        cursor.execute("""
            ALTER TABLE teams 
            ADD COLUMN IF NOT EXISTS division VARCHAR(50);
        """)
        conn.commit()
        
        # 2. Fetch Data
        url = "https://api-web.nhle.com/v1/standings/now"
        resp = requests.get(url)
        data = resp.json().get("standings", [])
        
        updated_count = 0
        
        for team in data:
            abbrev = team["teamAbbrev"]["default"]
            div_name = team.get("divisionName", "Unknown")
            
            # 3. Update Team
            sql = "UPDATE teams SET division = %s WHERE abbrev = %s;"
            cursor.execute(sql, (div_name, abbrev))
            updated_count += 1
            
        conn.commit()
        conn.close()
        print(f"Success! Updated division info for {updated_count} teams.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    update_divisions()
