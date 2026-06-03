<?php
header('Content-Type: application/json');
require_once '../db.php';

$batter_id = $_GET['batter_id'] ?? null;
$bowler_id = $_GET['bowler_id'] ?? null;

if (!$batter_id || !$bowler_id) {
    echo json_encode(['success' => false, 'error' => 'Missing batter_id or bowler_id']);
    exit;
}

$sql = "
SELECT 
    COUNT(delivery_id) as balls_faced,
    SUM(runs_batter) as total_runs,
    SUM(CASE WHEN runs_batter = 4 THEN 1 ELSE 0 END) as fours,
    SUM(CASE WHEN runs_batter = 6 THEN 1 ELSE 0 END) as sixes,
    SUM(CASE WHEN is_wicket = 1 AND player_out_id = :batter_id THEN 1 ELSE 0 END) as dismissals
FROM deliveries
WHERE batter_id = :batter_idx AND bowler_id = :bowler_id
";

try {
    $batterStyleStmt = $pdo->prepare(
        "SELECT batting_style FROM players WHERE player_id = :batter_id LIMIT 1"
    );
    $batterStyleStmt->execute(['batter_id' => $batter_id]);
    $batterStyleRow = $batterStyleStmt->fetch(PDO::FETCH_ASSOC) ?: ['batting_style' => null];

    $bowlerStyleStmt = $pdo->prepare(
        "SELECT bowling_arm, bowling_type FROM players WHERE player_id = :bowler_id LIMIT 1"
    );
    $bowlerStyleStmt->execute(['bowler_id' => $bowler_id]);
    $bowlerStyleRow = $bowlerStyleStmt->fetch(PDO::FETCH_ASSOC) ?: ['bowling_arm' => null, 'bowling_type' => null];

    $stmt = $pdo->prepare($sql);
    $stmt->execute([
        'batter_id' => $batter_id,
        'batter_idx' => $batter_id,
        'bowler_id' => $bowler_id
    ]);
    $stats = $stmt->fetch(PDO::FETCH_ASSOC);

    $stats['balls_faced'] = (int) $stats['balls_faced'];
    $stats['total_runs'] = (int) $stats['total_runs'];
    $stats['fours'] = (int) $stats['fours'];
    $stats['sixes'] = (int) $stats['sixes'];
    $stats['dismissals'] = (int) $stats['dismissals'];
    $stats['strike_rate'] = ($stats['balls_faced'] > 0) ? round(($stats['total_runs'] / $stats['balls_faced']) * 100, 2) : 0;
    $stats['batter_batting_style'] = $batterStyleRow['batting_style'] ?? null;
    $stats['bowler_bowling_arm'] = $bowlerStyleRow['bowling_arm'] ?? null;
    $stats['bowler_bowling_type'] = $bowlerStyleRow['bowling_type'] ?? null;

    echo json_encode(['success' => true, 'data' => $stats]);
} catch (\PDOException $e) {
    header('HTTP/1.1 500 Internal Server Error');
    echo json_encode(['success' => false, 'error' => 'Query failed']);
}
?>