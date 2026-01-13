# Sports Dashboard

## 🏒 NHL Standings and Playoff Predictor

A full-stack sports analytics platform that predicts NHL playoff probabilities in real-time. This project combines a FastAPI backend, a React frontend, and a Machine Learning pipeline to analyze team performance and forecast season outcomes.

### Requirements
- Python 3.9+
- PostgreSQL installed and running

## Installation

Clone the repo and install dependencies:
```
git clone https://github.com/JosephCheung0327/sports-dashboard.git
cd sports-dashboard
pip install -r requirements.txt
```

## Database Setup

Create a .env file in the root directory with your database credentials:

```
DB_NAME=sports_db
DB_USER=postgres
DB_PASSWORD=yourpassword
```

Initialize the database:
```
python -m database.reset_db
```

## Data & Model Training

Seed static data (teams) and fetch historical stats:

```
python -m etl.seed_static_data
python -m etl.update_history
```

Train the machine learning model:

```
python -m models.train
```

(This will compare models, pick the best one, and save it to models/playoff_predictor.pkl)

Fetch live data for the current season:
```
python -m etl.update_live
```

## Running the App

Start the Backend Server:
```
uvicorn backend.main:app --reload
```

Start the Frontend:
```
python -m http.server 3000 --directory frontend
```
Then visit http://localhost:3000.

---
MLB and NBA stats coming soon :)