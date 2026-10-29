<?php
require __DIR__ . '/includes/bootstrap.php';

require_login('users.php');
if (!is_admin()) {
    flash('error', 'Список пользователей доступен только команде.');
    redirect('account.php');
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $id = (int)($_POST['id'] ?? 0);
    $role = (string)($_POST['role'] ?? '');
    $target = user_find($id);
    if (!csrf_valid() || !$target || !isset(ROLES[$role])) {
        flash('error', 'Не удалось изменить роль.');
    } elseif ($target['role'] === 'admin' && $role !== 'admin' && admins_count() <= 1) {
        flash('error', 'Нельзя снять права с последнего участника команды.');
    } else {
        user_set_role($id, $role);
        flash('success', $target['display_name'] . ': роль изменена на «' . ROLES[$role] . '».');
    }
    redirect('users.php');
}

$users = users_all();
$me = current_user_id();

page_header('Пользователи', 'users', 'page-users', 'calm');
?>

<section class="page-hero page-hero-compact">
    <div class="container">
        <span class="kicker">Команда</span>
        <h1>Пользователи <span class="grad-text">и авторы</span></h1>
        <p class="lead">Авторы добавляют ситуации, команда отбирает их, видит скрытую информацию и экспортирует контент для игры.</p>
    </div>
</section>

<section class="container section-top-0 users-section">
    <div class="users-list">
        <?php foreach ($users as $u): $isMe = (int)$u['id'] === $me; ?>
            <article class="panel user-row">
                <span class="avatar" style="--ah: <?= name_hue($u['display_name']) ?>"><?= e(initials($u['display_name'])) ?></span>
                <div class="user-main">
                    <h3><?= e($u['display_name']) ?><?= $isMe ? ' <small>(вы)</small>' : '' ?></h3>
                    <p class="lib-sub"><?= icon('user') ?>@<?= e($u['login']) ?><span class="sep">·</span><?= icon('calendar') ?>с <?= e(format_date($u['created_at'])) ?><span class="sep">·</span><?= $u['last_login_at'] ? 'последний вход ' . e(format_date($u['last_login_at'])) : 'входа ещё не было' ?></p>
                </div>
                <div class="lib-stats">
                    <span title="Ситуаций"><?= icon('file') ?><?= (int)$u['situations'] ?></span>
                    <span title="В игре"><?= icon('check') ?><?= (int)$u['approved'] ?></span>
                </div>
                <form method="post" class="inline-form role-form"
                      data-confirm="<?= e($u['role'] === 'admin' ? 'Снять с «' . $u['display_name'] . '» права команды? Пользователь останется автором.' : 'Дать «' . $u['display_name'] . '» права команды? Пользователь сможет одобрять, удалять и экспортировать ситуации и видеть скрытую информацию.') ?>"
                      data-confirm-title="<?= $u['role'] === 'admin' ? 'Снять права команды' : 'Права команды' ?>"
                      data-confirm-ok="<?= $u['role'] === 'admin' ? 'Снять права' : 'Дать права' ?>"
                      data-confirm-tone="<?= $u['role'] === 'admin' ? 'danger' : 'warn' ?>">
                    <?= csrf_field() ?>
                    <input type="hidden" name="id" value="<?= (int)$u['id'] ?>">
                    <select class="vs" name="role" data-autosubmit data-size="sm" data-align="right" aria-label="Роль: <?= e($u['display_name']) ?>">
                        <option value="author"<?= option_icon('user', 190) ?> data-desc="Добавляет ситуации"<?= $u['role'] === 'author' ? ' selected' : '' ?>><?= e(ROLES['author']) ?></option>
                        <option value="admin"<?= option_icon('shield', 150) ?> data-desc="Отбор, скрытое, экспорт"<?= $u['role'] === 'admin' ? ' selected' : '' ?>><?= e(ROLES['admin']) ?></option>
                    </select>
                </form>
            </article>
        <?php endforeach; ?>
    </div>
</section>

<?php page_footer(); ?>
