"""
Database connection helper using SQLAlchemy.
Reads from the local MySQL ipl_db.
"""
import pandas as pd
from sqlalchemy import create_engine
from urllib.parse import urlparse
from ml.config import DB_CONFIG

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        if DB_CONFIG.get("url"):
            parsed = urlparse(DB_CONFIG["url"])
            user = parsed.username or DB_CONFIG.get("user")
            password = parsed.password or DB_CONFIG.get("password")
            host = parsed.hostname or DB_CONFIG.get("host")
            port = parsed.port or DB_CONFIG.get("port")
            database = parsed.path.lstrip("/") or DB_CONFIG.get("database")
            url = (
                f"mysql+mysqlconnector://{user}:{password}"
                f"@{host}:{port}/{database}"
            )
        else:
            url = (
                f"mysql+mysqlconnector://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
                f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
            )
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def load_matches() -> pd.DataFrame:
    """Load match-level data with venue info."""
    query = """
    SELECT
        m.match_id, m.match_date, m.venue_id,
        m.team1_id, m.team2_id,
        m.toss_winner_id, m.toss_decision,
        m.match_won_by_id,
        v.venue_name, v.city,
        vc.boundary_distance_m, vc.outfield_speed,
        t1.team_name AS team1_name,
        t2.team_name AS team2_name,
        tw.team_name AS toss_winner_name,
        mw.team_name AS match_winner_name
    FROM matches m
    JOIN venues v ON m.venue_id = v.venue_id
    LEFT JOIN (
        SELECT vc1.venue_id, vc1.boundary_distance_m, vc1.outfield_speed
        FROM venue_conditions vc1
        INNER JOIN (
            SELECT venue_id, MAX(season) AS season
            FROM venue_conditions
            GROUP BY venue_id
        ) latest
        ON vc1.venue_id = latest.venue_id AND vc1.season = latest.season
    ) vc ON m.venue_id = vc.venue_id
    JOIN teams t1 ON m.team1_id = t1.team_id
    JOIN teams t2 ON m.team2_id = t2.team_id
    LEFT JOIN teams tw ON m.toss_winner_id = tw.team_id
    LEFT JOIN teams mw ON m.match_won_by_id = mw.team_id
    ORDER BY m.match_date, m.match_id
    """
    return pd.read_sql(query, get_engine(), parse_dates=["match_date"])


def load_deliveries() -> pd.DataFrame:
    """Load ball-by-ball delivery data with match date and venue."""
    query = """
    SELECT
        d.delivery_id, d.match_id, d.innings,
        d.batting_team_id, d.bowling_team_id,
        d.over_num, d.ball_num,
        d.batter_id, d.bowler_id,
        d.runs_batter, d.runs_extras,
        d.is_wicket, d.wicket_type, d.player_out_id,
        m.match_date, m.venue_id
    FROM deliveries d
    JOIN matches m ON d.match_id = m.match_id
    ORDER BY m.match_date, d.match_id, d.innings, d.over_num, d.ball_num
    """
    return pd.read_sql(query, get_engine(), parse_dates=["match_date"])


def load_teams() -> pd.DataFrame:
    return pd.read_sql("SELECT team_id, team_name FROM teams", get_engine())


def load_venues() -> pd.DataFrame:
    query = """
    SELECT
        v.venue_id, v.venue_name, v.city,
        vc.boundary_distance_m, vc.outfield_speed
    FROM venues v
    LEFT JOIN (
        SELECT vc1.venue_id, vc1.boundary_distance_m, vc1.outfield_speed
        FROM venue_conditions vc1
        INNER JOIN (
            SELECT venue_id, MAX(season) AS season
            FROM venue_conditions
            GROUP BY venue_id
        ) latest
        ON vc1.venue_id = latest.venue_id AND vc1.season = latest.season
    ) vc ON v.venue_id = vc.venue_id
    ORDER BY v.venue_id
    """
    return pd.read_sql(query, get_engine())


def load_players() -> pd.DataFrame:
    return pd.read_sql(
        "SELECT player_id, player_name, batting_style, bowling_arm, bowling_type FROM players ORDER BY player_id",
        get_engine(),
    )
