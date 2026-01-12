import streamlit as st
import pandas as pd
import psycopg2
import pickle
import plotly.express as px

# --- CONFIG ---
DB_CONFIG = {
    "dbname": "nhl_analytics",
    "user": "postgres",
    "password": "nhldb0112"
}

def load_data():
    conn = psycopg2.connect(**DB_CONFIG)
    # Added 't.logo_url' to query
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
        d.games_played, 
        d.wins, 
        d.points, 
        d.goals_for, 
        d.goals_against
    FROM daily_standings d
    JOIN teams t ON d.team_id = t.team_id
    JOIN LatestDate ld ON d.date = ld.max_date
    WHERE d.season_id = 20252026;
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def predict_playoffs(df):
    with open('playoff_model.pkl', 'rb') as f:
        model = pickle.load(f)
        
    df['point_pct'] = df['points'] / (df['games_played'] * 2)
    df['goal_diff_per_game'] = (df['goals_for'] - df['goals_against']) / df['games_played']
    df['win_pct'] = df['wins'] / df['games_played']
    
    features = ['point_pct', 'goal_diff_per_game', 'win_pct']
    probs = model.predict_proba(df[features])[:, 1]
    df['Playoff Probability'] = probs
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
            st.markdown(f"### Playoff Chance: :{color}[{prob:.1%}]")
            
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
        display_df[['name', 'division', 'points', 'wins', 'Playoff Chance %']],
        use_container_width=True,
        hide_index=True,
        column_config={
            "name": "Team",
            "Playoff Chance %": st.column_config.ProgressColumn(
                "Playoff Chance",
                format="%.1f%%",
                min_value=0,
                max_value=100,
            )
        }
    )

except Exception as e:
    st.error(f"Error: {e}")