<?php
/**
 * One-off: writes the PHP catalog and demo cases to content/*.json for the Python site and game clients.
 *   php scripts/export_content.php
 * The 20 cases from database/new_cases_20.sql are decoded from their hex JSON as batch 3.
 */
declare(strict_types=1);

define('APP_ROOT', dirname(__DIR__));
require APP_ROOT . '/includes/catalog.php';
require APP_ROOT . '/includes/auth.php';
require APP_ROOT . '/includes/judge.php';

$out = APP_ROOT . '/content';
@mkdir($out . '/cases', 0777, true);
$json = static fn($v): string => json_encode($v, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n";

file_put_contents($out . '/catalog.json', $json([
    'categories'      => CATEGORIES,
    'situation_types' => SITUATION_TYPES,
    'metrics'         => METRICS,
    'metric_step'     => METRIC_STEP,
    'worlds'          => WORLDS,
    'checklist'       => CHECKLIST,
    'levels'          => LEVELS,
    'idea_min_words'  => IDEA_MIN_WORDS,
    'max_decisions'   => MAX_DECISIONS,
    'statuses'        => STATUSES,
    'roles'           => ROLES,
    'roadmap'         => ROADMAP,
    'judge'           => [
        'min_verdicts' => JUDGE_MIN_VERDICTS,
        'neutral'      => JUDGE_NEUTRAL,
        'min_relevant' => JUDGE_MIN_RELEVANT,
        'archetypes'   => JUDGE_ARCHETYPES,
    ],
]));

$n = 0;
$write = static function (int $batch, array $s) use (&$n, $out, $json): void {
    $n++;
    $s = ['batch' => $batch, 'status' => $s['status'] ?? 'approved'] + $s;
    file_put_contents(sprintf('%s/cases/%03d.json', $out, $n), $json($s));
};

foreach (require APP_ROOT . '/includes/seed.php' as $batch => $cases) {
    foreach ($cases as $s) {
        $write($batch, $s);
    }
}

$sql = (string)file_get_contents(APP_ROOT . '/database/new_cases_20.sql');
preg_match_all("/SELECT '([a-z]+)', '([a-z]+)', '((?:[^']|'')+)', '((?:[^']|'')+)',.*?'(approved|pending)',\s*CONVERT\(X'([0-9A-F]+)'/s", $sql, $m, PREG_SET_ORDER);
foreach ($m as [, $category, $type, $title, $author, $status, $hex]) {
    $data = json_decode((string)hex2bin($hex), true);
    $write(3, ['status' => $status, 'category' => $category, 'type' => $type,
        'title' => str_replace("''", "'", $title), 'author' => str_replace("''", "'", $author)] + $data);
}
echo "catalog + $n cases written\n";
