#!/usr/bin/env python
"""
Load real venue boundary distances and calculate outfield speed from first-innings data.

Boundary Distances: User-provided mapping for 37 venues; unmapped venues default to 70m.
Outfield Speed: Calculated from avg first-innings score per venue.
  - Top tercile (highest avg)  "Fast" (1.2)
  - Middle tercile  "Medium" (1.0)
  - Bottom tercile (lowest avg)  "Slow" (0.8)
"""

import mysql.connector
from mysql.connector import Error
import numpy as np
from collections import defaultdict

# Boundary distances provided by user (in meters)
BOUNDARY_DISTANCES = {
    "Arun Jaitley Stadium": 69,
    "Barabati Stadium": 71,
    "Barsapara Cricket Stadium": 67,
    "Ekana Cricket Stadium": 70,
    "Brabourne Stadium": 66,
    "Buffalo Park": 73,
    "De Beers Diamond Oval": 74,
    "Dr DY Patil Sports Academy": 68,
    "Dr. Y.S. Rajasekhara Reddy Stadium": 71,
    "Dubai International Cricket Stadium": 73,
    "Eden Gardens": 72,
    "Green Park": 70,
    "HPCA Stadium": 67,
    "Holkar Cricket Stadium": 65,
    "JSCA International Stadium": 73,
    "Kingsmead": 73,
    "M Chinnaswamy Stadium": 63,
    "MA Chidambaram Stadium": 70,
    "Maharaja Yadavindra Singh Stadium": 66,
    "Maharashtra Cricket Association Stadium": 71,
    "Narendra Modi Stadium": 75,
    "Nehru Stadium": 72,
    "New Wanderers Stadium": 77,
    "Newlands": 76,
    "OUTsurance Oval": 74,
    "PCA IS Bindra Stadium": 72,
    "Rajiv Gandhi International Stadium": 70,
    "Saurashtra Cricket Association Stadium": 72,
    "Sawai Mansingh Stadium": 68,
    "Shaheed Veer Narayan Singh Stadium": 73,
    "Sharjah Cricket Stadium": 62,
    "Sheikh Zayed Stadium": 73,
    "St George's Park": 74,
    "SuperSport Park": 72,
    "Vidarbha Cricket Association Stadium": 82,
    "Wankhede Stadium": 67,
    "Zayed Cricket Stadium": 73,
}

DEFAULT_BOUNDARY = 70.0

# Outfield speed numeric scale
OUTFIELD_SPEED_SCALE = {
    "Fast": 1.2,
    "Medium": 1.0,
    "Slow": 0.8,
}


def get_connection():
    """Establish MySQL connection."""
    try:
        conn = mysql.connector.connect(
            host="127.0.0.1",
            user="ipl_user",
            password="password123",
            database="ipl_db",
        )
        return conn
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        raise


def get_venue_id_map(cursor):
    """Get mapping of venue names to IDs."""
    cursor.execute("SELECT venue_id, venue_name FROM venues")
    return {name: vid for vid, name in cursor.fetchall()}


def get_first_innings_scores_by_venue(cursor):
    """
    Calculate average first-innings score for each venue.
    Returns: {venue_id: avg_first_innings_score}
    """
    # First, calculate first-innings total per match
    query = """
    SELECT 
        m.venue_id,
        m.match_id,
        SUM(d.runs_batter + d.runs_extras) as first_innings_total
    FROM matches m
    JOIN deliveries d ON m.match_id = d.match_id
    WHERE d.innings = 1
    GROUP BY m.match_id, m.venue_id
    """
    cursor.execute(query)
    
    # Aggregate by venue to get average
    venue_scores = {}
    match_counts = {}
    
    for venue_id, match_id, total_runs in cursor.fetchall():
        if venue_id not in venue_scores:
            venue_scores[venue_id] = 0
            match_counts[venue_id] = 0
        venue_scores[venue_id] += float(total_runs)
        match_counts[venue_id] += 1
    
    # Calculate averages
    for venue_id in venue_scores:
        venue_scores[venue_id] = venue_scores[venue_id] / match_counts[venue_id]
    
    return venue_scores


def assign_outfield_speed_terciles(venue_scores):
    """
    Assign outfield speed categories based on terciles of first-innings scores.
    
    Args:
        venue_scores: {venue_id: avg_first_innings_score}
    
    Returns:
        {venue_id: ("Fast"/"Medium"/"Slow", numeric_value)}
    """
    if not venue_scores:
        print("Warning: No venue scores found")
        return {}

    scores = sorted(venue_scores.values())
    n = len(scores)
    
    # Calculate tercile thresholds
    p33 = np.percentile(scores, 33.33)
    p67 = np.percentile(scores, 66.67)
    
    print(f"\nOutfield Speed Tercile Thresholds:")
    print(f"  33rd percentile: {p33:.2f}")
    print(f"  67th percentile: {p67:.2f}")
    print(f"  (Bottom third ≤ {p33:.2f}, Middle: {p33:.2f}–{p67:.2f}, Top ≥ {p67:.2f})\n")
    
    result = {}
    for venue_id, score in venue_scores.items():
        if score >= p67:
            category = "Fast"
        elif score >= p33:
            category = "Medium"
        else:
            category = "Slow"
        
        numeric_value = OUTFIELD_SPEED_SCALE[category]
        result[venue_id] = (category, numeric_value)
    
    return result


def update_venue_conditions(conn, cursor, venue_id_map, venue_scores, outfield_speeds):
    """
    Update venue_conditions table with boundary distances and outfield speeds.
    """
    updated_count = 0
    inserted_count = 0
    
    print("\nUpdating venue_conditions table...\n")
    
    # Get all seasons in the data
    cursor.execute("SELECT DISTINCT YEAR(match_date) as season FROM matches ORDER BY season")
    seasons = [int(row[0]) for row in cursor.fetchall()]
    
    # For each venue in the DB
    cursor.execute("SELECT venue_id, venue_name FROM venues ORDER BY venue_id")
    venues = cursor.fetchall()
    
    for venue_id, venue_name in venues:
        # Get boundary distance (user-provided or default)
        boundary_distance = BOUNDARY_DISTANCES.get(venue_name, DEFAULT_BOUNDARY)
        
        # Get outfield speed (if calculated, otherwise default to "Medium" / 1.0)
        if venue_id in outfield_speeds:
            outfield_category, outfield_numeric = outfield_speeds[venue_id]
        else:
            outfield_category, outfield_numeric = "Medium", 1.0
        
        # For each season, insert or update venue_conditions
        for season in seasons:
            # Check if row exists
            cursor.execute(
                "SELECT 1 FROM venue_conditions WHERE venue_id = %s AND season = %s",
                (venue_id, season),
            )
            exists = cursor.fetchone() is not None
            
            if exists:
                # Update existing row
                cursor.execute(
                    """
                    UPDATE venue_conditions
                    SET boundary_distance_m = %s,
                        outfield_speed = %s
                    WHERE venue_id = %s AND season = %s
                    """,
                    (boundary_distance, outfield_numeric, venue_id, season),
                )
                updated_count += 1
            else:
                # Insert new row
                cursor.execute(
                    """
                    INSERT INTO venue_conditions
                    (venue_id, season, boundary_distance_m, outfield_speed)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (venue_id, season, boundary_distance, outfield_numeric),
                )
                inserted_count += 1
        
        boundary_source = "user-provided" if venue_name in BOUNDARY_DISTANCES else "default"
        print(
            f"  {venue_name:50s} | Boundary: {boundary_distance:5.1f}m ({boundary_source:14s}) | "
            f"Outfield: {outfield_category:6s} ({outfield_numeric:.1f})"
        )
    
    conn.commit()
    print(f"\nDatabase update summary:")
    print(f"  Rows updated: {updated_count}")
    print(f"  Rows inserted: {inserted_count}")
    
    return updated_count, inserted_count


def main():
    """Main execution."""
    print("=" * 100)
    print("Venue Data Loader: Boundary Distances & Outfield Speed Calculation")
    print("=" * 100)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Step 1: Get venue ID mapping
        print("\nStep 1: Loading venue ID mapping...")
        venue_id_map = get_venue_id_map(cursor)
        print(f"  Loaded {len(venue_id_map)} venues from database")
        
        # Step 2: Calculate first-innings scores per venue
        print("\nStep 2: Calculating first-innings scores by venue...")
        venue_scores = get_first_innings_scores_by_venue(cursor)
        print(f"  Found {len(venue_scores)} venues with first-innings data")
        
        # Step 3: Assign outfield speed terciles
        print("\nStep 3: Assigning outfield speed terciles...")
        outfield_speeds = assign_outfield_speed_terciles(venue_scores)
        
        # Print outfield speed assignments
        print("Outfield Speed Assignments:")
        for venue_id in sorted(outfield_speeds.keys()):
            # Find venue name
            for name, vid in venue_id_map.items():
                if vid == venue_id:
                    category, numeric = outfield_speeds[venue_id]
                    avg_score = venue_scores.get(venue_id, 0)
                    print(f"  {name:50s} | Avg 1st Innings: {avg_score:6.1f} | Category: {category:6s}")
                    break
        
        # Step 4: Update database
        print("\nStep 4: Updating database...")
        updated, inserted = update_venue_conditions(
            conn, cursor, venue_id_map, venue_scores, outfield_speeds
        )
        
        print("\n" + "=" * 100)
        print("✓ Venue data load complete!")
        print("=" * 100)
        
        # Summary statistics
        print("\nSummary Statistics:")
        print(f"  Total venues in system: {len(venue_id_map)}")
        print(f"  Venues with user-provided boundaries: {len(BOUNDARY_DISTANCES)}")
        print(f"  Venues with default boundary (70m): {len(venue_id_map) - len(BOUNDARY_DISTANCES)}")
        print(f"  Venues with calculated outfield speed: {len(outfield_speeds)}")
        
    except Error as e:
        print(f"Error: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
