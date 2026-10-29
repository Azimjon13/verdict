<?php
require __DIR__ . '/includes/bootstrap.php';

if ($_SERVER['REQUEST_METHOD'] === 'POST' && csrf_valid() && is_logged_in()) {
    auth_logout();
    flash('success', 'Вы вышли из аккаунта.');
}

redirect('index.php');
