erDiagram
    TEAMS {
        int team_id PK
        string team_name
    }

    VENUES {
        int venue_id PK
        string venue_name
        string city
    }

    PLAYERS {
        int player_id PK
        string player_name
        string batting_style
        string bowling_arm
        string bowling_type
    }

    VENUE_CONDITIONS {
        bigint venue_condition_id PK
        int venue_id FK
        int season
        date effective_date
        decimal boundary_distance_m
        decimal outfield_speed
    }

    MATCHES {
        int match_id PK
        date match_date
        int venue_id FK
        int team1_id FK
        int team2_id FK
        int toss_winner_id FK
        string toss_decision "bat or field"
        int match_won_by_id FK "Nullable if tie/no result"
    }

    DELIVERIES {
        bigint delivery_id PK
        int match_id FK
        int innings 
        int batting_team_id FK
        int bowling_team_id FK
        int over_num
        int ball_num
        int batter_id FK
        int bowler_id FK
        int runs_batter
        int runs_extras
        boolean is_wicket
        string wicket_type "Nullable (e.g., bowled, caught)"
        int player_out_id FK "Nullable"
    }

    %% Relationships
    VENUES ||--o{ MATCHES : "hosts"
    VENUES ||--o{ VENUE_CONDITIONS : "has seasonal conditions"
    TEAMS ||--o{ MATCHES : "plays as team 1"
    TEAMS ||--o{ MATCHES : "plays as team 2"
    TEAMS ||--o{ MATCHES : "wins toss"
    TEAMS ||--o{ MATCHES : "wins match"
    
    MATCHES ||--o{ DELIVERIES : "contains"
    
    TEAMS ||--o{ DELIVERIES : "bats"
    TEAMS ||--o{ DELIVERIES : "bowls"
    
    PLAYERS ||--o{ DELIVERIES : "faces ball as batter"
    PLAYERS ||--o{ DELIVERIES : "bowls ball"
    PLAYERS ||--o{ DELIVERIES : "gets out"
erDiagram
    TEAMS {
        int team_id PK
        string team_name
    }

    VENUES {
        int venue_id PK
        string venue_name
        string city
    }

    PLAYERS {
        int player_id PK
        string player_name
    }

    MATCHES {
        int match_id PK
        date match_date
        int venue_id FK
        int team1_id FK
        int team2_id FK
        int toss_winner_id FK
        string toss_decision "bat or field"
        int match_won_by_id FK "Nullable if tie/no result"
    }

    DELIVERIES {
        bigint delivery_id PK
        int match_id FK
        int innings 
        int batting_team_id FK
        int bowling_team_id FK
        int over_num
        int ball_num
        int batter_id FK
        int bowler_id FK
        int runs_batter
        int runs_extras
        boolean is_wicket
        string wicket_type "Nullable (e.g., bowled, caught)"
        int player_out_id FK "Nullable"
    }

    %% Relationships
    VENUES ||--o{ MATCHES : "hosts"
    TEAMS ||--o{ MATCHES : "plays as team 1"
    TEAMS ||--o{ MATCHES : "plays as team 2"
    TEAMS ||--o{ MATCHES : "wins toss"
    TEAMS ||--o{ MATCHES : "wins match"
    
    MATCHES ||--o{ DELIVERIES : "contains"
    
    TEAMS ||--o{ DELIVERIES : "bats"
    TEAMS ||--o{ DELIVERIES : "bowls"
    
    PLAYERS ||--o{ DELIVERIES : "faces ball as batter"
    PLAYERS ||--o{ DELIVERIES : "bowls ball"
    PLAYERS ||--o{ DELIVERIES : "gets out"
