import requests
from config import API_URL
from database.db_utils import get_connection

def seed_teams():
    print("--- Seeding Teams & Metadata ---")
    url = f"{API_URL}/standings/now"
    resp = requests.get(url)
    data = resp.json().get("standings", [])
    
    conn = get_connection()
    cur = conn.cursor()
    
    count = 0
    for team in data:
        abbrev = team["teamAbbrev"]["default"]
        name = team["teamName"]["default"]
        logo = team.get("teamLogo", "")
        conf = team.get("conferenceName", "Unknown")
        div = team.get("divisionName", "Unknown")
        
        sql = """
            INSERT INTO teams (abbrev, name, logo_url, conference, division)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (abbrev) DO UPDATE SET
                logo_url = EXCLUDED.logo_url,
                conference = EXCLUDED.conference,
                division = EXCLUDED.division;
        """
        cur.execute(sql, (abbrev, name, logo, conf, div))
        count += 1
        
    conn.commit()
    conn.close()
    print(f"Success: Seeded {count} teams.")

if __name__ == "__main__":
    seed_teams()
