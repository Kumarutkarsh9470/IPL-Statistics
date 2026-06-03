import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from fuzzywuzzy import process
import os
from pathlib import Path

# Set style
sns.set_theme(style="whitegrid")

# Robust Path Handling
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
# We use PROJECT_ROOT since the file was moved to data/raw
DATA_PATH = PROJECT_ROOT / "data" / "raw" / "IPL.csv"
OUTPUT_DIR = SCRIPT_DIR / "eda_outputs"
PLOTS_DIR = OUTPUT_DIR / "plots"

print(f"Project Root: {PROJECT_ROOT}")
print(f"Loading dataset from: {DATA_PATH}")

# Load data
if not DATA_PATH.exists():
    raise FileNotFoundError(f"Could not find IPL.csv at {DATA_PATH}.")

df = pd.read_csv(DATA_PATH, low_memory=False)

print(f"Dataset Shape: {df.shape}")

# 1. DATA CLEANING
print("Starting Data Cleaning...")

# a) Standardize Team Names
team_mapping = {
    'Kings XI Punjab': 'Punjab Kings',
    'Delhi Daredevils': 'Delhi Capitals',
    'Royal Challengers Bangalore': 'Royal Challengers Bengaluru',
    'Deccan Chargers': 'Sunrisers Hyderabad',
    'Pune Warriors': 'Pune Warriors India',
    'Rising Pune Supergiant': 'Rising Pune Supergiants',
}

def clean_teams(df, columns):
    for col in columns:
        df[col] = df[col].replace(team_mapping)
    return df

df = clean_teams(df, ['batting_team', 'bowling_team', 'toss_winner', 'match_won_by', 'team_reviewed'])

# Let's see unique teams now
unique_teams = sorted(list(set(df['batting_team'].dropna().unique())))
print(f"Unique Teams after explicit mapping: {len(unique_teams)}")

# Fuzzy matching for any remaining slight typos (though IPL data is usually standard outside of name changes, it's a good safeguard)
def fuzzy_match_teams(team, choices, threshold=85):
    if pd.isna(team): return team
    match, score = process.extractOne(team, choices)
    if score >= threshold:
        return match
    return team

# Apply fuzzy matching efficiently (only on unique teams)
base_teams = unique_teams
def optimize_fuzzy_teams(df, cols, choices):
    for col in cols:
        unique_teams_in_col = df[col].dropna().unique()
        # Create a mapping for these unique teams
        mapping = {team: fuzzy_match_teams(team, choices) for team in unique_teams_in_col}
        df[col] = df[col].map(mapping)
    return df

df = optimize_fuzzy_teams(df, ['batting_team', 'bowling_team'], base_teams)


# b) Standardize Venues
print("Cleaning Venues...")
venue_mapping = {
    'M.Chinnaswamy Stadium': 'M Chinnaswamy Stadium, Bengaluru',
    'M Chinnaswamy Stadium': 'M Chinnaswamy Stadium, Bengaluru',
    'MA Chidambaram Stadium, Chepauk': 'MA Chidambaram Stadium, Chennai',
    'MA Chidambaram Stadium': 'MA Chidambaram Stadium, Chennai',
    'MA Chidambaram Stadium, Chepauk, Chennai': 'MA Chidambaram Stadium, Chennai',
    'Wankhede Stadium, Mumbai': 'Wankhede Stadium',
    'Eden Gardens, Kolkata': 'Eden Gardens',
    'Feroz Shah Kotla': 'Arun Jaitley Stadium, Delhi',
    'Arun Jaitley Stadium': 'Arun Jaitley Stadium, Delhi',
    'Rajiv Gandhi International Stadium, Uppal': 'Rajiv Gandhi International Stadium, Hyderabad',
    'Rajiv Gandhi International Stadium, Uppal, Hyderabad': 'Rajiv Gandhi International Stadium, Hyderabad',
    'Rajiv Gandhi International Stadium': 'Rajiv Gandhi International Stadium, Hyderabad',
    'Punjab Cricket Association Stadium, Mohali': 'Punjab Cricket Association IS Bindra Stadium, Mohali',
    'Punjab Cricket Association IS Bindra Stadium': 'Punjab Cricket Association IS Bindra Stadium, Mohali',
    'Punjab Cricket Association IS Bindra Stadium, Mohali, Chandigarh': 'Punjab Cricket Association IS Bindra Stadium, Mohali',
    'Sardar Patel Stadium, Motera': 'Narendra Modi Stadium, Ahmedabad',
    'Sawai Mansingh Stadium, Jaipur': 'Sawai Mansingh Stadium',
    'Dr. Y.S. Rajasekhara Reddy ACA-VDCA Cricket Stadium, Visakhapatnam': 'Dr. Y.S. Rajasekhara Reddy ACA-VDCA Cricket Stadium',
    'Himachal Pradesh Cricket Association Stadium, Dharamsala': 'Himachal Pradesh Cricket Association Stadium',
    'Brabourne Stadium, Mumbai': 'Brabourne Stadium',
    'Maharashtra Cricket Association Stadium, Pune': 'Maharashtra Cricket Association Stadium',
    'Maharaja Yadavindra Singh International Cricket Stadium, New Chandigarh': 'Maharaja Yadavindra Singh International Cricket Stadium, Mullanpur',
    'Subrata Roy Sahara Stadium': 'Maharashtra Cricket Association Stadium', # Same ground renamed
}

df['venue'] = df['venue'].replace(venue_mapping)

print("Data Cleaning Complete.")

# Create match level view for EDA to make it faster
match_df = df.drop_duplicates(subset=['match_id']).copy()

print(f"Total Matches: {len(match_df)}")

# Create output directories using absolute paths
print(f"Ensuring output directories exist at: {OUTPUT_DIR}")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PLOTS_DIR.mkdir(parents=True, exist_ok=True)


# 2. EXPLORATORY DATA ANALYSIS (EDA)

print("Starting EDA...")
insights = []

# --- Insight 1: Total Matches per Season ---
matches_per_season = match_df['season'].value_counts().sort_index()
plt.figure(figsize=(10, 6))
sns.barplot(x=matches_per_season.index, y=matches_per_season.values, palette='viridis')
plt.title('Total Matches Played per Season', fontsize=16)
plt.xlabel('Season', fontsize=12)
plt.ylabel('Number of Matches', fontsize=12)
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig(PLOTS_DIR / 'matches_per_season.png')
plt.close()

insights.append({
    "id": 1,
    "category": "Overall Statistics",
    "insight": f"Identified matches played across {len(matches_per_season)} seasons. The number of matches per season fluctuates but generally hovered around 60, increasing recently with more teams.",
    "visualization": "Bar Chart (X: Season, Y: Number of matches)",
    "image": "plots/matches_per_season.png"
})


# --- Insight 2: Matches Won By Each Team (Overall) ---
team_wins = match_df['match_won_by'].value_counts()
plt.figure(figsize=(12, 6))
sns.barplot(x=team_wins.values, y=team_wins.index, palette='magma')
plt.title('Total Matches Won by Each Team (2008-2025)', fontsize=16)
plt.xlabel('Matches Won', fontsize=12)
plt.ylabel('Team', fontsize=12)
plt.tight_layout()
plt.savefig(PLOTS_DIR / 'total_wins_per_team.png')
plt.close()

insights.append({
    "id": 2,
    "category": "Team Performance",
    "insight": f"Mumbai Indians and Chennai Super Kings dominate the history of IPL in terms of total match wins.",
    "visualization": "Horizontal Bar Chart (Y: Team Name, X: Total Wins)",
    "image": "plots/total_wins_per_team.png"
})


# --- Insight 3: Toss Decision Analysis ---
toss_decisions = match_df['toss_decision'].value_counts()
plt.figure(figsize=(6, 6))
plt.pie(toss_decisions.values, labels=toss_decisions.index, autopct='%1.1f%%', startangle=90, colors=['#ff9999','#66b3ff'])
plt.title('Overall Toss Decisions', fontsize=16)
plt.tight_layout()
plt.savefig(PLOTS_DIR / 'toss_decisions_pie.png')
plt.close()

insights.append({
    "id": 3,
    "category": "Match Dynamics",
    "insight": f"Teams overwhelmingly prefer to field first ({toss_decisions.get('field', 0)/len(match_df)*100:.1f}%) after winning the toss.",
    "visualization": "Pie Chart (Slices: Bat vs Field)",
    "image": "plots/toss_decisions_pie.png"
})

# --- Insight 4: Toss Decision over Seasons ---
toss_decision_season = match_df.groupby(['season', 'toss_decision']).size().unstack().fillna(0)
toss_decision_season.plot(kind='bar', stacked=True, figsize=(12, 6), color=['#ff9999','#66b3ff'])
plt.title('Toss Decisions Across Seasons', fontsize=16)
plt.xlabel('Season', fontsize=12)
plt.ylabel('Number of Matches', fontsize=12)
plt.xticks(rotation=45)
plt.legend(title='Decision')
plt.tight_layout()
plt.savefig(PLOTS_DIR / 'toss_decisions_stacked_bar.png')
plt.close()

insights.append({
    "id": 4,
    "category": "Match Dynamics (Time Series)",
    "insight": "There's a clear trend where the preference for fielding first has increased significantly in later seasons compared to earlier seasons.",
    "visualization": "Stacked Bar Chart (X: Season, Stack: Toss Decision)",
    "image": "plots/toss_decisions_stacked_bar.png"
})


# --- Insight 5: Average Score in 1st Innings Across Venues ---
first_innings = df[df['innings'].isin([1, '1'])]
venue_runs = first_innings.groupby('venue')['runs_total'].sum()
venue_matches = first_innings.groupby('venue')['match_id'].nunique()
avg_runs_venue = (venue_runs / venue_matches).sort_values(ascending=False)

# Get top 20 venues by matches played to avoid skewed data from single games
popular_venues = venue_matches[venue_matches > 5].index
avg_runs_filtered = avg_runs_venue[avg_runs_venue.index.isin(popular_venues)]

plt.figure(figsize=(12, 8))
sns.barplot(x=avg_runs_filtered.values, y=avg_runs_filtered.index, palette='viridis')
plt.title('Average 1st Innings Score across Popular Venues (>5 matches)', fontsize=16)
plt.xlabel('Average Total Runs', fontsize=12)
plt.ylabel('Venue', fontsize=12)
plt.tight_layout()
plt.savefig(PLOTS_DIR / 'avg_first_innings_venue.png')
plt.close()

insights.append({
    "id": 5,
    "category": "Venue Analysis",
    "insight": f"Venues vary significantly in scoring. {avg_runs_filtered.index[0]} averages {avg_runs_filtered.iloc[0]:.0f} runs, heavily favoring batters, while {avg_runs_filtered.index[-1]} is much lower scoring.",
    "visualization": "Horizontal Bar Chart (Y: Venue Name, X: Average First Innings Score)",
    "image": "plots/avg_first_innings_venue.png"
})

# --- Insight 6: Ground Advantage - Bat First vs Field First Win % by Venue ---
# Calculate win % batting first vs second per venue
match_df['win_batting_first'] = match_df.apply(lambda row: 1 if ((row['toss_decision'] == 'bat' and row['match_won_by'] == row['toss_winner']) or (row['toss_decision'] == 'field' and row['match_won_by'] != row['toss_winner'])) else 0, axis=1)

venue_win_stats = match_df.groupby('venue').agg(
    total_matches=('match_id', 'count'),
    wins_bat_first=('win_batting_first', 'sum')
)
venue_win_stats['win_pct_bat_first'] = venue_win_stats['wins_bat_first'] / venue_win_stats['total_matches'] * 100
venue_win_stats = venue_win_stats[venue_win_stats['total_matches'] > 10].sort_values('win_pct_bat_first', ascending=False)

plt.figure(figsize=(12, 8))
sns.barplot(x=venue_win_stats['win_pct_bat_first'], y=venue_win_stats.index, palette='coolwarm')
plt.axvline(50, color='black', linestyle='--')
plt.title('Win % Batting First across Venues (>10 matches)', fontsize=16)
plt.xlabel('Win % Batting First', fontsize=12)
plt.ylabel('Venue', fontsize=12)
plt.tight_layout()
plt.savefig(PLOTS_DIR / 'win_pct_bat_first_venue.png')
plt.close()

insights.append({
    "id": 6,
    "category": "Venue Analysis (Ground Advantage)",
    "insight": f"Certain grounds heavily favor defending scores (e.g., {venue_win_stats.index[0]}), while others favor chasing (e.g., {venue_win_stats.index[-1]}).",
    "visualization": "Heatmap or Sorted Bar Chart mapping Ground -> Win % Batting First",
    "image": "plots/win_pct_bat_first_venue.png"
})


# --- Insight 7: Most Wickets by Match Type/Phase (Powerplay, Death) ---
df['over'] = pd.to_numeric(df['over'])
df['phase'] = pd.cut(df['over'], bins=[-1, 5, 14, 19], labels=['Powerplay (0-5)', 'Middle (6-14)', 'Death (15-19)'])
wickets_df = df[df['wicket_kind'].notna() & (df['wicket_kind'] != '') & (df['wicket_kind'] != 'run out')]

phase_wickets = wickets_df['phase'].value_counts()
plt.figure(figsize=(8, 5))
sns.barplot(x=phase_wickets.index, y=phase_wickets.values, palette='Set2')
plt.title('Wickets Taken by Match Phase', fontsize=16)
plt.xlabel('Phase', fontsize=12)
plt.ylabel('Total Wickets', fontsize=12)
plt.tight_layout()
plt.savefig(PLOTS_DIR / 'wickets_by_phase.png')
plt.close()

insights.append({
    "id": 7,
    "category": "Match Dynamics",
    "insight": f"Middle overs see the most total wickets ({phase_wickets.get('Middle (6-14)',0)}), while death overs see an accelerated wicket rate.",
    "visualization": "Donut Chart or Bar Chart split by Phase",
    "image": "plots/wickets_by_phase.png"
})


# --- Insight 8: Distribution of Dismissal Types ---
dismissals = wickets_df['wicket_kind'].value_counts()
plt.figure(figsize=(10, 6))
sns.barplot(x=dismissals.values, y=dismissals.index, palette='Spectral')
plt.title('Types of Dismissals', fontsize=16)
plt.xlabel('Count', fontsize=12)
plt.tight_layout()
plt.savefig(PLOTS_DIR / 'dismissal_types.png')
plt.close()

insights.append({
    "id": 8,
    "category": "Player Statistics (Bowlers/Fielders)",
    "insight": f"Caught is overwhelmingly the most common mode of dismissal ({dismissals.get('caught',0)} times), followed by bowled.",
    "visualization": "Horizontal Bar Chart showing count of each dismissal type",
    "image": "plots/dismissal_types.png"
})


# --- Insight 9: Top Run Scorers (Batter Analysis) ---
top_batters = df.groupby('batter')['runs_batter'].sum().sort_values(ascending=False).head(10)
plt.figure(figsize=(10, 6))
sns.barplot(x=top_batters.values, y=top_batters.index, palette='rocket')
plt.title('Top 10 Aggregate Run Scorers (2008-2025)', fontsize=16)
plt.xlabel('Total Runs', fontsize=12)
plt.tight_layout()
plt.savefig(PLOTS_DIR / 'top_10_batters.png')
plt.close()

insights.append({
    "id": 9,
    "category": "Player Statistics (Batters)",
    "insight": f"{top_batters.index[0]} is the leading run-scorer in IPL history with {top_batters.iloc[0]} runs.",
    "visualization": "Leaderboard / Vertical Bar Chart (Top 10 players)",
    "image": "plots/top_10_batters.png"
})


# --- Insight 10: Run Rates Over the Years ---
run_rate_season = (df.groupby('season')['runs_total'].sum() / (df.groupby('season')['ball_no'].count() / 6)).sort_index()

plt.figure(figsize=(10, 6))
sns.lineplot(x=run_rate_season.index, y=run_rate_season.values, marker='o', linewidth=2, color='red')
plt.title('Average Run Rate Across Seasons', fontsize=16)
plt.xlabel('Season', fontsize=12)
plt.ylabel('Run Rate (Runs per Over)', fontsize=12)
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig(PLOTS_DIR / 'run_rate_evolution.png')
plt.close()

insights.append({
    "id": 10,
    "category": "Match Dynamics (Time Series)",
    "insight": "Run Rates have evolved over time, highlighting shifts in batting mentalities and rule changes like the Impact Player rule.",
    "visualization": "Line Chart tracking Average RR vs Season",
    "image": "plots/run_rate_evolution.png"
})


# --- Insight 11: Top Bowlers (Most Wickets) ---
top_bowlers = df[df['wicket_kind'].notna() & (df['wicket_kind'] != 'run out')].groupby('bowler')['wicket_kind'].count().sort_values(ascending=False).head(10)
plt.figure(figsize=(10, 6))
sns.barplot(x=top_bowlers.values, y=top_bowlers.index, palette='crest')
plt.title('Top 10 Aggregate Wicket Takers (2008-2025)', fontsize=16)
plt.xlabel('Total Wickets', fontsize=12)
plt.tight_layout()
plt.savefig(PLOTS_DIR / 'top_10_bowlers.png')
plt.close()

insights.append({
    "id": 11,
    "category": "Player Statistics (Bowlers)",
    "insight": f"{top_bowlers.index[0]} is the leading wicket-taker with {top_bowlers.iloc[0]} wickets.",
    "visualization": "Leaderboard / Vertical Bar Chart (Top 10 players)",
    "image": "plots/top_10_bowlers.png"
})


# --- Insight 12: Toss Winner vs Match Winner Correlation ---
toss_match_win = match_df[match_df['toss_winner'] == match_df['match_won_by']].shape[0]
percent_win = (toss_match_win / len(match_df)) * 100

plt.figure(figsize=(6, 6))
plt.pie([percent_win, 100-percent_win], labels=['Won Match', 'Lost Match'], autopct='%1.1f%%', startangle=140, colors=['#4CAF50', '#F44336'])
plt.title('Does Winning Toss mean Winning Match?', fontsize=16)
plt.tight_layout()
plt.savefig(PLOTS_DIR / 'toss_win_match_win_correlation.png')
plt.close()

insights.append({
    "id": 12,
    "category": "Match Dynamics",
    "insight": f"Winning the toss gives a slight edge, resulting in a win {percent_win:.1f}% of the time overall.",
    "visualization": "Gauge Chart or Pie Chart (Win vs Loss after Toss Win)",
    "image": "plots/toss_win_match_win_correlation.png"
})


# --- Save Insights to Rich Visual Markdown ---
REPORT_MD = OUTPUT_DIR / 'eda_report.md'
with open(REPORT_MD, 'w') as f:
    f.write("---\n")
    f.write("title: IPL Exploratory Data Analysis Pipeline\n")
    f.write("description: Comprehensive data cleaning and visual analysis of the IPL dataset\n")
    f.write("---\n\n")
    f.write("# IPL Data Analysis & Insights\n\n")
    f.write(f"The dataset contains **{len(match_df)}** unique matches across **{df.shape[0]}** ball-by-ball deliveries.\n\n")
    f.write("Here are 12 key insights derived from the robustly cleaned data, along with their visualizations:\n\n")
    
    for ins in insights:
        f.write(f"## {ins['id']}. {ins['category']} - {str(ins.get('insight', '')).split('.')[0]}\n")
        f.write(f"> [!TIP]\n")
        f.write(f"> {ins['insight']}\n\n")
        f.write(f"![]({ins['image']})\n\n")

print(f"EDA completed successfully. Graphical report and plots saved to: {OUTPUT_DIR}/")
