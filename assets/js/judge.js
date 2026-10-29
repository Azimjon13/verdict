/* VERDICT — профиль судьи: «Поделиться» (системное меню или копирование ссылки). */
(() => {
  'use strict';

  document.querySelectorAll('[data-share]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const url = new URL(btn.dataset.shareUrl, window.location.href).href;
      const text = btn.dataset.shareText || '';
      const label = btn.querySelector('span');
      try {
        if (navigator.share) {
          await navigator.share({ title: 'VERDICT', text, url });
          return;
        }
        await navigator.clipboard.writeText(`${text} ${url}`);
        const prev = label.textContent;
        label.textContent = 'Ссылка скопирована';
        setTimeout(() => { label.textContent = prev; }, 2200);
      } catch (_) { /* отменено пользователем или нет доступа к буферу */ }
    });
  });
})();
