/* VERDICT — общий интерфейс. */
(() => {
  'use strict';

  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* Сервер сохранил форму — удаляем её копию из браузера (см. create.js, автосохранение). */
  try {
    JSON.parse(document.body.dataset.autosaveClear || '[]').forEach((key) => window.localStorage.removeItem(key));
  } catch (_) { /* хранилище недоступно */ }

  /* Мобильное меню */
  const toggle = document.querySelector('.nav-toggle');
  const nav = document.getElementById('site-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', () => {
      const open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(open));
    });
    nav.addEventListener('click', (e) => {
      if (e.target.closest('a')) {
        nav.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  /* Тосты */
  document.querySelectorAll('.toast').forEach((toast, i) => {
    const close = () => {
      toast.classList.add('out');
      setTimeout(() => toast.remove(), 300);
    };
    toast.querySelector('.toast-close')?.addEventListener('click', close);
    setTimeout(close, 6000 + i * 800);
  });

  /* Появление при прокрутке */
  const reveals = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window && !reduce) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('in');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
    reveals.forEach((el) => io.observe(el));
  } else {
    reveals.forEach((el) => el.classList.add('in'));
  }

  /* Подсветка карточек за курсором */
  document.addEventListener('pointermove', (e) => {
    const card = e.target.closest?.('.card');
    if (!card) return;
    const r = card.getBoundingClientRect();
    card.style.setProperty('--mx', `${e.clientX - r.left}px`);
    card.style.setProperty('--my', `${e.clientY - r.top}px`);
  }, { passive: true });

  /* Счётчики */
  const counters = document.querySelectorAll('[data-count]');
  const runCounter = (el) => {
    const target = parseInt(el.dataset.count, 10) || 0;
    if (reduce || target === 0) { el.textContent = target; return; }
    const start = performance.now(), dur = 1400;
    const step = (now) => {
      const p = Math.min(1, (now - start) / dur);
      el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };
  if ('IntersectionObserver' in window) {
    const co = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) { runCounter(entry.target); co.unobserve(entry.target); }
      });
    });
    counters.forEach((el) => co.observe(el));
  }

  /* Терминал: печатающиеся вердикты */
  const word = document.querySelector('.t-word[data-words]');
  if (word && !reduce) {
    let words = [];
    try { words = JSON.parse(word.dataset.words); } catch (_) { words = []; }
    let wi = 0, ci = words[0]?.length || 0, deleting = true;
    const tick = () => {
      const current = words[wi] || '';
      if (deleting) {
        ci--;
        if (ci <= 0) { deleting = false; wi = (wi + 1) % words.length; }
      } else {
        ci++;
        if (ci >= (words[wi] || '').length) { deleting = true; word.textContent = words[wi]; setTimeout(tick, 1800); return; }
      }
      word.textContent = (deleting ? current : words[wi]).slice(0, Math.max(0, ci));
      setTimeout(tick, deleting ? 45 : 85);
    };
    if (words.length > 1) setTimeout(tick, 2200);
  }

  /* Подтверждение действий в модальном окне: <form data-confirm="…" data-confirm-title data-confirm-ok data-confirm-tone> */
  document.addEventListener('submit', (e) => {
    const form = e.target;
    if (!form.matches('form[data-confirm]') || form.dataset.confirmed === '1') return;
    e.preventDefault();
    e.stopImmediatePropagation();
    const submitter = e.submitter;
    const ask = window.VerdictModal
      ? window.VerdictModal.confirm({
        title: form.dataset.confirmTitle || 'Подтвердите действие',
        text: form.dataset.confirm,
        ok: form.dataset.confirmOk || 'Подтвердить',
        tone: form.dataset.confirmTone || 'warn',
      })
      : Promise.resolve(window.confirm(form.dataset.confirm));
    ask.then((ok) => {
      if (!ok) {
        form.dispatchEvent(new CustomEvent('verdict:confirm-cancel', { bubbles: true }));
        return;
      }
      form.dataset.confirmed = '1';
      if (form.requestSubmit) form.requestSubmit(submitter && submitter.form === form ? submitter : undefined);
      else form.submit();
      setTimeout(() => { delete form.dataset.confirmed; }, 0);
    });
  }, true);

  /* Проверка обязательных полей с окном-подсказкой: <form data-validate novalidate> */
  const fieldLabel = (el) => {
    const label = el.closest('.field')?.querySelector(':scope > span, :scope > legend');
    const text = el.dataset.label || (label ? label.firstChild.textContent : el.name) || '';
    return text.replace(/[\s—–-]+$/u, '').trim();
  };

  function formProblems(form) {
    const problems = [];
    form.querySelectorAll('input, textarea, select').forEach((el) => {
      if (el.disabled || el.type === 'hidden' || el.type === 'submit') return;
      const label = fieldLabel(el);
      const value = el.value.trim();
      let msg = '';
      if (el.validity.valueMissing) msg = `${label}: обязательное поле`;
      else if (el.minLength > 0 && value.length > 0 && value.length < el.minLength) msg = `${label}: минимум ${el.minLength} символов`;
      else if (el.validity.patternMismatch) msg = el.dataset.patternMsg || `${label}: неверный формат`;
      else if (el.dataset.match) {
        const other = form.querySelector(`[name="${el.dataset.match}"]`);
        if (other && other.value !== el.value) msg = el.dataset.matchMsg || 'Значения не совпадают';
      }
      if (msg) problems.push({ el, msg });
    });
    return problems;
  }

  function focusField(el) {
    el.closest('.field')?.classList.add('has-error');
    // Для неонового списка фокусируем его кнопку, а не скрытый <select>.
    const target = el.matches('select.vselect-native') ? el.parentElement.querySelector('.vselect-btn') : el;
    target.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'center' });
    target.focus({ preventScroll: true });
  }
  window.VerdictForms = { focusField };

  document.addEventListener('submit', (e) => {
    const form = e.target;
    if (!form.matches('form[data-validate]')) return;
    const problems = formProblems(form);
    if (!problems.length) return;
    e.preventDefault();
    problems.forEach((p) => p.el.closest('.field')?.classList.add('has-error'));
    window.VerdictModal?.alert({
      tone: 'warn',
      title: problems.length === 1 ? 'Проверьте поле' : 'Заполните обязательные поля',
      text: 'Чтобы продолжить, исправьте:',
      items: problems.map((p) => ({ text: p.msg, onClick: () => focusField(p.el) })),
    });
  });

  document.addEventListener('input', (e) => {
    e.target.closest?.('.field.has-error')?.classList.remove('has-error');
  });

  /* Показать / скрыть пароль */
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-pw-toggle]');
    if (!btn) return;
    const input = btn.parentElement.querySelector('input');
    const show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    btn.classList.toggle('on', show);
    btn.setAttribute('aria-label', show ? 'Скрыть пароль' : 'Показать пароль');
  });

  /* Поделиться: <button data-share-link data-share-text data-share-url> — системное меню «Поделиться» или копия в буфер */
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-share-link]');
    if (!btn) return;
    const { shareText: text, shareUrl: url } = btn.dataset;
    if (navigator.share) {
      try { await navigator.share({ title: 'VERDICT', text, url }); return; } catch (_) { /* отменили или нельзя */ }
    }
    const label = btn.querySelector('span') || btn;
    const was = label.textContent;
    try {
      await navigator.clipboard.writeText(`${text} ${url}`);
      label.textContent = 'Ссылка скопирована';
    } catch (_) {
      label.textContent = 'Не удалось скопировать';
    }
    setTimeout(() => { label.textContent = was; }, 1800);
  });

  /* Копировать в буфер: <button data-copy="текст"> (коды из подарков и т. п.) */
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-copy]');
    if (!btn) return;
    const label = btn.querySelector('span') || btn;
    const was = label.textContent;
    try {
      await navigator.clipboard.writeText(btn.dataset.copy);
      label.textContent = 'Скопировано';
    } catch (_) {
      label.textContent = 'Выделите и скопируйте';
    }
    setTimeout(() => { label.textContent = was; }, 1800);
  });

  /* Индикатор надёжности пароля */
  document.querySelectorAll('input[data-strength]').forEach((input) => {
    const bar = input.closest('.field')?.querySelector('.strength');
    if (!bar) return;
    input.addEventListener('input', () => {
      const v = input.value;
      let score = 0;
      if (v.length >= 8) score++;
      if (v.length >= 12) score++;
      if (/[a-zа-яё]/.test(v) && /[A-ZА-ЯЁ]/.test(v)) score++;
      if (/\d/.test(v)) score++;
      if (/[^\p{L}\d]/u.test(v)) score++;
      bar.dataset.level = v ? String(Math.min(4, score)) : '';
    });
  });

  /* Подсветка текущего раздела в боковом меню (создание, бриф) */
  const navLinks = document.querySelectorAll('[data-nav]');
  if (navLinks.length && 'IntersectionObserver' in window) {
    const map = new Map();
    navLinks.forEach((a) => map.set(a.dataset.nav, a));
    const visible = new Set();
    const so = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) visible.add(entry.target.id); else visible.delete(entry.target.id);
      });
      let first = null;
      document.querySelectorAll('[data-section]').forEach((s) => { if (!first && visible.has(s.id)) first = s.id; });
      if (first) navLinks.forEach((a) => a.classList.toggle('active', a.dataset.nav === first));
    }, { rootMargin: '-30% 0px -55% 0px' });
    document.querySelectorAll('[data-section]').forEach((s) => so.observe(s));
  }
})();

/* «Меньше эффектов»: a static background, no blur and no animations — for older phones. */
(() => {
  document.querySelectorAll('[data-fx-toggle]').forEach((btn) => {
    btn.setAttribute('aria-pressed', document.documentElement.dataset.fx === 'lite' ? 'true' : 'false');
    btn.addEventListener('click', () => {
      const lite = document.documentElement.dataset.fx !== 'lite';
      try { localStorage.setItem('verdict:fx', lite ? 'lite' : 'full'); } catch (_) { /* private mode */ }
      window.location.reload();
    });
  });
})();

/* The installable app: the service worker (styles and scripts from the cache, a «Нет связи» page offline) and the
 * «Установить приложение» button where the browser offers installing. */
(() => {
  if ('serviceWorker' in navigator && window.isSecureContext) {
    window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
  }
  const buttons = [...document.querySelectorAll('[data-install]')];
  let offer = null;
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    offer = e;
    buttons.forEach((b) => { b.hidden = false; });
  });
  buttons.forEach((b) => b.addEventListener('click', async () => {
    if (!offer) return;
    offer.prompt();
    await offer.userChoice.catch(() => null);
    offer = null;
    buttons.forEach((x) => { x.hidden = true; });
  }));
  window.addEventListener('appinstalled', () => buttons.forEach((b) => { b.hidden = true; }));
})();
