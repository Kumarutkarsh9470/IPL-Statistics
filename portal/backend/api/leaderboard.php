<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

require_once '../db.php';

$season = $_GET['season'] ?? 'all';
$team_id = $_GET['team_id'] ?? 'all';

$params = [];
$subParams = [];
$whereBat = "";
$whereBowl = "";
$subWhereBat = ""; // For fifty/century subquery

if ($season !== 'all') {
    $whereBat .= " AND YEAR(m.match_date) = :season";
    $whereBowl .= " AND YEAR(m.match_date) = :season";
    $subWhereBat .= " AND YEAR(m2.match_date) = :sub_season";
    $params['season'] = $season;
    $subParams['sub_season'] = $season;
}

if ($team_id !== 'all') {
    $whereBat .= " AND d.batting_team_id = :team_id";
    $whereBowl .= " AND d.bowling_team_id = :team_id";
    $params['team_id'] = $team_id;
    $subParams['sub_team_id'] = $team_id;
}

// 1. Fetch Batting Stats
$sqlBat = "
SELECT 
    b.player_id,
    b.player_name,
    b.batting_style,
    b.bowling_arm,
    b.bowling_type,
    COUNT(DISTINCT m.match_id) as matches,
    SUM(d.runs_batter) as total_runs,
    SUM(CASE WHEN d.runs_batter = 4 THEN 1 ELSE 0 END) as fours,
    SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
    COUNT(d.delivery_id) as balls_faced,
    SUM(CASE WHEN d.player_out_id = b.player_id THEN 1 ELSE 0 END) as times_out,
    IFNULL(ms.fifties, 0) as fifties,
    IFNULL(ms.centuries, 0) as centuries
FROM players b
JOIN deliveries d ON b.player_id = d.batter_id
JOIN matches m ON d.match_id = m.match_id
LEFT JOIN (
    SELECT 
        match_scores.batter_id,
        SUM(CASE WHEN match_runs >= 50 AND match_runs < 100 THEN 1 ELSE 0 END) as fifties,
        SUM(CASE WHEN match_runs >= 100 THEN 1 ELSE 0 END) as centuries
    FROM (
        SELECT d2.match_id, d2.batter_id, SUM(d2.runs_batter) as match_runs
        FROM deliveries d2
        JOIN matches m2 ON d2.match_id = m2.match_id
        WHERE 1=1 $subWhereBat
        GROUP BY d2.match_id, d2.batter_id
    ) match_scores
    GROUP BY match_scores.batter_id
) ms ON b.player_id = ms.batter_id
WHERE 1=1 $whereBat
GROUP BY b.player_id, b.player_name, b.batting_style, b.bowling_arm, b.bowling_type, ms.fifties, ms.centuries
";

// 2. Fetch Bowling Stats
$sqlBowl = "
SELECT 
    p.player_id,
    p.player_name,
    p.batting_style,
    p.bowling_arm,
    p.bowling_type,
    SUM(CASE WHEN d.is_wicket = 1 AND d.wicket_type != 'run out' THEN 1 ELSE 0 END) as wickets,
    SUM(d.runs_batter + d.runs_extras) as runs_conceded,
    COUNT(d.delivery_id) as balls_bowled
FROM players p
JOIN deliveries d ON p.player_id = d.bowler_id
JOIN matches m ON d.match_id = m.match_id
WHERE 1=1 $whereBowl
GROUP BY p.player_id, p.player_name, p.batting_style, p.bowling_arm, p.bowling_type
";

try {
    $stmtBat = $pdo->prepare($sqlBat);
    $allBatParams = array_merge($params, $subParams);
    $stmtBat->execute($allBatParams);
    $batters = $stmtBat->fetchAll(PDO::FETCH_ASSOC);

    $stmtBowl = $pdo->prepare($sqlBowl);
    $stmtBowl->execute($params);
    $bowlers = $stmtBowl->fetchAll(PDO::FETCH_ASSOC);

    // Merge logics securely
    $playersHash = [];

    foreach ($batters as $b) {
        $id = $b['player_id'];
        $playersHash[$id] = [
            'player_id' => $id,
            'player_name' => $b['player_name'],
            'batting_style' => $b['batting_style'],
            'bowling_arm' => $b['bowling_arm'],
            'bowling_type' => $b['bowling_type'],
            'matches' => (int) $b['matches'],
            'total_runs' => (int) $b['total_runs'],
            'fours' => (int) $b['fours'],
            'sixes' => (int) $b['sixes'],
            'balls_faced' => (int) $b['balls_faced'],
            'times_out' => (int) $b['times_out'],
            'fifties' => (int) $b['fifties'],
            'centuries' => (int) $b['centuries'],
            'average' => ($b['times_out'] > 0) ? round($b['total_runs'] / $b['times_out'], 2) : (int) $b['total_runs'],
            'strikeRate' => ($b['balls_faced'] > 0) ? round(($b['total_runs'] / $b['balls_faced']) * 100, 2) : 0,
            'wickets' => 0,
            'runs_conceded' => 0,
            'balls_bowled' => 0,
            'economy' => 0.0
        ];
    }

    foreach ($bowlers as $b) {
        $id = $b['player_id'];
        if (!isset($playersHash[$id])) {
            $playersHash[$id] = [
                'player_id' => $id,
                'player_name' => $b['player_name'],
                'batting_style' => $b['batting_style'],
                'bowling_arm' => $b['bowling_arm'],
                'bowling_type' => $b['bowling_type'],
                'matches' => 0,
                'total_runs' => 0,
                'fours' => 0,
                'sixes' => 0,
                'balls_faced' => 0,
                'times_out' => 0,
                'fifties' => 0,
                'centuries' => 0,
                'average' => 0,
                'strikeRate' => 0,
            ];
        }

        if (empty($playersHash[$id]['batting_style']) && !empty($b['batting_style'])) {
            $playersHash[$id]['batting_style'] = $b['batting_style'];
        }
        if (empty($playersHash[$id]['bowling_arm']) && !empty($b['bowling_arm'])) {
            $playersHash[$id]['bowling_arm'] = $b['bowling_arm'];
        }
        if (empty($playersHash[$id]['bowling_type']) && !empty($b['bowling_type'])) {
            $playersHash[$id]['bowling_type'] = $b['bowling_type'];
        }

        $playersHash[$id]['wickets'] = (int) $b['wickets'];
        $playersHash[$id]['runs_conceded'] = (int) $b['runs_conceded'];
        $playersHash[$id]['balls_bowled'] = (int) $b['balls_bowled'];

        $overs = $b['balls_bowled'] / 6.0;
        $playersHash[$id]['economy'] = ($overs > 0) ? round($b['runs_conceded'] / $overs, 2) : 0;
    }

    $finalArray = array_values($playersHash);

    echo json_encode(['success' => true, 'data' => $finalArray]);
} catch (\PDOException $e) {
    header('HTTP/1.1 500 Internal Server Error');
    echo json_encode(['success' => false, 'error' => 'Query failed: ' . $e->getMessage()]);
}
?>