<?php
require __DIR__ . '/includes/bootstrap.php';

require_login('account.php', 'Войдите, чтобы открыть профиль.');
$me = current_user();
$uid = (int)$me['id'];

$errors = [];
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $action = (string)($_POST['action'] ?? '');
    if (!csrf_valid()) {
        flash('error', 'Сессия устарела. Попробуйте ещё раз.');
        redirect('account.php');
    }
    if ($action === 'name') {
        $name = input_str($_POST['display_name'] ?? '', 80);
        $errors = name_validate($name);
        if (!$errors) {
            user_update_name($uid, $name);
            flash('success', 'Имя обновлено. Подпись в ваших ситуациях тоже изменена.');
            redirect('account.php');
        }
    } elseif ($action === 'password') {
        $current = (string)($_POST['current_password'] ?? '');
        $new = (string)($_POST['new_password'] ?? '');
        $confirm = (string)($_POST['new_password_confirm'] ?? '');
        if (!auth_attempt($me['login'], $current)) {
            $errors['current_password'] = 'Текущий пароль указан неверно.';
        } else {
            foreach (password_validate($new, $confirm) as $field => $message) {
                $errors['new_' . $field] = $message;
            }
        }
        if (!$errors) {
            user_set_password($uid, $new);
            $closed = sessions_revoke_others($uid);
            session_regenerate_id(true);
            flash('success', 'Пароль изменён.' . ($closed ? ' Другие сеансы входа завершены: ' . $closed . '.' : ''));
            redirect('account.php');
        }
    } elseif ($action === 'sessions') {
        $closed = sessions_revoke_others($uid);
        flash('success', $closed ? 'Завершено других сеансов: ' . $closed . '.' : 'Других активных сеансов нет.');
        redirect('account.php');
    }
}

$mine = situations_list(['user_id' => $uid]);
$byStatus = array_fill_keys(array_keys(STATUSES), 0);
foreach ($mine as $s) {
    $byStatus[$s['status']] = ($byStatus[$s['status']] ?? 0) + 1;
}
$counts = vote_counts();
$sessions = sessions_active_count($uid);

page_header('Профиль', 'account', 'page-account', 'calm');
?>

<section class="page-hero page-hero-compact">
    <div class="container account-hero">
        <span class="avatar avatar-lg" style="--ah: <?= name_hue($me['display_name']) ?>"><?= e(initials($me['display_name'])) ?></span>
        <div>
            <span class="kicker">Профиль · <?= e(ROLES[$me['role']] ?? $me['role']) ?></span>
            <h1><?= e($me['display_name']) ?></h1>
            <p class="account-meta">
                <span><?= icon('user') ?>@<?= e($me['login']) ?></span>
                <span><?= icon('calendar') ?>с <?= e(format_date($me['created_at'])) ?></span>
                <span><?= icon('shield') ?><?= $sessions ?> <?= plural($sessions, 'активный сеанс', 'активных сеанса', 'активных сеансов') ?></span>
            </p>
        </div>
        <div class="hero-actions">
            <a class="btn btn-primary" href="create.php"><?= icon('plus') ?>Новая ситуация</a>
            <?php if (is_admin()): ?><a class="btn" href="users.php"><?= icon('users') ?>Пользователи</a><?php endif; ?>
        </div>
    </div>
</section>

<div class="container account-layout">
    <section class="account-main">
        <div class="account-stats">
            <div class="panel"><b><?= count($mine) ?></b><span>всего ситуаций</span></div>
            <?php foreach (STATUSES as $key => $label): ?>
                <div class="panel stat-<?= e($key) ?>"><b><?= $byStatus[$key] ?></b><span><?= e(mb_strtolower($label)) ?></span></div>
            <?php endforeach; ?>
        </div>

        <div class="panel block">
            <header class="block-head"><span class="block-num"><?= icon('file') ?></span><h2>Мои ситуации</h2></header>
            <?php if (!$mine): ?>
                <div class="empty-inline">
                    <p class="muted">Вы ещё не создали ни одной ситуации.</p>
                    <a class="btn btn-primary btn-sm" href="create.php"><?= icon('plus') ?>Создать первую</a>
                </div>
            <?php else: ?>
                <ul class="my-list">
                    <?php foreach ($mine as $s):
                        $cat = CATEGORIES[$s['category']] ?? ['name' => $s['category'], 'icon' => 'circle'];
                        $v = array_sum($counts[$s['id']] ?? []); ?>
                        <li style="<?= e(category_style($s['category'])) ?>">
                            <span class="my-icon"><?= icon($cat['icon']) ?></span>
                            <div class="my-body">
                                <a href="<?= $s['status'] === 'draft' ? 'create.php?edit=' : 'view.php?id=' ?><?= $s['id'] ?>"><?= e($s['title']) ?></a>
                                <span><?= e($cat['name']) ?> · <?= e(SITUATION_TYPES[$s['type']]['name'] ?? $s['type']) ?> · <?= e(format_date($s['created_at'])) ?></span>
                            </div>
                            <?= level_chip(situation_level($s)) ?>
                            <span class="my-votes" title="Вердиктов"><?= icon('gavel') ?><?= $v ?></span>
                            <span class="status status-<?= e($s['status']) ?>"><?= e(STATUSES[$s['status']] ?? $s['status']) ?></span>
                            <?php if (can_edit_situation($s)): ?>
                                <a class="icon-btn" href="create.php?edit=<?= $s['id'] ?>" title="Редактировать" aria-label="Редактировать"><?= icon('edit') ?></a>
                            <?php endif; ?>
                        </li>
                    <?php endforeach; ?>
                </ul>
                <p class="muted small">Черновики видите только вы — дописывайте их в любое время. Отправленные ситуации можно редактировать, пока они на отборе.</p>
            <?php endif; ?>
        </div>
    </section>

    <aside class="account-side">
        <form method="post" class="panel side-card" data-validate novalidate>
            <?= csrf_field() ?>
            <input type="hidden" name="action" value="name">
            <span class="label-mono">Имя в подписи</span>
            <label class="field<?= isset($errors['display_name']) ? ' has-error' : '' ?>">
                <span>Имя или ник</span>
                <input type="text" name="display_name" value="<?= e($_POST['display_name'] ?? $me['display_name']) ?>" required minlength="2" maxlength="80">
                <?= field_error($errors, 'display_name') ?>
            </label>
            <button class="btn btn-sm btn-block" type="submit"><?= icon('check') ?>Сохранить имя</button>
        </form>

        <form method="post" class="panel side-card" data-validate novalidate>
            <?= csrf_field() ?>
            <input type="hidden" name="action" value="password">
            <span class="label-mono">Смена пароля</span>
            <label class="field<?= isset($errors['current_password']) ? ' has-error' : '' ?>">
                <span>Текущий пароль</span>
                <input type="password" name="current_password" required autocomplete="current-password">
                <?= field_error($errors, 'current_password') ?>
            </label>
            <label class="field<?= isset($errors['new_password']) ? ' has-error' : '' ?>">
                <span>Новый пароль</span>
                <input type="password" name="new_password" required minlength="<?= PASSWORD_MIN ?>" maxlength="200" autocomplete="new-password" data-strength>
                <span class="strength" aria-hidden="true"><i></i></span>
                <?= field_error($errors, 'new_password') ?>
            </label>
            <label class="field<?= isset($errors['new_password_confirm']) ? ' has-error' : '' ?>">
                <span>Повторите новый пароль</span>
                <input type="password" name="new_password_confirm" required data-match="new_password" data-match-msg="Новые пароли не совпадают." autocomplete="new-password">
                <?= field_error($errors, 'new_password_confirm') ?>
            </label>
            <button class="btn btn-sm btn-block" type="submit"><?= icon('lock') ?>Изменить пароль</button>
            <p class="muted small">После смены пароля все другие сеансы входа будут завершены.</p>
        </form>

        <form method="post" class="panel side-card" data-confirm="Завершить все сеансы входа, кроме этого? На других устройствах придётся войти заново." data-confirm-title="Завершить сеансы" data-confirm-ok="Завершить" data-confirm-tone="danger">
            <?= csrf_field() ?>
            <input type="hidden" name="action" value="sessions">
            <span class="label-mono">Безопасность</span>
            <p class="muted small">Сессии хранятся на сервере. Если вы входили с чужого устройства, завершите остальные сеансы.</p>
            <button class="btn btn-sm btn-block btn-danger" type="submit"><?= icon('logout') ?>Выйти на других устройствах</button>
        </form>
    </aside>
</div>

<?php page_footer(); ?>
