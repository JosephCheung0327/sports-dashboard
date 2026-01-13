import os
from dotenv import load_dotenv

load_dotenv()

# Database Config
DB_NAME = os.getenv("DB_NAME", "sports_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")

DB_CONFIG = {
    "dbname": DB_NAME,
    "user": DB_USER,
    "password": DB_PASSWORD
}

API_URL = "https://api-web.nhle.com/v1"