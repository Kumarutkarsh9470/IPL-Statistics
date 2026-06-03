<?php
header('Content-Type: application/json');
require_once '../db.php';

function normalizeVenueToken($value)
{
    $value = strtolower(trim((string) $value));
    $value = str_replace(['.', '\'', '-', ','], ' ', $value);
    $value = preg_replace('/[^a-z0-9\s]/', ' ', $value);
    $value = preg_replace('/\s+/', ' ', $value);
    return trim($value);
}

function canonicalizeVenue($venueName, $city)
{
    $nameToken = normalizeVenueToken($venueName);

    if (strpos($nameToken, 'm chinnaswamy') !== false) {
        return ['M Chinnaswamy Stadium, Bengaluru', 'Bengaluru'];
    }

    if (strpos($nameToken, 'dy patil') !== false) {
        return ['Dr DY Patil Sports Academy, Mumbai', 'Mumbai'];
    }

    if (strpos($nameToken, 'sharjah') !== false) {
        return ['Sharjah Cricket Stadium, Sharjah', 'Sharjah'];
    }

    if (strpos($nameToken, 'dubai international cricket stadium') !== false) {
        return ['Dubai International Cricket Stadium, Dubai', 'Dubai'];
    }

    if (
        strpos($nameToken, 'maharaja yadavindra singh') !== false ||
        strpos($nameToken, 'mullanpur') !== false
    ) {
        return ['Maharaja Yadavindra Singh International Cricket Stadium, Mullanpur', 'Mohali'];
    }

    $safeName = trim((string) $venueName);
    $safeCity = trim((string) $city);
    return [$safeName, $safeCity];
}

try {
    $stmt = $pdo->query(
        'SELECT v.venue_id, v.venue_name, v.city, COUNT(m.match_id) AS match_count
         FROM venues v
         LEFT JOIN matches m ON m.venue_id = v.venue_id
         WHERE v.venue_name IS NOT NULL AND TRIM(v.venue_name) <> ""
         GROUP BY v.venue_id, v.venue_name, v.city
         ORDER BY v.venue_name, v.city'
    );

    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
    $canonicalVenues = [];

    foreach ($rows as $row) {
        $venueId = (int) $row['venue_id'];
        $matchCount = (int) ($row['match_count'] ?? 0);
        list($canonicalName, $canonicalCity) = canonicalizeVenue($row['venue_name'] ?? '', $row['city'] ?? '');
        $dedupeKey = normalizeVenueToken($canonicalName) . '|' . normalizeVenueToken($canonicalCity);

        if (!isset($canonicalVenues[$dedupeKey])) {
            $canonicalVenues[$dedupeKey] = [
                'venue_id' => $venueId,
                'venue_name' => $canonicalName,
                'city' => $canonicalCity,
                '_match_count' => $matchCount,
            ];
            continue;
        }

        // Prefer the venue_id that has more historical matches.
        if ($matchCount > $canonicalVenues[$dedupeKey]['_match_count']) {
            $canonicalVenues[$dedupeKey]['venue_id'] = $venueId;
            $canonicalVenues[$dedupeKey]['_match_count'] = $matchCount;
        }
    }

    $venues = array_values(array_map(function ($item) {
        unset($item['_match_count']);
        return $item;
    }, $canonicalVenues));

    usort($venues, function ($a, $b) {
        return strcasecmp($a['venue_name'], $b['venue_name']);
    });

    echo json_encode(['success' => true, 'data' => $venues]);
} catch (\PDOException $e) {
    header('HTTP/1.1 500 Internal Server Error');
    echo json_encode(['success' => false, 'error' => 'Query failed']);
}
?>