<?php
require __DIR__ . '/includes/bootstrap.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST' || !csrf_valid()) {
    flash('error', 'Не удалось выполнить действие. Обновите страницу и попробуйте снова.');
    redirect('library.php');
}
$id = (int)($_POST['id'] ?? 0);
$action = (string)($_POST['action'] ?? '');
$back = safe_back($_POST['back'] ?? '') ?: 'view.php?id=' . $id;
$s = situation_find($id);

// Автор может удалить свой черновик; всё остальное — только команда.
$ownDraftDelete = $s && $action === 'delete' && $s['status'] === 'draft' && owns_situation($s);
if (!is_admin() && !$ownDraftDelete) {
    flash('error', 'Это действие доступно только команде.');
    redirect(is_logged_in() ? 'library.php' : 'login.php?back=library.php');
}

if (!$s) {
    flash('error', 'Ситуация не найдена.');
    redirect('library.php');
}

switch ($action) {
    case 'approved':
        situation_set_status($id, 'approved');
        flash('success', 'Ситуация «' . $s['title'] . '» добавлена в игру.');
        break;
    case 'rejected':
        situation_set_status($id, 'rejected');
        flash('success', 'Ситуация «' . $s['title'] . '» отклонена.');
        break;
    case 'pending':
        situation_set_status($id, 'pending');
        flash('success', 'Ситуация «' . $s['title'] . '» возвращена на отбор.');
        break;
    case 'delete':
        situation_delete($id);
        flash('success', $s['status'] === 'draft'
            ? 'Черновик «' . $s['title'] . '» удалён.'
            : 'Ситуация «' . $s['title'] . '» удалена.');
        redirect($ownDraftDelete ? 'account.php' : 'library.php');
    default:
        flash('error', 'Неизвестное действие.');
}

redirect($back);
