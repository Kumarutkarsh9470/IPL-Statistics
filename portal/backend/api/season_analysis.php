<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

require_once '../db.php';

$season = isset($_GET['season']) ? (int) $_GET['season'] : 0;
if ($season <= 0) {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'season parameter is required']);
    exit;
}

try {
    // 1. Get all teams' stats for the season to determine points table, winning & runner-up teams
    $pointsTableSql = "
        SELECT
            t.team_id,
            t.team_name,
            COUNT(m.match_id) AS matches_played,
            SUM(CASE WHEN m.match_won_by_id = t.team_id THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN m.match_won_by_id IS NOT NULL AND m.match_won_by_id != t.team_id THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN m.match_won_by_id IS NULL THEN 1 ELSE 0 END) AS no_result
        FROM teams t
        LEFT JOIN matches m ON (m.team1_id = t.team_id OR m.team2_id = t.team_id)
            AND YEAR(m.match_date) = :season
            AND m.match_date IS NOT NULL
        GROUP BY t.team_id, t.team_name
        HAVING COUNT(m.match_id) > 0
        ORDER BY wins DESC, 
            (CASE WHEN COUNT(m.match_id) > 0 THEN (SUM(CASE WHEN m.match_won_by_id = t.team_id THEN 1 ELSE 0 END) / (COUNT(m.match_id) - SUM(CASE WHEN m.match_won_by_id IS NULL THEN 1 ELSE 0 END))) ELSE 0 END) DESC
    ";
    
    $pointsStmt = $pdo->prepare($pointsTableSql);
    $pointsStmt->execute(['season' => $season]);
    $pointsTable = $pointsStmt->fetchAll(PDO::FETCH_ASSOC);

    if (empty($pointsTable)) {
        http_response_code(404);
        echo json_encode(['success' => false, 'error' => 'No data found for season ' . $season]);
        exit;
    }

    $winningTeam = [];
    $runnerUpTeam = [];

    foreach ($pointsTable as $idx => $team) {
        $team['matches_played'] = (int) $team['matches_played'];
        $team['wins'] = (int) $team['wins'];
        $team['losses'] = (int) $team['losses'];
        $team['no_result'] = (int) $team['no_result'];
        
        $effectiveMatches = $team['matches_played'] - $team['no_result'];
        $team['win_pct'] = $effectiveMatches > 0 ? ($team['wins'] / $effectiveMatches) * 100.0 : 0.0;
        $team['points'] = ($team['wins'] * 2) + ($team['no_result'] * 1);
        
        $pointsTable[$idx] = $team;

        if ($idx === 0) {
            $winningTeam = $team;
        }
        if ($idx === 1) {
            $runnerUpTeam = $team;
        }
    }

    // 2. Get top 5 run scorers (batters) for the season
    $topBattersSql = "
        SELECT
            p.player_id,
            p.player_name,
            SUM(d.runs_batter) AS total_runs,
            COUNT(DISTINCT m.match_id) AS matches
        FROM players p
        JOIN deliveries d ON p.player_id = d.batter_id
        JOIN matches m ON d.match_id = m.match_id
        WHERE YEAR(m.match_date) = :season
            AND m.match_date IS NOT NULL
        GROUP BY p.player_id, p.player_name
        ORDER BY total_runs DESC
        LIMIT 5
    ";

    $batsStmt = $pdo->prepare($topBattersSql);
    $batsStmt->execute(['season' => $season]);
    $topBatters = $batsStmt->fetchAll(PDO::FETCH_ASSOC);

    foreach ($topBatters as &$batter) {
        $batter['total_runs'] = (int) $batter['total_runs'];
        $batter['matches'] = (int) $batter['matches'];
    }

    // 3. Get top 5 wicket takers (bowlers) for the season
    $topBowlersSql = "
        SELECT
            p.player_id,
            p.player_name,
            COUNT(d.delivery_id) AS wickets,
            COUNT(DISTINCT m.match_id) AS matches
        FROM players p
        JOIN deliveries d ON p.player_id = d.bowler_id
        JOIN matches m ON d.match_id = m.match_id
        WHERE d.wicket_type IS NOT NULL
            AND YEAR(m.match_date) = :season
            AND m.match_date IS NOT NULL
        GROUP BY p.player_id, p.player_name
        ORDER BY wickets DESC
        LIMIT 5
    ";

    $bowlStmt = $pdo->prepare($topBowlersSql);
    $bowlStmt->execute(['season' => $season]);
    $topBowlers = $bowlStmt->fetchAll(PDO::FETCH_ASSOC);

    foreach ($topBowlers as &$bowler) {
        $bowler['wickets'] = (int) $bowler['wickets'];
        $bowler['matches'] = (int) $bowler['matches'];
    }

    // 4. Get highest team innings for the season
    $highestInningsSql = "
        SELECT
            t.team_name,
            SUM(d.runs_batter) AS innings_total
        FROM matches m
        JOIN deliveries d ON m.match_id = d.match_id
        JOIN teams t ON d.batting_team_id = t.team_id
        WHERE YEAR(m.match_date) = :season
            AND m.match_date IS NOT NULL
        GROUP BY m.match_id, d.batting_team_id, t.team_id, t.team_name
        ORDER BY innings_total DESC
        LIMIT 1
    ";

    $highestStmt = $pdo->prepare($highestInningsSql);
    $highestStmt->execute(['season' => $season]);
    $highestInningsData = $highestStmt->fetch(PDO::FETCH_ASSOC);

    // 5. Get lowest team innings for the season
    $lowestInningsSql = "
        SELECT
            t.team_name,
            SUM(d.runs_batter) AS innings_total
        FROM matches m
        JOIN deliveries d ON m.match_id = d.match_id
        JOIN teams t ON d.batting_team_id = t.team_id
        WHERE YEAR(m.match_date) = :season
            AND m.match_date IS NOT NULL
        GROUP BY m.match_id, d.batting_team_id, t.team_id, t.team_name
        ORDER BY innings_total ASC
        LIMIT 1
    ";

    $lowestStmt = $pdo->prepare($lowestInningsSql);
    $lowestStmt->execute(['season' => $season]);
    $lowestInningsData = $lowestStmt->fetch(PDO::FETCH_ASSOC);

    // 5. Get total matches and venues used in the season
    $seasonStatsSql = "
        SELECT
            COUNT(DISTINCT m.match_id) AS total_matches,
            COUNT(DISTINCT v.venue_id) AS total_venues
        FROM matches m
        LEFT JOIN venues v ON m.venue_id = v.venue_id
        WHERE YEAR(m.match_date) = :season
            AND m.match_date IS NOT NULL
    ";

    $seasonStmt = $pdo->prepare($seasonStatsSql);
    $seasonStmt->execute(['season' => $season]);
    $seasonStats = $seasonStmt->fetch(PDO::FETCH_ASSOC);
    $seasonStats['total_matches'] = (int) $seasonStats['total_matches'];
    $seasonStats['total_venues'] = (int) $seasonStats['total_venues'];

    // Build highest and lowest innings objects
    $highestInnings = null;
    if ($highestInningsData) {
        $highestInnings = [
            'team' => $highestInningsData['team_name'],
            'runs' => (int) $highestInningsData['innings_total']
        ];
    }

    $lowestInnings = null;
    if ($lowestInningsData) {
        $lowestInnings = [
            'team' => $lowestInningsData['team_name'],
            'runs' => (int) $lowestInningsData['innings_total']
        ];
    }

    echo json_encode([
        'success' => true,
        'season' => $season,
        'winning_team' => $winningTeam,
        'runner_up_team' => $runnerUpTeam,
        'top_batters' => $topBatters,
        'top_bowlers' => $topBowlers,
        'highest_innings' => $highestInnings,
        'lowest_innings' => $lowestInnings,
        'season_stats' => $seasonStats,
        'points_table' => $pointsTable
    ]);

} catch (Exception $e) {
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => $e->getMessage()]);
}
?>
