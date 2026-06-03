CREATE DATABASE IF NOT EXISTS ipl_db;
USE ipl_db;

CREATE TABLE IF NOT EXISTS teams (
    team_id INT AUTO_INCREMENT PRIMARY KEY,
    team_name VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS venues (
    venue_id INT AUTO_INCREMENT PRIMARY KEY,
    venue_name VARCHAR(255) NOT NULL,
    city VARCHAR(255),
    UNIQUE(venue_name, city)
);

CREATE TABLE IF NOT EXISTS players (
    player_id INT AUTO_INCREMENT PRIMARY KEY,
    player_name VARCHAR(255) NOT NULL UNIQUE,
    batting_style VARCHAR(32),
    bowling_arm VARCHAR(32),
    bowling_type VARCHAR(32)
);

CREATE TABLE IF NOT EXISTS venue_conditions (
    venue_condition_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    venue_id INT NOT NULL,
    season INT NOT NULL,
    effective_date DATE,
    boundary_distance_m DECIMAL(5,2),
    outfield_speed DECIMAL(5,2),
    source_name VARCHAR(255),
    notes TEXT,
    UNIQUE (venue_id, season),
    FOREIGN KEY (venue_id) REFERENCES venues(venue_id)
);

CREATE TABLE IF NOT EXISTS matches (
    match_id INT AUTO_INCREMENT PRIMARY KEY,
    match_date DATE,
    venue_id INT,
    team1_id INT,
    team2_id INT,
    toss_winner_id INT,
    toss_decision ENUM('bat', 'field'),
    match_won_by_id INT,
    FOREIGN KEY (venue_id) REFERENCES venues(venue_id),
    FOREIGN KEY (team1_id) REFERENCES teams(team_id),
    FOREIGN KEY (team2_id) REFERENCES teams(team_id),
    FOREIGN KEY (toss_winner_id) REFERENCES teams(team_id),
    FOREIGN KEY (match_won_by_id) REFERENCES teams(team_id)
);

CREATE TABLE IF NOT EXISTS deliveries (
    delivery_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    match_id INT,
    innings INT,
    batting_team_id INT,
    bowling_team_id INT,
    over_num INT,
    ball_num INT,
    batter_id INT,
    bowler_id INT,
    runs_batter INT,
    runs_extras INT,
    is_wicket BOOLEAN,
    wicket_type VARCHAR(50),
    player_out_id INT,
    FOREIGN KEY (match_id) REFERENCES matches(match_id),
    FOREIGN KEY (batting_team_id) REFERENCES teams(team_id),
    FOREIGN KEY (bowling_team_id) REFERENCES teams(team_id),
    FOREIGN KEY (batter_id) REFERENCES players(player_id),
    FOREIGN KEY (bowler_id) REFERENCES players(player_id),
    FOREIGN KEY (player_out_id) REFERENCES players(player_id)
);
