import psycopg2

# Use the EXACT same config you have in your other scripts
DB_CONFIG = {
    "dbname": "nhl_analytics",
    "user": "postgres",
    "password": "nhldb0112",
    "host": "localhost",
    "port": "5432"
}

def investigate():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 1. Ask the Database who it is
        cursor.execute("SELECT inet_server_addr(), inet_server_port(), current_database();")
        host, port, db_name = cursor.fetchone()
        
        print(f"--- PYTHON CONNECTION DETAILS ---")
        print(f"Connected to Host: {host}")
        print(f"Connected to Port: {port}")
        print(f"Database Name:     {db_name}")
        
        # 2. Check the Table Count
        cursor.execute("SELECT count(*) FROM season_outcomes;")
        count = cursor.fetchone()[0]
        print(f"-------------------------------")
        print(f"Rows seen by Python: {count}")
        print(f"-------------------------------")
        
        conn.close()
        
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    investigate()