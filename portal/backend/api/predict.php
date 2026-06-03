<?php
header('Content-Type: application/json');
$inputJSON = file_get_contents('php://input');
$input = json_decode($inputJSON, true);

if (!$input) {
    echo json_encode(["success" => false, "error" => "Invalid JSON payload"]);
    exit;
}
$task = $input['task'] ?? '';
if (!in_array($task, ['match_outcome', 'score_prediction', 'player_performance'])) {
    echo json_encode(["success" => false, "error" => "Invalid or missing task"]);
    exit;
}
$ds = DIRECTORY_SEPARATOR;
$baseDir = realpath(__DIR__ . "$ds..$ds..$ds..$ds");
$predictScript = escapeshellarg($baseDir . "{$ds}ml{$ds}predict.py");
$cmd = "python $predictScript --task " . escapeshellarg($task);
if ($task === 'match_outcome') {
    $cmd .= " --team1 " . escapeshellarg($input['team1'] ?? '');
    $cmd .= " --team2 " . escapeshellarg($input['team2'] ?? '');
    $cmd .= " --venue " . escapeshellarg($input['venue'] ?? '');
    $cmd .= " --toss_winner " . escapeshellarg($input['toss_winner'] ?? '');
    $cmd .= " --toss_decision " . escapeshellarg($input['toss_decision'] ?? '');
} elseif ($task === 'score_prediction') {
    $cmd .= " --team1 " . escapeshellarg($input['team1'] ?? '');
    $cmd .= " --team2 " . escapeshellarg($input['team2'] ?? '');
    $cmd .= " --venue " . escapeshellarg($input['venue'] ?? '');
    $cmd .= " --innings " . escapeshellarg($input['innings'] ?? 1);
    $cmd .= " --current_score " . escapeshellarg($input['current_score'] ?? 0);
    $cmd .= " --wickets " . escapeshellarg($input['wickets'] ?? 0);
    $cmd .= " --overs_remaining " . escapeshellarg($input['overs_remaining'] ?? 20);
} elseif ($task === 'player_performance') {
    $cmd .= " --batter " . escapeshellarg($input['batter'] ?? '');
    $cmd .= " --team2 " . escapeshellarg($input['team2'] ?? '');
    $cmd .= " --venue " . escapeshellarg($input['venue'] ?? '');
}
$output = shell_exec($cmd . " 2>&1");
if ($output === null) {
    echo json_encode(["success" => false, "error" => "Failed to execute python inference script", "cmd" => $cmd]);
    exit;
}
$lines = explode("\n", trim($output));
$lastLine = end($lines);
$jsonOut = json_decode($lastLine, true);
if ($jsonOut) {
    echo $lastLine;
} else {
    echo json_encode(["success" => false, "error" => "Invalid output from ML model", "raw_output" => $output]);
}
