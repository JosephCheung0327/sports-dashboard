import requests
import psycopg2

DB_CONFIG = {
    "dbname": "nhl_analytics",
    "user": "postgres",
    "password": "yourpassword" # <--- UPDATE THIS
}

def update_logos():
    print("--- UPDATING TEAM LOGOS ---")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 1. Add column if not exists
        print("Ensuring 'logo_url' column exists...")
        cursor.execute("""
            ALTER TABLE teams 
            ADD COLUMN IF NOT EXISTS logo_url TEXT;
        """)
        conn.commit()
        
        # 2. Fetch Data
        url = "https://api-web.nhle.com/v1/standings/now"
        resp = requests.get(url)
        data = resp.json().get("standings", [])
        
        updated_count = 0
        
        for team in data:
            abbrev = team["teamAbbrev"]["default"]
            logo = team.get("teamLogo", "")
            
            # 3. Update Team
            sql = "UPDATE teams SET logo_url = %s WHERE abbrev = %s;"
            cursor.execute(sql, (logo, abbrev))
            updated_count += 1
            
        conn.commit()
        conn.close()
        print(f"Success! Updated logos for {updated_count} teams.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    update_logos()
