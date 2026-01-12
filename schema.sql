CREATE TABLE IF NOT EXISTS teams (
    team_id INT PRIMARY KEY,        -- Official NHL ID
    name VARCHAR(50) NOT NULL,      -- Full team name
    abbrev VARCHAR(5) NOT NULL,     -- Team abbreviation
    conference VARCHAR(10)          -- "East" or "West"
);

CREATE TABLE IF NOT EXISTS season_outcomes (
    season_id INT,                              -- e.g., 20242025
    team_id INT REFERENCES teams(team_id),      -- Links to teams table
    made_playoffs BOOLEAN NOT NULL,             -- True (1) or False (0)
    points INT,                                 -- Final points
    PRIMARY KEY (season_id, team_id)            -- Primary key
);

CREATE TABLE IF NOT EXISTS daily_standings (
    id SERIAL PRIMARY KEY,                  -- Auto-incrementing unique ID for every row
    date DATE NOT NULL,                     -- "Snapshot" date (e.g., 2023-11-15)
    season_id INT NOT NULL,                 -- Helps group data by year
    team_id INT REFERENCES teams(team_id),  -- Links to the team

    games_played INT NOT NULL,
    wins INT NOT NULL,
    losses INT NOT NULL,
    ot_losses INT NOT NULL,
    points INT NOT NULL,
    regulation_wins INT NOT NULL,
    goals_for INT,
    goals_against INT,

    UNIQUE (date, team_id)
);

CREATE INDEX IF NOT EXISTS idx_standings_date ON daily_standings(date);
CREATE INDEX IF NOT EXISTS idx_standings_team ON daily_standings(team_id);