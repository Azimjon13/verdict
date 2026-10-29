<?php
/**
 * Экспорт ситуаций в JSON для игрового клиента (только для команды).
 *   api/export.php?id=3        — одна ситуация (любого статуса)
 *   api/export.php             — все одобренные
 *   api/export.php?status=all  — все
 */
require dirname(__DIR__) . '/includes/bootstrap.php';

if (!is_admin()) {
    json_response(['ok' => false, 'error' => 'Доступно только команде.'], 403);
}

$counts = vote_counts();
$pack = static function (array $s) use ($counts): array {
    $s['votes'] = $counts[$s['id']] ?? new stdClass();
    return $s;
};

$id = (int)($_GET['id'] ?? 0);
if ($id > 0) {
    $s = situation_find($id);
    if (!$s) {
        json_response(['ok' => false, 'error' => 'Ситуация не найдена.'], 404);
    }
    $items = [$pack($s)];
    $filename = 'verdict-situation-' . $id . '.json';
} else {
    $status = ($_GET['status'] ?? '') === 'all' ? null : 'approved';
    $items = array_map($pack, situations_list(['status' => $status, 'order' => 'old']));
    $filename = 'verdict-situations-' . date('Ymd') . '.json';
}

header('Content-Type: application/json; charset=utf-8');
header('Content-Disposition: attachment; filename="' . $filename . '"');
echo json_encode([
    'exported_at' => date('c'),
    'count'       => count($items),
    'situations'  => $items,
], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
