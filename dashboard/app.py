import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import joblib
import sys
import os
import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from database.db_utils import get_connection

def load_model():
    model_path = os.path.join(parent_dir, 'models', 'playoff_predictor.pkl')

    try:
        return joblib.load(model_path)

    except FileNotFoundError:
        return None

def load_data():
    conn = get_connection()
    query = """
    WITH LatestDate AS (
        SELECT max(date) as max_date 
        FROM daily_standings 
        WHERE season_id = 20252026
    )
    SELECT
        t.name,
        t.abbrev,
        t.conference,
        t.division,
        t.logo_url,
        ds.games_played,
        ds.wins,
        ds.losses,
        ds.ot_losses,
        ds.points,
        ds.goals_for,
        ds.goals_against
    FROM daily_standings ds
    JOIN teams t ON ds.team_id = t.team_id
    JOIN LatestDate ld ON ds.date = ld.max_date
    WHERE ds.season_id = 20252026;
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def predict_playoffs(df):
    model = load_model()
    if model is None:
        raise FileNotFoundError("Model not found at 'models/playoff_predictor.pkl'. Place the trained model there or update load_model().")

    df = df.copy()
    # recreate training-time features
    df['goal_diff'] = df['goals_for'] - df['goals_against']
    df['win_pct'] = df['wins'] / df['games_played'].replace(0, np.nan)

    # Ensure expected columns exist and fill/clean
    df[['games_played', 'points', 'win_pct', 'goal_diff']] = df[['games_played', 'points', 'win_pct', 'goal_diff']].fillna(0)
    features = ['games_played', 'points', 'win_pct', 'goal_diff']

    X = df[features]

    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(X)[:, 1]
    else:
        probs = model.predict(X).astype(float)

    df['Playoff Probability'] = np.clip(probs, 0.0, 1.0)
    return df

st.set_page_config(page_title="NHL Playoffs Predictor", layout="wide")
st.title("🏒 NHL Playoffs Predictor (2025-2026)")

try:
    df = load_data()
    df = predict_playoffs(df)
    
    # --- TEAM SEARCH FEATURE ---
    st.sidebar.header("Find Your Team")
    # Create a list of names for the dropdown
    team_list = sorted(df['name'].unique())
    selected_team_name = st.sidebar.selectbox("Select a Team", team_list, index=None, placeholder="Choose a team...")

    # If a team is selected, show the "Spotlight"
    if selected_team_name:
        team_data = df[df['name'] == selected_team_name].iloc[0]
        prob = team_data['Playoff Probability']
        
        st.markdown("---")
        
        # Layout: Logo on Left, Big Stats on Right
        col1, col2, col3 = st.columns([1, 2, 2])
        
        with col1:
            if team_data['logo_url']:
                st.image(team_data['logo_url'], width=150)
            else:
                st.write("🏒") # Fallback icon
                
        with col2:
            st.subheader(f"{team_data['name']}")
            st.caption(f"{team_data['conference']} | {team_data['division']}")
            
            # Color code the probability
            color = "green" if prob > 0.7 else "orange" if prob > 0.3 else "red"
            st.markdown(f"### Playoffs Chance: :{color}[{prob:.1%}]")
            
        with col3:
            st.metric("Points", team_data['points'])
            st.metric("Wins", team_data['wins'])
            
        st.markdown("---")

    # --- REST OF DASHBOARD (Filtered View) ---
    st.sidebar.markdown("---")
    st.sidebar.header("League Filters")
    divisions = sorted(df['division'].unique())
    selected_divs = st.sidebar.multiselect("Filter by Division", divisions, default=divisions)
    
    # Filter Data
    filtered_df = df[df['division'].isin(selected_divs)]
    
    # Main Table
    st.subheader("League Standings")
    filtered_df['Playoff Chance %'] = filtered_df['Playoff Probability'] * 100
    display_df = filtered_df.sort_values(by='Playoff Probability', ascending=False)
    
    st.dataframe(
        display_df[['name', 'conference', 'division', 'points', 'games_played', 'wins', 'losses', 'ot_losses', 'Playoff Chance %']],
        use_container_width=True,
        hide_index=True,
        column_config={
            "name": "Team",
            "conference": "Conference",
            "division": "Division",
            "points": "Points",
            "games_played": "Games",
            "wins": "Wins",
            "losses": "Losses",
            "ot_losses": "OT Losses",
            "Playoff Chance %": st.column_config.ProgressColumn(
                "Playoffs Chance",
                format="%.1f%%",
                min_value=0,
                max_value=100,
            )
        }
    )

except Exception as e:
    st.error(f"Error: {e}")
