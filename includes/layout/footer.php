<?php
defined('APP_ROOT') || exit;

/** @var array $scripts */
?>
</main>

<footer class="site-footer">
    <div class="container footer-grid">
        <div class="footer-brand">
            <a class="brand" href="index.php"><?= logo_svg('logo') ?><span class="brand-name">VERDICT</span></a>
            <p>Нет правильного ответа.<br>Есть только ваш вердикт.</p>
        </div>
        <div>
            <h4>Игра</h4>
            <a href="quick.php">Быстрый суд</a>
            <a href="play.php">Архив дел</a>
            <a href="judge.php">Профиль судьи</a>
            <a href="index.php#how">Как это работает</a>
            <a href="index.php#categories">Категории</a>
        </div>
        <div>
            <h4>Авторам</h4>
            <a href="brief.php">Бриф для авторов</a>
            <a href="create.php">Создать ситуацию</a>
            <a href="library.php">Отбор контента</a>
        </div>
        <div>
            <h4>Путь проекта</h4>
            <ol class="footer-road">
                <?php foreach (ROADMAP as $i => $step): ?>
                    <li class="<?= $i === 0 ? 'now' : '' ?>"><?= e($step) ?></li>
                <?php endforeach; ?>
            </ol>
        </div>
    </div>
    <div class="container footer-bottom">
        <span>© <?= date('Y') ?> VERDICT · MVP</span>
        <span>Все миры вымышлены и не связаны с реальными странами, политикой или законами.</span>
    </div>
</footer>

<script src="<?= e(asset('js/background.js')) ?>"></script>
<script src="<?= e(asset('js/modal.js')) ?>"></script>
<script src="<?= e(asset('js/select.js')) ?>"></script>
<script src="<?= e(asset('js/app.js')) ?>"></script>
<?php foreach ($scripts as $s): ?>
<script src="<?= e(asset('js/' . $s)) ?>"></script>
<?php endforeach; ?>
</body>
</html>
