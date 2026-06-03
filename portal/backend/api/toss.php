<?php
header('Content-Type: application/json');
require_once '../db.php';

$venue_id = $_GET['venue_id'] ?? 'all';
$whereClause = "";
$params = [];

if ($venue_id !== 'all') {
    $whereClause = " AND venue_id = :venue_id";
    $params['venue_id'] = $venue_id;
}

$sql = "
SELECT 
    SUM(CASE 
        WHEN (toss_decision='bat' AND toss_winner_id = match_won_by_id) OR (toss_decision='field' AND toss_winner_id != match_won_by_id) THEN 1 
        ELSE 0 
    END) as bat_first_wins,
    SUM(CASE 
        WHEN (toss_decision='field' AND toss_winner_id = match_won_by_id) OR (toss_decision='bat' AND toss_winner_id != match_won_by_id) THEN 1 
        ELSE 0 
    END) as chase_wins
FROM matches
WHERE match_won_by_id IS NOT NULL $whereClause
";

try {
    $stmt = $pdo->prepare($sql);
    $stmt->execute($params);
    $stats = $stmt->fetch(PDO::FETCH_ASSOC);

    // cast to int
    $stats['bat_first_wins'] = (int) $stats['bat_first_wins'];
    $stats['chase_wins'] = (int) $stats['chase_wins'];

    echo json_encode(['success' => true, 'data' => $stats]);
} catch (\PDOException $e) {
    echo json_encode(['success' => false, 'error' => $e->getMessage()]);
}
?>