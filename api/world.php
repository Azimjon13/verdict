<?php
require dirname(__DIR__) . '/includes/bootstrap.php';

$back = safe_back($_POST['back'] ?? '') ?: 'play.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST' || !csrf_valid()) {
    flash('error', 'Не удалось выполнить действие. Обновите страницу и попробуйте снова.');
    redirect('../' . $back);
}

world_reset();
flash('success', 'Мир начат заново. Все показатели вернулись к исходным значениям.');
redirect('../' . $back);
