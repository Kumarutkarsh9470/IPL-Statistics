---
title: IPL Exploratory Data Analysis Pipeline
description: Comprehensive data cleaning and visual analysis of the IPL dataset
---

# IPL Data Analysis & Insights

The dataset contains **1169** unique matches across **278205** ball-by-ball deliveries.

Here are 12 key insights derived from the robustly cleaned data, along with their visualizations:

## 1. Overall Statistics - Identified matches played across 18 seasons
> [!TIP]
> Identified matches played across 18 seasons. The number of matches per season fluctuates but generally hovered around 60, increasing recently with more teams.

![](plots/matches_per_season.png)

## 2. Team Performance - Mumbai Indians and Chennai Super Kings dominate the history of IPL in terms of total match wins
> [!TIP]
> Mumbai Indians and Chennai Super Kings dominate the history of IPL in terms of total match wins.

![](plots/total_wins_per_team.png)

## 3. Match Dynamics - Teams overwhelmingly prefer to field first (65
> [!TIP]
> Teams overwhelmingly prefer to field first (65.4%) after winning the toss.

![](plots/toss_decisions_pie.png)

## 4. Match Dynamics (Time Series) - There's a clear trend where the preference for fielding first has increased significantly in later seasons compared to earlier seasons
> [!TIP]
> There's a clear trend where the preference for fielding first has increased significantly in later seasons compared to earlier seasons.

![](plots/toss_decisions_stacked_bar.png)

## 5. Venue Analysis - Venues vary significantly in scoring
> [!TIP]
> Venues vary significantly in scoring. Himachal Pradesh Cricket Association Stadium averages 183 runs, heavily favoring batters, while Newlands is much lower scoring.

![](plots/avg_first_innings_venue.png)

## 6. Venue Analysis (Ground Advantage) - Certain grounds heavily favor defending scores (e
> [!TIP]
> Certain grounds heavily favor defending scores (e.g., Himachal Pradesh Cricket Association Stadium), while others favor chasing (e.g., SuperSport Park).

![](plots/win_pct_bat_first_venue.png)

## 7. Match Dynamics - Middle overs see the most total wickets (5009), while death overs see an accelerated wicket rate
> [!TIP]
> Middle overs see the most total wickets (5009), while death overs see an accelerated wicket rate.

![](plots/wickets_by_phase.png)

## 8. Player Statistics (Bowlers/Fielders) - Caught is overwhelmingly the most common mode of dismissal (8665 times), followed by bowled
> [!TIP]
> Caught is overwhelmingly the most common mode of dismissal (8665 times), followed by bowled.

![](plots/dismissal_types.png)

## 9. Player Statistics (Batters) - V Kohli is the leading run-scorer in IPL history with 8671 runs
> [!TIP]
> V Kohli is the leading run-scorer in IPL history with 8671 runs.

![](plots/top_10_batters.png)

## 10. Match Dynamics (Time Series) - Run Rates have evolved over time, highlighting shifts in batting mentalities and rule changes like the Impact Player rule
> [!TIP]
> Run Rates have evolved over time, highlighting shifts in batting mentalities and rule changes like the Impact Player rule.

![](plots/run_rate_evolution.png)

## 11. Player Statistics (Bowlers) - YS Chahal is the leading wicket-taker with 221 wickets
> [!TIP]
> YS Chahal is the leading wicket-taker with 221 wickets.

![](plots/top_10_bowlers.png)

## 12. Match Dynamics - Winning the toss gives a slight edge, resulting in a win 50
> [!TIP]
> Winning the toss gives a slight edge, resulting in a win 50.6% of the time overall.

![](plots/toss_win_match_win_correlation.png)

