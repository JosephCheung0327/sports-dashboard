import requests
import psycopg2

# --- CONFIG ---
DB_CONFIG = {
    "dbname": "nhl_analytics",
    "user": "postgres",
    "password": "nhldb0112"
}

def update_conferences():
    print("--- UPDATING CONFERENCES ---")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Get latest standings (contains conference info)
        url = "https://api-web.nhle.com/v1/standings/now"
        resp = requests.get(url)
        data = resp.json().get("standings", [])
        
        updated_count = 0
        
        for team in data:
            abbrev = team["teamAbbrev"]["default"]
            conf_name = team.get("conferenceName", "Unknown")
            
            # Simple Update
            sql = "UPDATE teams SET conference = %s WHERE abbrev = %s;"
            cursor.execute(sql, (conf_name, abbrev))
            updated_count += 1
            
        conn.commit()
        conn.close()
        print(f"Success! Updated conference info for {updated_count} teams.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    update_conferences()