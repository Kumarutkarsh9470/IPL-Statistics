CREATE TABLE teams (
    team_id SERIAL PRIMARY KEY,
    team_name VARCHAR(255) NOT NULL
);

CREATE TABLE venues (
    venue_id SERIAL PRIMARY KEY,
    venue_name VARCHAR(255) NOT NULL,
    city VARCHAR(255)
);

CREATE TABLE players (
    player_id SERIAL PRIMARY KEY,
    player_name VARCHAR(255) NOT NULL,
    batting_style VARCHAR(32),
    bowling_arm VARCHAR(32),
    bowling_type VARCHAR(32)
);

CREATE TABLE venue_conditions (
    venue_condition_id BIGSERIAL PRIMARY KEY,
    venue_id INT NOT NULL REFERENCES venues(venue_id),
    season INT NOT NULL,
    effective_date DATE,
    boundary_distance_m DECIMAL(5,2),
    outfield_speed DECIMAL(5,2),
    source_name VARCHAR(255),
    notes TEXT,
    UNIQUE (venue_id, season)
);

CREATE TABLE matches (
    match_id SERIAL PRIMARY KEY,
    match_date DATE,
    venue_id INT REFERENCES venues(venue_id),
    team1_id INT REFERENCES teams(team_id),
    team2_id INT REFERENCES teams(team_id),
    toss_winner_id INT REFERENCES teams(team_id),
    toss_decision VARCHAR(10) CHECK (toss_decision IN ('bat', 'field')),
    match_won_by_id INT REFERENCES teams(team_id)
);

CREATE TABLE deliveries (
    delivery_id BIGSERIAL PRIMARY KEY,
    match_id INT REFERENCES matches(match_id),
    innings INT,
    batting_team_id INT REFERENCES teams(team_id),
    bowling_team_id INT REFERENCES teams(team_id),
    over_num INT,
    ball_num INT,
    batter_id INT REFERENCES players(player_id),
    bowler_id INT REFERENCES players(player_id),
    runs_batter INT,
    runs_extras INT,
    is_wicket BOOLEAN,
    wicket_type VARCHAR(50),
    player_out_id INT REFERENCES players(player_id)
);
