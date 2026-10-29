<?php
require __DIR__ . '/includes/bootstrap.php';

$back = safe_back($_POST['back'] ?? ($_GET['back'] ?? ''));
if (is_logged_in()) {
    redirect($back ?: (is_admin() ? 'library.php' : 'create.php'));
}

$error = '';
$login = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $login = input_str($_POST['login'] ?? '', 40);
    $password = (string)($_POST['password'] ?? '');
    $wait = login_lock_seconds();
    if (!csrf_valid()) {
        $error = 'Сессия устарела. Попробуйте ещё раз.';
    } elseif ($wait > 0) {
        $error = 'Слишком много неудачных попыток. Попробуйте через ' . $wait . ' сек.';
    } elseif ($login === '' || $password === '') {
        $error = 'Введите логин и пароль.';
    } elseif ($user = auth_attempt($login, $password)) {
        auth_login($user);
        flash('success', 'С возвращением, ' . $user['display_name'] . '!');
        redirect($back ?: ($user['role'] === 'admin' ? 'library.php' : 'create.php'));
    } else {
        login_register_failure();
        usleep(300000);
        $error = 'Неверный логин или пароль.';
    }
}

page_header('Вход', '', 'page-auth', 'high');
?>

<section class="section auth-section">
    <div class="container">
        <form method="post" class="panel auth-card hud" data-validate novalidate>
            <?= csrf_field() ?>
            <input type="hidden" name="back" value="<?= e($back) ?>">
            <div class="auth-icon"><?= icon('login') ?></div>
            <span class="kicker">Вход в VERDICT</span>
            <h1>С возвращением</h1>
            <p class="muted">Войдите, чтобы добавлять ситуации и следить за их отбором.</p>

            <?php if ($error): ?>
                <div class="form-alert" role="alert"><?= icon('alert') ?><span><?= e($error) ?></span></div>
            <?php endif; ?>

            <label class="field">
                <span>Логин</span>
                <input type="text" name="login" value="<?= e($login) ?>" required maxlength="40" autocomplete="username" autocapitalize="none" spellcheck="false" autofocus>
            </label>
            <label class="field">
                <span>Пароль</span>
                <span class="password-wrap">
                    <input type="password" name="password" required autocomplete="current-password">
                    <button type="button" class="pw-toggle" aria-label="Показать пароль" data-pw-toggle><?= icon('eye') ?></button>
                </span>
            </label>
            <button class="btn btn-primary btn-block btn-lg" type="submit"><?= icon('login') ?>Войти</button>
            <p class="auth-switch">Нет аккаунта? <a href="register.php<?= $back ? '?back=' . e(rawurlencode($back)) : '' ?>">Зарегистрироваться</a></p>
        </form>
    </div>
</section>

<?php page_footer(); ?>
