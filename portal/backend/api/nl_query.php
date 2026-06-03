<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['success' => false, 'error' => 'Only POST requests are allowed.']);
    exit;
}

require_once '../db.php';

$rootEnvPath = dirname(__DIR__, 3) . DIRECTORY_SEPARATOR . '.env';
loadEnvFile($rootEnvPath);

$apiKey = getenv('GROQ_API_KEY') ?: getenv('XAI_API_KEY');
$model = getenv('GROQ_MODEL') ?: 'google/gemma-2-9b-it';

if (!$apiKey) {
    http_response_code(500);
    echo json_encode([
        'success' => false,
        'error' => 'GROQ_API_KEY is not configured in the server environment.'
    ]);
    exit;
}

$rawBody = file_get_contents('php://input');
$payload = json_decode($rawBody, true);
if (!is_array($payload)) {
    $payload = [];
}

$tab = $payload['tab'] ?? ($_POST['tab'] ?? ($_GET['tab'] ?? ''));
$userQuery = trim((string) ($payload['query'] ?? ($_POST['query'] ?? ($_GET['query'] ?? ''))));

if ($userQuery === '') {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'Query text is required.']);
    exit;
}

$allowedTables = ['teams', 'venues', 'players', 'matches', 'deliveries'];
$allowedTablesText = implode(', ', $allowedTables);

$schemaText = <<<SCHEMA
Database schema:
- teams(team_id, team_name)
- venues(venue_id, venue_name, city)
- players(player_id, player_name)
- matches(match_id, match_date, venue_id, team1_id, team2_id, toss_winner_id, toss_decision, match_won_by_id)
- deliveries(delivery_id, match_id, innings, batting_team_id, bowling_team_id, over_num, ball_num, batter_id, bowler_id, runs_batter, runs_extras, is_wicket, wicket_type, player_out_id)

CRITICAL SEMANTIC RULES:
1. TEAM STATISTICS: To calculate a team's total matches or win rate, you MUST join `teams` to `matches` using: `FROM teams t JOIN matches m ON (t.team_id = m.team1_id OR t.team_id = m.team2_id)`.
2. SEASONS/YEARS: Use `YEAR(m.match_date)` to extract the season from the `matches` table.
3. BALL-BY-BALL: The `deliveries` table holds BALL-BY-BALL data. `runs_batter` is for a single delivery. To count 50s/100s, use a subquery/CTE to SUM runs per match_id and batter_id first.
4. PLAYER NAMES: Always use `LIKE '%Name%'` for player names (e.g., `WHERE p.player_name LIKE '%Kohli%'`) as they often contain initials.
5. VENUE NAMES: Use `LIKE '%Venue%'` for venue names to be safe.
SCHEMA;

$systemPrompt = <<<PROMPT
You are a MySQL SQL generator for an IPL analytics dashboard.
Output ONLY a compact JSON object with keys: "sql" and "explanation".
Rules:
1) Generate exactly one read-only SQL query starting with SELECT or WITH.
2) Use ONLY these tables: {$allowedTablesText}.
3) Return useful columns with clear aliases.
4) MySQL dialect only (use YEAR() for seasons).
5) Strictly adhere to the provided schema; do not hallucinate columns like 'season' or 'team_id' in the matches table.

{$schemaText}

EXAMPLES:
User: "At Eden Gardens, which teams have played at least 10 matches and what is their win percentage?"
SQL: SELECT t.team_name, COUNT(m.match_id) AS total_matches, (SUM(CASE WHEN m.match_won_by_id = t.team_id THEN 1 ELSE 0 END) / COUNT(m.match_id)) * 100 AS win_percentage FROM teams t JOIN matches m ON (t.team_id = m.team1_id OR t.team_id = m.team2_id) JOIN venues v ON m.venue_id = v.venue_id WHERE v.venue_name LIKE '%Eden Gardens%' GROUP BY t.team_id, t.team_name HAVING total_matches >= 10 ORDER BY win_percentage DESC

User: "Show toss winners and match winners alignment by season."
SQL: SELECT YEAR(match_date) AS season, COUNT(*) AS total_matches, SUM(CASE WHEN toss_winner_id = match_won_by_id THEN 1 ELSE 0 END) AS toss_and_match_wins, (SUM(CASE WHEN toss_winner_id = match_won_by_id THEN 1 ELSE 0 END) / COUNT(*)) * 100 AS alignment_pct FROM matches GROUP BY season ORDER BY season

User: "Who has the most 50s?"
SQL: SELECT p.player_name, COUNT(CASE WHEN match_runs >= 50 AND match_runs < 100 THEN 1 END) as fifties FROM (SELECT d.match_id, d.batter_id, SUM(d.runs_batter) as match_runs FROM deliveries d GROUP BY d.match_id, d.batter_id) match_scores JOIN players p ON p.player_id = match_scores.batter_id GROUP BY p.player_id ORDER BY fifties DESC LIMIT 10

Context focus: Unified IPL analytics across teams, players, venues, matches, and batter-vs-bowler matchups.
PROMPT;

$userPrompt = "User question: " . $userQuery;

$attempt = 0;
$maxAttempts = 2;
$parsed = null;
$sql = '';
$validationError = null;
$promptForAttempt = $userPrompt;

while ($attempt < $maxAttempts) {
    $llmResponse = callGroq($apiKey, $model, $systemPrompt, $promptForAttempt);
    if (!$llmResponse['success']) {
        http_response_code(500);
        echo json_encode(['success' => false, 'error' => $llmResponse['error']]);
        exit;
    }

    $parsed = parseModelJson($llmResponse['content']);
    if (!$parsed || empty($parsed['sql'])) {
        http_response_code(500);
        echo json_encode(['success' => false, 'error' => 'Could not parse SQL from model response.']);
        exit;
    }

    $sql = normalizeSql($parsed['sql']);
    $validationError = validateSqlSafety($sql, $allowedTables);

    if ($validationError === null) {
        break;
    }

    $attempt++;
    if ($attempt >= $maxAttempts) {
        http_response_code(400);
        echo json_encode([
            'success' => false,
            'error' => $validationError . ' Allowed tables: ' . $allowedTablesText,
            'sql' => $sql
        ]);
        exit;
    }

    $promptForAttempt = $userPrompt . "\n\nThe previous SQL was invalid: " . $validationError . "\nPrevious SQL: " . $sql . "\nGenerate corrected SQL using only these tables: " . $allowedTablesText . ".";
}

if (!preg_match('/\bLIMIT\s+\d+/i', $sql)) {
    $sql .= ' LIMIT 100';
}

try {
    $stmt = $pdo->query($sql);
    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
    $columns = [];

    if (!empty($rows)) {
        $columns = array_keys($rows[0]);
    } else {
        for ($i = 0; $i < $stmt->columnCount(); $i++) {
            $meta = $stmt->getColumnMeta($i);
            if (isset($meta['name'])) {
                $columns[] = $meta['name'];
            }
        }
    }

    // --- PASS 2: DATA SYNTHESIS ---
    $dataSnippet = count($rows) > 0 ? json_encode(array_slice($rows, 0, 15)) : 'No results found.';
    $pass2System = "You are a concise, friendly IPL analytics expert.";
    $pass2User = "The user asked: '$userQuery'.\n\nThe database returned this JSON output: $dataSnippet\n\nBased strictly on this data, write a very brief 1-sentence conversational answer directly addressing the user's question. Output only the plain text response. Do not mention JSON formatting or the SQL query.";

    $pass2Response = callGroq($apiKey, $model, $pass2System, $pass2User);
    $chatAnswer = $pass2Response['success'] ? trim($pass2Response['content']) : 'Here are your results.';

    echo json_encode([
        'success' => true,
        'sql' => $sql,
        'explanation' => $parsed['explanation'] ?? '',
        'chat_response' => $chatAnswer,
        'columns' => $columns,
        'rows' => $rows
    ]);
} catch (\PDOException $e) {
    http_response_code(400);
    echo json_encode([
        'success' => false,
        'error' => 'Generated SQL failed to execute.',
        'sql' => $sql,
        'details' => $e->getMessage()
    ]);
}

function callGroq($apiKey, $model, $systemPrompt, $userPrompt)
{
    $url = 'https://api.groq.com/openai/v1/chat/completions';
    $modelCandidates = buildGroqModelCandidates($model);
    $tried = [];
    $lastError = 'Groq API error.';

    foreach ($modelCandidates as $candidateModel) {
        $tried[] = $candidateModel;

        $payload = [
            'model' => $candidateModel,
            'temperature' => 0,
            'messages' => [
                ['role' => 'system', 'content' => $systemPrompt],
                ['role' => 'user', 'content' => $userPrompt]
            ]
        ];

        $ch = curl_init($url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_HTTPHEADER, [
            'Content-Type: application/json',
            'Authorization: Bearer ' . $apiKey
        ]);
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));

        $raw = curl_exec($ch);
        if ($raw === false) {
            $err = curl_error($ch);
            curl_close($ch);
            return ['success' => false, 'error' => 'xAI request failed: ' . $err];
        }

        $status = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        $decoded = json_decode($raw, true);
        if ($status >= 200 && $status < 300) {
            $content = $decoded['choices'][0]['message']['content'] ?? '';
            if ($content === '') {
                return ['success' => false, 'error' => 'No content returned from Grok model.'];
            }

            return ['success' => true, 'content' => $content, 'model' => $candidateModel];
        }

        $errMsg = extractProviderErrorMessage($decoded, $raw, $status, 'Groq');
        $lastError = $errMsg;

        // Keep trying only if this looks like a model availability issue.
        if (isGroqModelAvailabilityError($errMsg)) {
            continue;
        }

        return ['success' => false, 'error' => $errMsg];
    }

    if (!empty($tried)) {
        $lastError .= ' Tried: ' . implode(', ', $tried) . '. Set GROQ_MODEL in .env to one supported by your key.';
    }

    return ['success' => false, 'error' => $lastError];
}

function buildGroqModelCandidates($rawModel)
{
    $normalized = trim((string) $rawModel);
    $normalized = preg_replace('#^models/#i', '', $normalized);

    $candidates = [$normalized];

    // Practical Gemma model fallbacks on Groq.
    $fallbacks = [
        'google/gemma-2-9b-it',
        'google/gemma-2-27b-it',
        'gemma2-9b-it',
        'gemma-2-9b-it',
        'gemma-2-27b-it',
        'gemma-7b-it'
    ];

    foreach ($fallbacks as $fallback) {
        $candidates[] = $fallback;
    }

    $clean = [];
    foreach ($candidates as $candidate) {
        if ($candidate !== '' && !in_array($candidate, $clean, true)) {
            $clean[] = $candidate;
        }
    }

    return $clean;
}

function isGroqModelAvailabilityError($message)
{
    $msg = strtolower((string) $message);
    return str_contains($msg, 'not found') ||
        str_contains($msg, 'does not exist') ||
        str_contains($msg, 'invalid model') ||
        str_contains($msg, 'not supported') ||
        str_contains($msg, 'decommissioned') ||
        str_contains($msg, 'model_decommissioned') ||
        str_contains($msg, 'method not found');
}

function parseModelJson($text)
{
    $decoded = json_decode($text, true);
    if (is_array($decoded)) {
        return $decoded;
    }

    if (preg_match('/\{.*\}/s', $text, $match)) {
        $decoded = json_decode($match[0], true);
        if (is_array($decoded)) {
            return $decoded;
        }
    }

    return null;
}

function normalizeSql($sql)
{
    $sql = trim($sql);
    $sql = preg_replace('/;+\s*$/', '', $sql);
    return $sql;
}

function validateSqlSafety($sql, $allowedTables)
{
    if (!preg_match('/^(SELECT|WITH)\b/i', ltrim($sql))) {
        return 'Only SELECT/CTE queries are allowed.';
    }

    if (preg_match('/\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE|GRANT|REVOKE|CALL|SET|USE|SHOW|DESCRIBE|EXPLAIN)\b/i', $sql)) {
        return 'Unsafe SQL was generated. Please rephrase your question.';
    }

    // Extract CTE aliases so they are not treated as physical tables.
    preg_match_all('/(?:\bWITH|,)\s*`?([a-zA-Z_][a-zA-Z0-9_]*)`?\s+AS\s*\(/i', $sql, $cteMatches);
    $cteNames = array_map('strtolower', array_unique($cteMatches[1] ?? []));

    preg_match_all('/\b(?:FROM|JOIN)\s+`?([a-zA-Z_][a-zA-Z0-9_]*)`?/i', $sql, $matches);
    $tablesInQuery = array_unique($matches[1] ?? []);

    foreach ($tablesInQuery as $table) {
        if (in_array(strtolower($table), $cteNames, true)) {
            continue;
        }

        if (!in_array(strtolower($table), array_map('strtolower', $allowedTables), true)) {
            return 'Query referenced a table outside allowed schema: ' . $table;
        }
    }

    return null;
}

function loadEnvFile($path)
{
    if (!is_readable($path)) {
        return;
    }

    $lines = file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    if ($lines === false) {
        return;
    }

    foreach ($lines as $line) {
        $trimmed = trim($line);
        if ($trimmed === '' || str_starts_with($trimmed, '#')) {
            continue;
        }

        $parts = explode('=', $trimmed, 2);
        if (count($parts) !== 2) {
            continue;
        }

        $key = trim($parts[0]);
        $value = trim($parts[1]);

        if ($key === '') {
            continue;
        }

        if ((str_starts_with($value, '"') && str_ends_with($value, '"')) || (str_starts_with($value, "'") && str_ends_with($value, "'"))) {
            $value = substr($value, 1, -1);
        }

        putenv($key . '=' . $value);
        $_ENV[$key] = $value;
        $_SERVER[$key] = $value;
    }
}

function extractProviderErrorMessage($decoded, $raw, $status, $providerName)
{
    if (is_array($decoded)) {
        if (isset($decoded['error']['message']) && is_string($decoded['error']['message']) && $decoded['error']['message'] !== '') {
            return $decoded['error']['message'];
        }

        if (isset($decoded['error']) && is_string($decoded['error']) && $decoded['error'] !== '') {
            return $decoded['error'];
        }

        if (isset($decoded['message']) && is_string($decoded['message']) && $decoded['message'] !== '') {
            return $decoded['message'];
        }
    }

    $rawSnippet = trim((string) $raw);
    if ($rawSnippet !== '') {
        $rawSnippet = preg_replace('/\s+/', ' ', $rawSnippet);
        $rawSnippet = substr($rawSnippet, 0, 260);
        return $providerName . ' API HTTP ' . $status . ': ' . $rawSnippet;
    }

    return $providerName . ' API HTTP ' . $status . ': Unknown error.';
}
?>