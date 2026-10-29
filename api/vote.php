<?php
require dirname(__DIR__) . '/includes/bootstrap.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    json_response(['ok' => false, 'error' => 'Метод не поддерживается.'], 405);
}
if (!csrf_valid()) {
    json_response(['ok' => false, 'error' => 'Сессия устарела. Обновите страницу и попробуйте снова.'], 419);
}

$s = situation_find((int)($_POST['situation_id'] ?? 0));
if (!$s || !can_view_situation($s)) {
    json_response(['ok' => false, 'error' => 'Дело не найдено.'], 404);
}

$key = input_str($_POST['option'] ?? '', 10);
$reasoning = input_str($_POST['reasoning'] ?? '', 1000);
$decision = $key === 'other' ? null : situation_decision($s, $key);

if ($key !== 'other' && !$decision) {
    json_response(['ok' => false, 'error' => 'Выберите один из вариантов решения.'], 422);
}
if ($key === 'other' && mb_strlen($reasoning) < 10) {
    json_response(['ok' => false, 'error' => 'Опишите своё решение — хотя бы одно предложение.'], 422);
}

$preview = $s['status'] !== 'approved';
$voter = voter_id();
$quick = ($_POST['mode'] ?? '') === 'quick';
if ($quick && $preview) {
    json_response(['ok' => false, 'error' => 'Это дело ещё не в игре.'], 422);
}

// Догадка о большинстве («Быстрый суд»): сравниваем с голосами других игроков ДО этого вердикта.
$guess = input_str($_POST['guess'] ?? '', 10);
$guess = $guess !== '' && situation_decision($s, $guess) ? $guess : null;
$majority = $quick ? majority_keys($s['id'], $voter) : [];
$guessCorrect = $guess !== null && $majority ? (int)in_array($guess, $majority, true) : null;
$duration = (int)($_POST['duration_ms'] ?? 0);

if (!$preview) {
    vote_save($s['id'], $voter, $key, $reasoning, [
        'mode'          => $quick ? 'quick' : 'full',
        'duration_ms'   => $duration > 0 ? min($duration, 3600000) : null,
        'guess_key'     => $quick ? $guess : null,
        'guess_correct' => $quick ? $guessCorrect : null,
    ]);
    world_record($s['id'], $key, $decision['effects'] ?? []);
}

// Профиль судьи: после вердикта сообщаем, открылся ли он или сменился стиль.
$judge = null;
if (!$preview) {
    $profile = judge_profile($voter);
    $judge = ['profile' => $profile, 'event' => judge_event($profile)];
}

$html = $quick
    ? partial('quick-result', [
        's'        => $s,
        'choice'   => $key,
        'guess'    => $guess,
        'majority' => $majority,
        'correct'  => $guessCorrect,
        'counts'   => vote_counts_for($s['id']),
        'stats'    => quick_stats($voter),
        'judge'    => $judge,
    ])
    : partial('result', [
        's'         => $s,
        'choice'    => $key,
        'reasoning' => $reasoning,
        'counts'    => vote_counts_for($s['id']),
        'preview'   => $preview,
        'next'      => $preview ? null : next_case($s['id'], $voter),
        'fresh'     => true,
        'judge'     => $judge,
    ]);

$deltas = [];
if (!$preview) {
    foreach ($decision['effects'] ?? [] as $m => $v) {
        $deltas[$m] = (int)$v * METRIC_STEP;
    }
}

$count = world_count();
json_response([
    'ok'      => true,
    'html'    => $html,
    'preview' => $preview,
    'quick'   => $quick ? ['correct' => $guessCorrect, 'stats' => quick_stats($voter)] : null,
    'world'   => [
        'metrics' => world_metrics(),
        'deltas'  => $deltas,
        'count'   => $count,
        'word'    => plural($count, 'вердикт', 'вердикта', 'вердиктов'),
    ],
]);
