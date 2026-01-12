from database.db_utils import execute_sql_file

if __name__ == "__main__":
    print("--- RESETTING DATABASE ---")
    print("Warning: This deletes all existing data.")
    execute_sql_file("database/schema.sql")
