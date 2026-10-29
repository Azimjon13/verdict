/* VERDICT — неоновые модальные окна вместо alert() и confirm().
 *
 *   VerdictModal.confirm({ title, text, ok, cancel, tone }) → Promise<boolean>
 *   VerdictModal.alert({ title, text, items: [{ text, onClick }], tone }) → Promise<void>
 *   html — вместо text: готовая разметка с сервера (уже экранированная шаблоном), например подарок из тайника.
 *
 * tone: info | warn | danger | success
 */
(() => {
  'use strict';

  const ICONS = {
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    warn: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    danger: '<path d="M3 6h18"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M10 11v6"/><path d="M14 11v6"/>',
    success: '<circle cx="12" cy="12" r="10"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
    question: '<circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
    logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
    x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    arrow: '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    gift: '<rect x="3" y="8" width="18" height="4" rx="1"/><path d="M12 8v13"/><path d="M19 12v7a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-7"/><path d="M7.5 8a2.5 2.5 0 0 1 0-5C10 3 12 8 12 8s2-5 4.5-5a2.5 2.5 0 0 1 0 5"/>',
    lock: '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  };
  const KICKERS = { info: 'Сообщение', warn: 'Внимание', danger: 'Подтвердите действие', success: 'Подтверждение' };
  const svg = (name) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ICONS.info}</svg>`;

  let root = null;
  let resolver = null;
  let lastFocus = null;
  let hideTimer = 0;

  function build() {
    root = document.createElement('div');
    root.className = 'modal-root';
    root.hidden = true;
    root.innerHTML = `
      <div class="modal-backdrop" data-close></div>
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="vm-title" aria-describedby="vm-text">
        <div class="modal-scan" aria-hidden="true"></div>
        <button type="button" class="modal-x" data-close aria-label="Закрыть">${svg('x')}</button>
        <div class="modal-icon"></div>
        <span class="modal-kicker"></span>
        <h2 class="modal-title" id="vm-title"></h2>
        <div class="modal-text" id="vm-text"></div>
        <ul class="modal-list"></ul>
        <div class="modal-actions">
          <button type="button" class="btn btn-ghost" data-cancel></button>
          <button type="button" class="btn btn-primary" data-ok></button>
        </div>
      </div>`;
    document.body.appendChild(root);

    root.addEventListener('click', (e) => {
      if (e.target.closest('[data-ok]')) close(true);
      else if (e.target.closest('[data-close], [data-cancel]')) close(false);
    });
    root.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        close(false);
      } else if (e.key === 'Tab') {
        trapFocus(e);
      }
    });
  }

  function trapFocus(e) {
    const items = [...root.querySelectorAll('.modal button:not([hidden]), .modal a[href]')].filter((el) => el.offsetParent !== null);
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  function open(options) {
    if (!root) build();
    if (resolver) close(false);
    clearTimeout(hideTimer);

    const o = Object.assign({ tone: 'info', title: '', text: '', items: [], ok: 'Подтвердить', cancel: 'Отмена', mode: 'confirm' }, options);
    const modal = root.querySelector('.modal');
    modal.className = `modal tone-${o.tone}`;
    root.querySelector('.modal-icon').innerHTML = svg(o.icon || o.tone);
    root.querySelector('.modal-kicker').textContent = o.kicker || KICKERS[o.tone] || KICKERS.info;
    root.querySelector('.modal-title').textContent = o.title;

    const text = root.querySelector('.modal-text');
    if (o.html) text.innerHTML = o.html;
    else text.textContent = o.text;
    text.hidden = !o.text && !o.html;
    modal.classList.toggle('modal-rich', Boolean(o.html));

    const list = root.querySelector('.modal-list');
    list.innerHTML = '';
    list.hidden = !o.items.length;
    o.items.forEach((item, i) => {
      const li = document.createElement('li');
      const el = document.createElement(item.onClick ? 'button' : 'span');
      if (item.onClick) {
        el.type = 'button';
        el.addEventListener('click', () => {
          close(false);
          setTimeout(item.onClick, 30);
        });
      }
      el.className = 'modal-item';
      el.innerHTML = `<span class="modal-item-num">${String(i + 1).padStart(2, '0')}</span><span class="modal-item-text"></span>${item.onClick ? svg('arrow') : ''}`;
      el.querySelector('.modal-item-text').textContent = item.text;
      li.appendChild(el);
      list.appendChild(li);
    });

    const okBtn = root.querySelector('[data-ok]');
    const cancelBtn = root.querySelector('[data-cancel]');
    okBtn.textContent = o.ok;
    cancelBtn.textContent = o.cancel;
    cancelBtn.hidden = o.mode === 'alert';

    lastFocus = document.activeElement;
    root.hidden = false;
    document.documentElement.classList.add('modal-lock');
    requestAnimationFrame(() => root.classList.add('open'));
    // Для опасных действий фокус по умолчанию — на «Отмене».
    setTimeout(() => (o.mode === 'confirm' && o.tone === 'danger' ? cancelBtn : okBtn).focus({ preventScroll: true }), 40);

    return new Promise((resolve) => { resolver = resolve; });
  }

  function close(result) {
    if (!resolver) return;
    const resolve = resolver;
    resolver = null;
    root.classList.remove('open');
    document.documentElement.classList.remove('modal-lock');
    hideTimer = setTimeout(() => { root.hidden = true; }, 260);
    if (lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus({ preventScroll: true });
    resolve(result);
  }

  window.VerdictModal = {
    confirm: (o) => open(Object.assign({}, o, { mode: 'confirm' })),
    alert: (o) => open(Object.assign({ ok: 'Понятно' }, o, { mode: 'alert' })).then(() => undefined),
    isOpen: () => resolver !== null,
  };
})();
