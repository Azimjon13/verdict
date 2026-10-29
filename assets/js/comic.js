/* VERDICT — «Дело в кадрах»: листаемый комикс поверх обычной разметки (без JS всё читается текстом). */
(() => {
  'use strict';

  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const MODE_KEY = 'verdict:comic-mode';
  const STEP_MS = 420; // пауза между появлением подписей и реплик

  function readMode() {
    try { return window.localStorage.getItem(MODE_KEY); } catch (_) { return null; }
  }
  function saveMode(mode) {
    try { window.localStorage.setItem(MODE_KEY, mode); } catch (_) { /* хранилище недоступно */ }
  }

  function init(root) {
    const panels = [...root.querySelectorAll('[data-cm-panel]')];
    const figures = [...root.querySelectorAll('[data-cm-figures]')];
    const dots = [...root.querySelectorAll('[data-cm-dot]')];
    const scene = root.querySelector('[data-cm-scene]');
    const viewport = root.querySelector('[data-cm-viewport]');
    const count = root.querySelector('[data-cm-count]');
    const next = root.querySelector('[data-cm-next]');
    const nextLabel = root.querySelector('[data-cm-next-label]');
    const prev = root.querySelector('[data-cm-prev]');
    const modeBtn = root.querySelector('[data-cm-mode]');
    const finishLabel = root.dataset.finishLabel || 'Дальше';
    if (!panels.length) return;

    let current = -1;
    let timers = [];

    const pending = () => panels[current]?.querySelectorAll('[data-seq]:not(.in)') || [];

    function talk(el) {
      const who = el.dataset.who;
      figures[current]?.querySelectorAll('.cm-fig').forEach((f) => f.classList.toggle('talking', who !== undefined && f.dataset.who === who));
    }

    function reveal(panel) {
      timers.forEach(clearTimeout);
      timers = [];
      const items = [...panel.querySelectorAll('[data-seq]')];
      items.forEach((el) => el.classList.remove('in'));
      if (reduce) {
        items.forEach((el) => el.classList.add('in'));
        updateNext();
        return;
      }
      items.forEach((el, k) => {
        timers.push(setTimeout(() => {
          el.classList.add('in');
          talk(el);
          if (k === items.length - 1) updateNext();
        }, 260 + k * STEP_MS));
      });
      updateNext();
    }

    function showAll() {
      timers.forEach(clearTimeout);
      timers = [];
      pending().forEach((el) => el.classList.add('in'));
      updateNext();
    }

    function updateNext() {
      const last = current === panels.length - 1;
      nextLabel.textContent = pending().length ? 'Показать всё' : (last ? finishLabel : 'Дальше');
      next.classList.toggle('is-final', last && !pending().length);
    }

    function show(i) {
      i = Math.max(0, Math.min(panels.length - 1, i));
      if (i === current) return;
      current = i;
      panels.forEach((p, k) => { p.hidden = k !== i; });
      figures.forEach((f, k) => {
        f.hidden = k !== i;
        f.classList.remove('enter');
        if (k === i) {
          void f.offsetWidth;
          f.classList.add('enter');
        }
      });
      const [x, y, s] = (panels[i].dataset.cam || '0 0 1').split(' ').map(Number);
      if (scene) scene.style.transform = `translate(${x}%, ${y}%) scale(${s})`;
      count.textContent = `${i + 1} / ${panels.length}`;
      dots.forEach((d, k) => {
        d.classList.toggle('done', k < i);
        if (k === i) d.setAttribute('aria-current', 'step'); else d.removeAttribute('aria-current');
      });
      prev.disabled = i === 0;
      reveal(panels[i]);
    }

    function finish() {
      showAll();
      root.dispatchEvent(new CustomEvent('comic:done', { bubbles: true }));
      const target = root.dataset.finish && document.querySelector(root.dataset.finish);
      if (target) {
        target.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
        setTimeout(() => target.querySelector('button, a, input, textarea')?.focus({ preventScroll: true }), reduce ? 0 : 450);
      }
    }

    function forward() {
      if (pending().length) showAll();
      else if (current === panels.length - 1) finish();
      else show(current + 1);
    }

    function back() {
      show(current - 1);
    }

    next.addEventListener('click', forward);
    prev.addEventListener('click', back);
    root.querySelector('[data-cm-skip]')?.addEventListener('click', finish);
    root.querySelectorAll('[data-cm-finish]').forEach((b) => b.addEventListener('click', finish));
    dots.forEach((d, k) => d.addEventListener('click', () => show(k)));

    // Нажатие на картинку — «дальше», свайп — листать.
    let startX = null;
    let startY = null;
    viewport.addEventListener('pointerdown', (e) => { startX = e.clientX; startY = e.clientY; });
    viewport.addEventListener('pointerup', (e) => {
      if (startX === null) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      startX = null;
      if (e.target.closest('button')) return;
      if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) {
        if (dx < 0) forward(); else back();
      } else if (Math.abs(dx) < 10 && Math.abs(dy) < 10) {
        forward();
      }
    });
    root.querySelector('.cm-panels').addEventListener('click', (e) => {
      if (!e.target.closest('button, a') && pending().length) showAll();
    });

    // Стрелки работают, пока комикс на экране.
    let visible = false;
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; }, { threshold: 0.35 }).observe(viewport);
    }
    document.addEventListener('keydown', (e) => {
      if (!visible || root.classList.contains('is-text') || window.VerdictModal?.isOpen()) return;
      if (e.target.closest?.('input, textarea, select, [contenteditable]') || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === 'ArrowRight') { e.preventDefault(); forward(); }
      if (e.key === 'ArrowLeft') { e.preventDefault(); back(); }
    });

    // «Читать текстом» — все кадры подряд, выбор запоминается.
    function setMode(mode) {
      const text = mode === 'text';
      root.classList.toggle('is-text', text);
      modeBtn.setAttribute('aria-pressed', String(text));
      modeBtn.querySelector('span').textContent = text ? 'Смотреть комиксом' : 'Читать текстом';
      panels.forEach((p, k) => { p.hidden = text ? false : k !== current; });
      if (text) {
        timers.forEach(clearTimeout);
        root.querySelectorAll('[data-seq]').forEach((el) => el.classList.add('in'));
      } else {
        const i = current;
        current = -1;
        show(i < 0 ? 0 : i);
      }
    }
    modeBtn.addEventListener('click', () => {
      const mode = root.classList.contains('is-text') ? 'comic' : 'text';
      saveMode(mode);
      setMode(mode);
    });

    root.classList.add('is-ready');
    show(0);
    if (readMode() === 'text') setMode('text');
  }

  document.querySelectorAll('[data-comic]').forEach(init);
})();
