<?php
header('Content-Type: application/json');

// Enable CORS if necessary for local testing, though they will be on same domain
header('Access-Control-Allow-Origin: *');

require_once '../db.php';

try {
    $stmt = $pdo->query('SELECT team_id, team_name FROM teams ORDER BY team_name');
    $teams = $stmt->fetchAll();
    echo json_encode(['success' => true, 'data' => $teams]);
} catch (\PDOException $e) {
    header('HTTP/1.1 500 Internal Server Error');
    echo json_encode(['success' => false, 'error' => 'Query failed']);
}
?>