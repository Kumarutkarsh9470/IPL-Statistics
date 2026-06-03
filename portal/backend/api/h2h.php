<?php
header('Content-Type: application/json');
require_once '../db.php';

$team_a = $_GET['team_a'] ?? null;
$team_b = $_GET['team_b'] ?? null;

if (!$team_a || !$team_b) {
    echo json_encode(['success' => false, 'error' => 'Provide team_a and team_b']);
    exit;
}

$sql = "
SELECT 
    COUNT(match_id) as total_matches,
    SUM(CASE WHEN match_won_by_id = :team_a THEN 1 ELSE 0 END) as team_a_wins,
    SUM(CASE WHEN match_won_by_id = :team_b THEN 1 ELSE 0 END) as team_b_wins,
    SUM(CASE WHEN match_won_by_id IS NULL THEN 1 ELSE 0 END) as no_result
FROM matches
WHERE (team1_id = :team_ax AND team2_id = :team_bx) OR (team1_id = :team_by AND team2_id = :team_ay)
";

try {
    $stmt = $pdo->prepare($sql);
    $stmt->execute([
        'team_a' => $team_a,
        'team_b' => $team_b,
        'team_ax' => $team_a,
        'team_bx' => $team_b,
        'team_ay' => $team_a,
        'team_by' => $team_b
    ]);
    $stats = $stmt->fetch(PDO::FETCH_ASSOC);

    $stats['total_matches'] = (int) $stats['total_matches'];
    $stats['team_a_wins'] = (int) $stats['team_a_wins'];
    $stats['team_b_wins'] = (int) $stats['team_b_wins'];
    $stats['no_result'] = (int) $stats['no_result'];

    echo json_encode(['success' => true, 'data' => $stats]);
} catch (\PDOException $e) {
    echo json_encode(['success' => false, 'error' => $e->getMessage()]);
}
?>