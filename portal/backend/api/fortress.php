<?php
header('Content-Type: application/json');
require_once '../db.php';

$sql = "
SELECT 
    m.venue_id, v.venue_name, 
    t.team_id, t.team_name,
    COUNT(m.match_id) as matches_played,
    SUM(CASE WHEN m.match_won_by_id = t.team_id THEN 1 ELSE 0 END) as matches_won
FROM matches m
JOIN venues v ON m.venue_id = v.venue_id
JOIN teams t ON (m.team1_id = t.team_id OR m.team2_id = t.team_id)
WHERE m.match_won_by_id IS NOT NULL
GROUP BY m.venue_id, v.venue_name, t.team_id, t.team_name
HAVING matches_played >= 10
ORDER BY v.venue_name, t.team_name;
";

try {
    $stmt = $pdo->query($sql);
    $results = $stmt->fetchAll(PDO::FETCH_ASSOC);

    // Convert to integers
    foreach ($results as &$r) {
        $r['matches_played'] = (int) $r['matches_played'];
        $r['matches_won'] = (int) $r['matches_won'];
    }

    echo json_encode(['success' => true, 'data' => $results]);
} catch (\PDOException $e) {
    echo json_encode(['success' => false, 'error' => $e->getMessage()]);
}
?>