<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

require_once '../db.php';

function normalizeVenueName($value)
{
    $value = strtolower(trim((string) $value));
    if ($value === '') {
        return '';
    }

    // Drop trailing city fragments such as ", Delhi" used by some sources.
    $value = preg_replace('/,.*$/', '', $value);
    $value = str_replace(['.', '\'', '-'], ' ', $value);
    $value = preg_replace('/[^a-z0-9\s]/', ' ', $value);
    $value = preg_replace('/\s+/', ' ', $value);
    return trim($value);
}

function compactVenueKey($value)
{
    $normalized = normalizeVenueName($value);
    if ($normalized === '') {
        return '';
    }

    // Remove generic words to make matching robust across naming variants.
    $normalized = preg_replace(
        '/\b(stadium|cricket|ground|association|international|sports|academy|complex|park|the)\b/',
        ' ',
        $normalized
    );
    $normalized = preg_replace('/\s+/', ' ', $normalized);
    return trim($normalized);
}

function resolveBoundaryDistanceFallback($venueName)
{
    $boundaryByVenue = [
        'Arun Jaitley Stadium' => 69.0,
        'Barabati Stadium' => 71.0,
        'Barsapara Cricket Stadium' => 67.0,
        'Ekana Cricket Stadium' => 70.0,
        'Brabourne Stadium' => 66.0,
        'Buffalo Park' => 73.0,
        'De Beers Diamond Oval' => 74.0,
        'Dr DY Patil Sports Academy' => 68.0,
        'Dr. Y.S. Rajasekhara Reddy Stadium' => 71.0,
        'Dubai International Cricket Stadium' => 73.0,
        'Eden Gardens' => 72.0,
        'Green Park' => 70.0,
        'HPCA Stadium' => 67.0,
        'Holkar Cricket Stadium' => 65.0,
        'JSCA International Stadium' => 73.0,
        'Kingsmead' => 73.0,
        'M Chinnaswamy Stadium' => 63.0,
        'MA Chidambaram Stadium' => 70.0,
        'Maharaja Yadavindra Singh Stadium' => 66.0,
        'Maharashtra Cricket Association Stadium' => 71.0,
        'Narendra Modi Stadium' => 75.0,
        'Nehru Stadium' => 72.0,
        'New Wanderers Stadium' => 77.0,
        'Newlands' => 76.0,
        'OUTsurance Oval' => 74.0,
        'PCA IS Bindra Stadium' => 72.0,
        'Rajiv Gandhi International Stadium' => 70.0,
        'Saurashtra Cricket Association Stadium' => 72.0,
        'Sawai Mansingh Stadium' => 68.0,
        'Shaheed Veer Narayan Singh Stadium' => 73.0,
        'Sharjah Cricket Stadium' => 62.0,
        'Sheikh Zayed Stadium' => 73.0,
        'St George\'s Park' => 74.0,
        'SuperSport Park' => 72.0,
        'Vidarbha Cricket Association Stadium' => 82.0,
        'Wankhede Stadium' => 67.0,
        'Zayed Cricket Stadium' => 73.0,
    ];

    $exact = [];
    $compact = [];
    foreach ($boundaryByVenue as $name => $distance) {
        $exact[normalizeVenueName($name)] = $distance;
        $compact[compactVenueKey($name)] = $distance;
    }

    $venueExactKey = normalizeVenueName($venueName);
    if (isset($exact[$venueExactKey])) {
        return $exact[$venueExactKey];
    }

    $venueCompactKey = compactVenueKey($venueName);
    if ($venueCompactKey !== '' && isset($compact[$venueCompactKey])) {
        return $compact[$venueCompactKey];
    }

    // Fuzzy fallback for near-matches (e.g., extra honorifics or abbreviations).
    foreach ($compact as $key => $distance) {
        if ($key !== '' && ($venueCompactKey !== '') && (strpos($venueCompactKey, $key) !== false || strpos($key, $venueCompactKey) !== false)) {
            return $distance;
        }
    }

    return null;
}

$venueId = isset($_GET['venue_id']) ? (int) $_GET['venue_id'] : 0;
if ($venueId <= 0) {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'venue_id is required']);
    exit;
}

try {
    $venueStmt = $pdo->prepare(
        'SELECT venue_id, venue_name, city FROM venues WHERE venue_id = :venue_id'
    );
    $venueStmt->execute(['venue_id' => $venueId]);
    $venue = $venueStmt->fetch(PDO::FETCH_ASSOC);

    if (!$venue) {
        http_response_code(404);
        echo json_encode(['success' => false, 'error' => 'Venue not found']);
        exit;
    }

    $overviewStmt = $pdo->prepare(
        "SELECT
            ROUND(AVG(fi.first_innings_score), 2) AS avg_first_innings_score,
            COUNT(fi.match_id) AS total_matches
        FROM (
            SELECT d.match_id, SUM(d.runs_batter) AS first_innings_score
            FROM deliveries d
            JOIN matches m ON m.match_id = d.match_id
            WHERE m.venue_id = :venue_id AND d.innings = 1
            GROUP BY d.match_id
        ) fi"
    );
    $overviewStmt->execute(['venue_id' => $venueId]);
    $overview = $overviewStmt->fetch(PDO::FETCH_ASSOC) ?: [];

    $homeTeamStmt = $pdo->prepare(
        "SELECT
            t.team_id,
            t.team_name,
            COUNT(*) AS played,
            SUM(CASE WHEN m.match_won_by_id = t.team_id THEN 1 ELSE 0 END) AS wins
        FROM matches m
        JOIN teams t ON (m.team1_id = t.team_id OR m.team2_id = t.team_id)
        WHERE m.venue_id = :venue_id
        GROUP BY t.team_id, t.team_name
        ORDER BY played DESC, wins DESC, t.team_name ASC
        LIMIT 1"
    );
    $homeTeamStmt->execute(['venue_id' => $venueId]);
    $homeTeam = $homeTeamStmt->fetch(PDO::FETCH_ASSOC) ?: [
        'team_id' => null,
        'team_name' => null,
        'played' => 0,
        'wins' => 0
    ];

    $played = (int) ($homeTeam['played'] ?? 0);
    $wins = (int) ($homeTeam['wins'] ?? 0);
    $homeTeam['played'] = $played;
    $homeTeam['wins'] = $wins;
    $homeTeam['win_pct'] = $played > 0 ? round(($wins / $played) * 100.0, 2) : 0.0;

    $recentStmt = $pdo->prepare(
        "SELECT
            m.match_id,
            DATE(m.match_date) AS match_date,
            t1.team_name AS team1_name,
            t2.team_name AS team2_name,
            tw.team_name AS winner_name,
            fi.first_innings_score
        FROM matches m
        LEFT JOIN teams t1 ON m.team1_id = t1.team_id
        LEFT JOIN teams t2 ON m.team2_id = t2.team_id
        LEFT JOIN teams tw ON m.match_won_by_id = tw.team_id
        LEFT JOIN (
            SELECT d.match_id, SUM(d.runs_batter) AS first_innings_score
            FROM deliveries d
            WHERE d.innings = 1
            GROUP BY d.match_id
        ) fi ON fi.match_id = m.match_id
        WHERE m.venue_id = :venue_id
        ORDER BY m.match_date DESC, m.match_id DESC
        LIMIT 5"
    );
    $recentStmt->execute(['venue_id' => $venueId]);
    $recentMatches = $recentStmt->fetchAll(PDO::FETCH_ASSOC);

    $conditionsStmt = $pdo->prepare(
        "SELECT season, boundary_distance_m, outfield_speed
        FROM venue_conditions
        WHERE venue_id = :venue_id
        ORDER BY season DESC, venue_condition_id DESC
        LIMIT 1"
    );
    $conditionsStmt->execute(['venue_id' => $venueId]);
    $conditions = $conditionsStmt->fetch(PDO::FETCH_ASSOC) ?: [
        'season' => null,
        'boundary_distance_m' => null,
        'outfield_speed' => null
    ];

    if (!isset($conditions['boundary_distance_m']) || $conditions['boundary_distance_m'] === null || $conditions['boundary_distance_m'] === '') {
        $fallbackBoundary = resolveBoundaryDistanceFallback($venue['venue_name'] ?? '');
        if ($fallbackBoundary !== null) {
            $conditions['boundary_distance_m'] = $fallbackBoundary;
        }
    }

    echo json_encode([
        'success' => true,
        'venue' => [
            'venue_id' => (int) $venue['venue_id'],
            'venue_name' => $venue['venue_name'],
            'city' => $venue['city'],
        ],
        'overview' => [
            'avg_first_innings_score' => (float) ($overview['avg_first_innings_score'] ?? 0),
            'total_matches' => (int) ($overview['total_matches'] ?? 0),
        ],
        'home_team' => [
            'team_id' => isset($homeTeam['team_id']) ? (int) $homeTeam['team_id'] : null,
            'team_name' => $homeTeam['team_name'],
            'played' => $homeTeam['played'],
            'wins' => $homeTeam['wins'],
            'win_pct' => (float) $homeTeam['win_pct'],
        ],
        'conditions' => [
            'season' => isset($conditions['season']) ? (int) $conditions['season'] : null,
            'boundary_distance_m' => isset($conditions['boundary_distance_m']) ? (float) $conditions['boundary_distance_m'] : null,
            'outfield_speed' => isset($conditions['outfield_speed']) ? (float) $conditions['outfield_speed'] : null,
        ],
        'recent_matches' => array_map(function ($row) {
            return [
                'match_id' => (int) $row['match_id'],
                'match_date' => $row['match_date'],
                'team1_name' => $row['team1_name'],
                'team2_name' => $row['team2_name'],
                'winner_name' => $row['winner_name'],
                'first_innings_score' => isset($row['first_innings_score']) ? (int) $row['first_innings_score'] : null,
            ];
        }, $recentMatches),
    ]);
} catch (\PDOException $e) {
    http_response_code(500);
    echo json_encode(['success' => false, 'error' => 'Failed to fetch venue insights']);
}
