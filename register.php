<?php
require __DIR__ . '/includes/bootstrap.php';

$back = safe_back($_POST['back'] ?? ($_GET['back'] ?? '')) ?: 'create.php';
if (is_logged_in()) {
    redirect($back);
}

$errors = [];
$values = ['login' => '', 'display_name' => ''];
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $values['login'] = input_str($_POST['login'] ?? '', 40);
    $values['display_name'] = input_str($_POST['display_name'] ?? '', 80);
    $password = (string)($_POST['password'] ?? '');
    $confirm = (string)($_POST['password_confirm'] ?? '');

    if (!csrf_valid()) {
        $errors['_csrf'] = 'Сессия устарела. Попробуйте ещё раз.';
    } else {
        $errors = registration_validate($values['login'], $values['display_name'], $password, $confirm);
    }
    if (!$errors) {
        try {
            $id = user_create($values['login'], $values['display_name'], $password);
            auth_login(user_find($id));
            flash('success', 'Аккаунт создан. Добро пожаловать, ' . $values['display_name'] . '!');
            redirect($back);
        } catch (PDOException $e) {
            if ($e->getCode() !== '23000') {
                throw $e;
            }
            $errors['login'] = 'Такой логин уже занят.';
        }
    }
}

page_header('Регистрация', '', 'page-auth', 'high');
?>

<section class="section auth-section">
    <div class="container">
        <form method="post" class="panel auth-card hud" data-validate novalidate>
            <?= csrf_field() ?>
            <input type="hidden" name="back" value="<?= e($back) ?>">
            <div class="auth-icon"><?= icon('user') ?></div>
            <span class="kicker">Для авторов контента</span>
            <h1>Регистрация</h1>
            <p class="muted">Аккаунт нужен, чтобы добавлять ситуации: под этим именем будет учитываться ваш вклад.</p>

            <?php if (isset($errors['_csrf'])): ?>
                <div class="form-alert" role="alert"><?= icon('alert') ?><span><?= e($errors['_csrf']) ?></span></div>
            <?php endif; ?>

            <label class="field<?= isset($errors['login']) ? ' has-error' : '' ?>">
                <span>Логин <em>— для входа</em></span>
                <input type="text" name="login" value="<?= e($values['login']) ?>" required minlength="3" maxlength="40"
                       pattern="[A-Za-z0-9_.\-]{3,40}" data-pattern-msg="Логин: латинские буквы, цифры, точка, дефис или подчёркивание (3–40 символов)."
                       autocomplete="username" autocapitalize="none" spellcheck="false" autofocus>
                <?= field_error($errors, 'login') ?>
            </label>
            <label class="field<?= isset($errors['display_name']) ? ' has-error' : '' ?>">
                <span>Имя или ник <em>— видно в подписи ситуаций</em></span>
                <input type="text" name="display_name" value="<?= e($values['display_name']) ?>" required minlength="2" maxlength="80" autocomplete="nickname" placeholder="Например: Анна К.">
                <?= field_error($errors, 'display_name') ?>
            </label>
            <label class="field<?= isset($errors['password']) ? ' has-error' : '' ?>">
                <span>Пароль <em>— не короче <?= PASSWORD_MIN ?> символов</em></span>
                <span class="password-wrap">
                    <input type="password" name="password" required minlength="<?= PASSWORD_MIN ?>" maxlength="200" autocomplete="new-password" data-strength>
                    <button type="button" class="pw-toggle" aria-label="Показать пароль" data-pw-toggle><?= icon('eye') ?></button>
                </span>
                <span class="strength" aria-hidden="true"><i></i></span>
                <?= field_error($errors, 'password') ?>
            </label>
            <label class="field<?= isset($errors['password_confirm']) ? ' has-error' : '' ?>">
                <span>Повторите пароль</span>
                <input type="password" name="password_confirm" required data-match="password" data-match-msg="Пароли не совпадают." autocomplete="new-password">
                <?= field_error($errors, 'password_confirm') ?>
            </label>
            <button class="btn btn-primary btn-block btn-lg" type="submit"><?= icon('check') ?>Создать аккаунт</button>
            <p class="auth-switch">Уже есть аккаунт? <a href="login.php<?= $back ? '?back=' . e(rawurlencode($back)) : '' ?>">Войти</a></p>
        </form>
    </div>
</section>

<?php page_footer(); ?>
