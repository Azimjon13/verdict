<?php
/**
 * Роутер для встроенного сервера PHP: php -S localhost:8000 router.php
 * Закрывает служебные папки, остальное отдаёт как обычно.
 */
$path = (string)parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);

if (preg_match('#^/(includes|database)(/|$)#i', $path) || preg_match('#/\.#', $path)
    || preg_match('#^/(config|router)\.php$#i', $path)) {
    http_response_code(403);
    echo 'Forbidden';
    return true;
}

return false;
