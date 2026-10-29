<?php
defined('APP_ROOT') || exit;

/** @var string $title @var string $active @var string $bodyClass @var string $bg */
$flashes = take_flashes();
$autosaveClear = take_autosave_clear();
$nav = [
    'home'    => ['index.php', 'Главная'],
    'quick'   => ['quick.php', 'Быстрый суд'],
    'play'    => ['play.php', 'Архив дел'],
    'create'  => ['create.php', 'Создать ситуацию'],
    'library' => ['library.php', 'Отбор'],
    'brief'   => ['brief.php', 'Бриф'],
];
$me = current_user();
if ($me && $me['role'] === 'admin') {
    $nav['users'] = ['users.php', 'Пользователи'];
}
?><!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
    <title><?= e($title !== '' ? $title . ' — VERDICT' : 'VERDICT — симулятор решений и суждений') ?></title>
    <meta name="description" content="VERDICT — игра-симулятор решений: вымышленные миры, спорные поступки, свидетели, которые могут лгать, и последствия вашего выбора.">
    <meta name="theme-color" content="#03040a">
    <link rel="icon" href="assets/img/favicon.svg" type="image/svg+xml">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Manrope:wght@400;500;600;700;800&family=Unbounded:wght@500;700;800;900&display=swap">
    <link rel="stylesheet" href="<?= e(asset('css/style.css')) ?>">
    <script>document.documentElement.classList.add('js');</script>
</head>
<?php $vp = ['page-home' => '0.72', 'page-play' => '0.79'][$bodyClass] ?? '0.5'; /* где на широком экране стоит неоновое солнце */ ?>
<body class="<?= e($bodyClass) ?>" data-bg="<?= e($bg) ?>" data-vp="<?= $vp ?>" data-csrf="<?= e(csrf_token()) ?>"<?= $autosaveClear ? ' data-autosave-clear="' . e(json_encode($autosaveClear)) . '"' : '' ?>>
<a class="skip-link" href="#main">Перейти к содержимому</a>

<div class="bg-base" aria-hidden="true">
    <div class="bg-aurora bg-aurora-1"></div>
    <div class="bg-aurora bg-aurora-2"></div>
    <div class="bg-aurora bg-aurora-3"></div>
</div>
<canvas id="bg-canvas" aria-hidden="true"></canvas>
<div class="bg-fx" aria-hidden="true">
    <div class="bg-hex"></div>
    <div class="bg-beam"></div>
    <div class="bg-scan"></div>
    <div class="bg-vignette"></div>
</div>

<header class="site-header">
    <a class="brand" href="index.php" aria-label="VERDICT — на главную">
        <?= logo_svg('logo') ?>
        <span class="brand-name" data-text="VERDICT">VERDICT</span>
        <span class="brand-tag">MVP</span>
    </a>

    <nav class="nav" id="site-nav" aria-label="Основная навигация">
        <?php foreach ($nav as $key => [$href, $label]): ?>
            <a href="<?= $href ?>"<?= $active === $key ? ' class="active" aria-current="page"' : '' ?>><?= e($label) ?></a>
        <?php endforeach; ?>
    </nav>

    <div class="header-actions">
        <?php if ($me): ?>
            <a class="user-chip<?= $active === 'account' ? ' active' : '' ?>" href="account.php" title="Профиль">
                <span class="avatar avatar-xs" style="--ah: <?= name_hue($me['display_name']) ?>"><?= e(initials($me['display_name'])) ?></span>
                <span class="user-name"><?= e($me['display_name']) ?></span>
                <?php if ($me['role'] === 'admin'): ?><span class="user-role" title="Команда"><?= icon('shield') ?></span><?php endif; ?>
            </a>
            <form method="post" action="logout.php" class="inline-form" data-confirm="Выйти из аккаунта на этом устройстве?" data-confirm-title="Выход" data-confirm-ok="Выйти">
                <?= csrf_field() ?>
                <button class="icon-btn" type="submit" title="Выйти" aria-label="Выйти"><?= icon('logout') ?></button>
            </form>
        <?php else: ?>
            <a class="btn btn-sm btn-ghost btn-login" href="login.php"><?= icon('login') ?>Войти</a>
        <?php endif; ?>
        <a class="btn btn-primary btn-sm btn-play" href="quick.php"><?= icon('play') ?>Играть</a>
        <button class="icon-btn nav-toggle" type="button" aria-controls="site-nav" aria-expanded="false" aria-label="Меню"><?= icon('menu') ?></button>
    </div>
</header>

<?php if ($flashes): ?>
    <div class="toasts" role="status">
        <?php foreach ($flashes as $f): ?>
            <div class="toast toast-<?= e($f['type']) ?>">
                <?= icon($f['type'] === 'error' ? 'alert' : 'check-circle') ?>
                <span><?= e($f['message']) ?></span>
                <button type="button" class="toast-close" aria-label="Закрыть"><?= icon('x') ?></button>
            </div>
        <?php endforeach; ?>
    </div>
<?php endif; ?>

<main id="main">
