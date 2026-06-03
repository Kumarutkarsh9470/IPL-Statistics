<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

require_once '../db.php';

$teamId = isset($_GET['team_id']) ? (int) $_GET['team_id'] : 0;
if ($teamId <= 0) {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'team_id is required']);
    exit;
}

try {
    // Validate team
    $teamStmt = $pdo->prepare('SELECT team_id, team_name FROM teams WHERE team_id = :team_id');
    $teamStmt->execute(['team_id' => $teamId]);
    $team = $teamStmt->fetch(PDO::FETCH_ASSOC);
    if (!$team) {
        http_response_code(404);
        echo json_encode(['success' => false, 'error' => 'Team not found']);
        exit;
    }

    // All teams seasonal summary for position calculation.
    $allSeasonStatsSql = "
        SELECT
            YEAR(m.match_date) AS season,
            t.team_id,
            COUNT(m.match_id) AS played,
            SUM(CASE WHEN m.match_won_by_id = t.team_id THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN m.match_won_by_id IS NULL THEN 1 ELSE 0 END) AS no_result
        FROM matches m
        JOIN teams t ON (m.team1_id = t.team_id OR m.team2_id = t.team_id)
        WHERE m.match_date IS NOT NULL
        GROUP BY YEAR(m.match_date), t.team_id
    ";
    $allSeasonStats = $pdo->query($allSeasonStatsSql)->fetchAll(PDO::FETCH_ASSOC);

    $seasonTable = [];
    foreach ($allSeasonStats as $row) {
        $season = (int) $row['season'];
        $played = (int) $row['played'];
        $wins = (int) $row['wins'];
        $noResult = (int) $row['no_result'];
        $effectivePlayed = max($played - $noResult, 0);
        $winPct = $effectivePlayed > 0 ? ($wins / $effectivePlayed) * 100.0 : 0.0;

        if (!isset($seasonTable[$season])) {
            $seasonTable[$season] = [];
        }

        $seasonTable[$season][] = [
            'team_id' => (int) $row['team_id'],
            'played' => $played,
            'wins' => $wins,
            'no_result' => $noResult,
            'win_pct' => $winPct
        ];
    }

    // Build position map per season.
    $positionMap = [];
    foreach ($seasonTable as $season => $rows) {
        usort($rows, function ($a, $b) {
            if ($a['wins'] !== $b['wins']) {
                return $b['wins'] <=> $a['wins'];
            }
            if (abs($a['win_pct'] - $b['win_pct']) > 0.0001) {
                return $b['win_pct'] <=> $a['win_pct'];
            }
            return $b['played'] <=> $a['played'];
        });

        $rank = 1;
        foreach ($rows as $index => $r) {
            if ($index > 0) {
                $prev = $rows[$index - 1];
                if ($r['wins'] !== $prev['wins'] || abs($r['win_pct'] - $prev['win_pct']) > 0.0001 || $r['played'] !== $prev['played']) {
                    $rank = $index + 1;
                }
            }
            $positionMap[$season][$r['team_id']] = $rank;
        }
    }

    // Team-specific seasonal match outcomes.
    $teamSeasonSql = "
        SELECT
            YEAR(m.match_date) AS season,
            COUNT(m.match_id) AS played,
            SUM(CASE WHEN m.match_won_by_id = :team_id THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN m.match_won_by_id IS NULL THEN 1 ELSE 0 END) AS no_result
        FROM matches m
        WHERE m.match_date IS NOT NULL
          AND (m.team1_id = :team_id_x OR m.team2_id = :team_id_y)
        GROUP BY YEAR(m.match_date)
        ORDER BY season DESC
    ";
    $teamSeasonStmt = $pdo->prepare($teamSeasonSql);
    $teamSeasonStmt->execute([
        'team_id' => $teamId,
        'team_id_x' => $teamId,
        'team_id_y' => $teamId
    ]);
    $teamSeasons = $teamSeasonStmt->fetchAll(PDO::FETCH_ASSOC);

    // Team average runs per match by season.
    $avgRunsSql = "
        SELECT
            YEAR(m.match_date) AS season,
            SUM(d.runs_batter + d.runs_extras) AS total_runs,
            COUNT(DISTINCT d.match_id) AS batting_matches
        FROM deliveries d
        JOIN matches m ON d.match_id = m.match_id
        WHERE m.match_date IS NOT NULL
          AND d.batting_team_id = :team_id
        GROUP BY YEAR(m.match_date)
    ";
    $avgRunsStmt = $pdo->prepare($avgRunsSql);
    $avgRunsStmt->execute(['team_id' => $teamId]);
    $avgRunsRows = $avgRunsStmt->fetchAll(PDO::FETCH_ASSOC);
    $avgRunsMap = [];
    $overallRuns = 0;
    $overallBattingMatches = 0;
    foreach ($avgRunsRows as $row) {
        $season = (int) $row['season'];
        $totalRuns = (int) $row['total_runs'];
        $battingMatches = (int) $row['batting_matches'];
        $avgRunsMap[$season] = $battingMatches > 0 ? round($totalRuns / $battingMatches, 2) : 0.0;
        $overallRuns += $totalRuns;
        $overallBattingMatches += $battingMatches;
    }

    // Top scorers by season for selected team.
    $seasonBattersSql = "
        SELECT
            YEAR(m.match_date) AS season,
            p.player_name,
            SUM(d.runs_batter) AS runs
        FROM deliveries d
        JOIN matches m ON d.match_id = m.match_id
        JOIN players p ON d.batter_id = p.player_id
        WHERE m.match_date IS NOT NULL
          AND d.batting_team_id = :team_id
        GROUP BY YEAR(m.match_date), p.player_id, p.player_name
        ORDER BY season DESC, runs DESC, p.player_name ASC
    ";
    $seasonBattersStmt = $pdo->prepare($seasonBattersSql);
    $seasonBattersStmt->execute(['team_id' => $teamId]);
    $seasonBatters = $seasonBattersStmt->fetchAll(PDO::FETCH_ASSOC);
    $topScorerMap = [];
    foreach ($seasonBatters as $row) {
        $season = (int) $row['season'];
        if (!isset($topScorerMap[$season])) {
            $topScorerMap[$season] = [
                'player_name' => $row['player_name'],
                'runs' => (int) $row['runs']
            ];
        }
    }

    // Top wicket-takers by season for selected team.
    $seasonBowlersSql = "
        SELECT
            YEAR(m.match_date) AS season,
            p.player_name,
            SUM(CASE WHEN d.is_wicket = 1 AND d.wicket_type != 'run out' THEN 1 ELSE 0 END) AS wickets
        FROM deliveries d
        JOIN matches m ON d.match_id = m.match_id
        JOIN players p ON d.bowler_id = p.player_id
        WHERE m.match_date IS NOT NULL
          AND d.bowling_team_id = :team_id
        GROUP BY YEAR(m.match_date), p.player_id, p.player_name
        ORDER BY season DESC, wickets DESC, p.player_name ASC
    ";
    $seasonBowlersStmt = $pdo->prepare($seasonBowlersSql);
    $seasonBowlersStmt->execute(['team_id' => $teamId]);
    $seasonBowlers = $seasonBowlersStmt->fetchAll(PDO::FETCH_ASSOC);
    $topWicketMap = [];
    foreach ($seasonBowlers as $row) {
        $season = (int) $row['season'];
        if (!isset($topWicketMap[$season])) {
            $topWicketMap[$season] = [
                'player_name' => $row['player_name'],
                'wickets' => (int) $row['wickets']
            ];
        }
    }

    // Overall top scorer.
    $overallTopScorerSql = "
        SELECT
            p.player_name,
            SUM(d.runs_batter) AS runs
        FROM deliveries d
        JOIN players p ON d.batter_id = p.player_id
        WHERE d.batting_team_id = :team_id
        GROUP BY p.player_id, p.player_name
        ORDER BY runs DESC, p.player_name ASC
        LIMIT 1
    ";
    $overallTopScorerStmt = $pdo->prepare($overallTopScorerSql);
    $overallTopScorerStmt->execute(['team_id' => $teamId]);
    $overallTopScorer = $overallTopScorerStmt->fetch(PDO::FETCH_ASSOC);

    // Overall top wicket taker.
    $overallTopWicketSql = "
        SELECT
            p.player_name,
            SUM(CASE WHEN d.is_wicket = 1 AND d.wicket_type != 'run out' THEN 1 ELSE 0 END) AS wickets
        FROM deliveries d
        JOIN players p ON d.bowler_id = p.player_id
        WHERE d.bowling_team_id = :team_id
        GROUP BY p.player_id, p.player_name
        ORDER BY wickets DESC, p.player_name ASC
        LIMIT 1
    ";
    $overallTopWicketStmt = $pdo->prepare($overallTopWicketSql);
    $overallTopWicketStmt->execute(['team_id' => $teamId]);
    $overallTopWicket = $overallTopWicketStmt->fetch(PDO::FETCH_ASSOC);

    $seasonal = [];
    $bestSeason = null;
    $overallMatches = 0;
    $overallWins = 0;

    foreach ($teamSeasons as $row) {
        $season = (int) $row['season'];
        $played = (int) $row['played'];
        $wins = (int) $row['wins'];
        $noResult = (int) $row['no_result'];
        $losses = max($played - $wins - $noResult, 0);
        $effectivePlayed = max($played - $noResult, 0);
        $winPct = $effectivePlayed > 0 ? round(($wins / $effectivePlayed) * 100, 2) : 0.0;

        $position = $positionMap[$season][$teamId] ?? null;
        $avgRuns = $avgRunsMap[$season] ?? 0.0;
        $topScorer = $topScorerMap[$season] ?? ['player_name' => 'N/A', 'runs' => 0];
        $topWicket = $topWicketMap[$season] ?? ['player_name' => 'N/A', 'wickets' => 0];

        $seasonRow = [
            'season' => $season,
            'position' => $position,
            'played' => $played,
            'wins' => $wins,
            'losses' => $losses,
            'no_result' => $noResult,
            'win_pct' => $winPct,
            'avg_runs_per_match' => (float) $avgRuns,
            'top_scorer' => $topScorer,
            'top_wicket_taker' => $topWicket
        ];

        $seasonal[] = $seasonRow;

        if ($bestSeason === null || $seasonRow['win_pct'] > $bestSeason['win_pct']) {
            $bestSeason = $seasonRow;
        }

        $overallMatches += $played;
        $overallWins += $wins;
    }

    $overallNoResult = array_sum(array_map(function ($s) {
        return (int) $s['no_result'];
    }, $seasonal));
    $overallEffectivePlayed = max($overallMatches - $overallNoResult, 0);

    $response = [
        'success' => true,
        'team' => [
            'team_id' => (int) $team['team_id'],
            'team_name' => $team['team_name']
        ],
        'overall' => [
            'seasons_played' => count($seasonal),
            'total_matches' => $overallMatches,
            'total_wins' => $overallWins,
            'overall_win_pct' => $overallEffectivePlayed > 0 ? round(($overallWins / $overallEffectivePlayed) * 100, 2) : 0.0,
            'avg_runs_per_match' => $overallBattingMatches > 0 ? round($overallRuns / $overallBattingMatches, 2) : 0.0,
            'best_season' => $bestSeason ? $bestSeason['season'] : null,
            'best_season_win_pct' => $bestSeason ? $bestSeason['win_pct'] : 0.0,
            'overall_top_scorer' => $overallTopScorer ? [
                'player_name' => $overallTopScorer['player_name'],
                'runs' => (int) $overallTopScorer['runs']
            ] : ['player_name' => 'N/A', 'runs' => 0],
            'overall_top_wicket_taker' => $overallTopWicket ? [
                'player_name' => $overallTopWicket['player_name'],
                'wickets' => (int) $overallTopWicket['wickets']
            ] : ['player_name' => 'N/A', 'wickets' => 0]
        ],
        'seasonal' => $seasonal
    ];

    echo json_encode($response);
} catch (\PDOException $e) {
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => 'Query failed: ' . $e->getMessage()]);
}
?>