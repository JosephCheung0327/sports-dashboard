import psycopg2
from config import DB_CONFIG

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def execute_sql_file(filename):
    """Reads and executes a .sql file (like schema.sql)"""
    conn = get_connection()
    try:
        cur = conn.cursor()
        with open(filename, 'r') as f:
            cur.execute(f.read())
        conn.commit()
        print(f"Success: Executed {filename}")
    except Exception as e:
        conn.rollback()
        print(f"Error executing {filename}: {e}")
    finally:
        conn.close()
