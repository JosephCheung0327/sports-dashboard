DROP TABLE IF EXISTS daily_standings;
DROP TABLE IF EXISTS season_outcomes;
DROP TABLE IF EXISTS teams;

CREATE TABLE IF NOT EXISTS teams (
    team_id SERIAL PRIMARY KEY,         -- Official NHL ID
    name VARCHAR(100) NOT NULL,         -- Full team name
    abbrev VARCHAR(10) UNIQUE,          -- Team abbreviation
    conference VARCHAR(50),
    division VARCHAR(50),
    logo_url TEXT
);

CREATE TABLE season_outcomes (
    id SERIAL PRIMARY KEY,
    season_id INT,
    team_id INT REFERENCES teams(team_id),
    made_playoffs BOOLEAN,
    points INT,
    UNIQUE(season_id, team_id) -- One outcome per team per season
);

CREATE TABLE daily_standings (
    id SERIAL PRIMARY KEY,
    date DATE,
    season_id INT,
    team_id INT REFERENCES teams(team_id),
    games_played INT,
    wins INT,
    losses INT,
    ot_losses INT,
    points INT,
    goals_for INT,
    goals_against INT,
    l10_points INT DEFAULT 0,
    streak_code VARCHAR(5),     -- 'W', 'L', 'OT'
    streak_count INT DEFAULT 0,
    UNIQUE(date, team_id)       -- One record per team per day
);