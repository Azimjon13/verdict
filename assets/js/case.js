/* VERDICT — вынесение вердикта: выбор, удержание кнопки, результат. */
(() => {
  'use strict';

  const form = document.getElementById('verdict');
  const resultBox = document.getElementById('verdict-result');
  if (!form || !resultBox) return;

  const holdBtn = form.querySelector('.hold-btn');
  const holdText = form.querySelector('[data-hold-text]');
  const errorBox = form.querySelector('.form-error');
  const reasoning = form.querySelector('textarea[name="reasoning"]');
  const reasonLabel = form.querySelector('[data-reason-label]');
  const csrf = document.body.dataset.csrf || '';
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const HOLD_MS = reduce ? 450 : 1000;
  const openedAt = performance.now(); // время на решение — для статистики команды
  const defaultHoldText = holdText.textContent;

  const selected = () => form.querySelector('input[name="option"]:checked')?.value || null;

  function showError(msg, title = 'Вердикт не вынесен', tone = 'warn') {
    if (window.VerdictModal) {
      window.VerdictModal.alert({ tone, title, text: msg });
      return;
    }
    errorBox.textContent = msg;
    errorBox.hidden = false;
  }

  /* Выбор варианта */
  form.addEventListener('change', (e) => {
    if (e.target.name !== 'option') return;
    form.querySelectorAll('.option').forEach((o) => o.classList.toggle('is-selected', o.contains(e.target)));
    holdBtn.disabled = false;
    errorBox.hidden = true;
    const other = e.target.value === 'other';
    reasonLabel.innerHTML = other
      ? 'Опишите ваше решение и обоснуйте его <em>(обязательно)</em>'
      : 'Почему вы выбрали это решение? <em>(необязательно)</em>';
    if (other) reasoning.focus();
  });

  /* Удержание кнопки */
  let holding = false, sending = false, startAt = 0, raf = 0, timer = 0;
  const setProgress = (p) => holdBtn.style.setProperty('--p', p);

  function complete() {
    if (!holding) return;
    holding = false;
    cancelAnimationFrame(raf);
    clearTimeout(timer);
    setProgress(1);
    holdBtn.classList.remove('holding');
    window.Juice?.strike(holdBtn);
    submit();
  }

  function begin() {
    if (holdBtn.disabled || sending || holding) return;
    if (selected() === 'other' && reasoning.value.trim().length < 10) {
      showError('Вы выбрали «Другое решение». Опишите его и обоснуйте — хотя бы одним предложением.', 'Опишите своё решение');
      reasoning.closest('.field')?.classList.add('has-error');
      return;
    }
    holding = true;
    startAt = performance.now();
    holdBtn.classList.add('holding');
    holdText.textContent = 'Держите…';
    // Таймер решает, когда удержание засчитано; кадры анимации только рисуют заполнение.
    timer = setTimeout(complete, HOLD_MS);
    const tick = (now) => {
      if (!holding) return;
      setProgress(Math.max(0, Math.min(1, (now - startAt) / HOLD_MS)));
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
  }

  function cancel() {
    if (!holding) return;
    holding = false;
    clearTimeout(timer);
    cancelAnimationFrame(raf);
    holdBtn.classList.remove('holding');
    holdText.textContent = defaultHoldText;
    setProgress(0);
  }

  holdBtn.addEventListener('pointerdown', (e) => {
    if (e.button !== undefined && e.button !== 0) return;
    e.preventDefault();
    try { holdBtn.setPointerCapture(e.pointerId); } catch (_) { /* noop */ }
    begin();
  });
  ['pointerup', 'pointercancel', 'lostpointercapture'].forEach((ev) => holdBtn.addEventListener(ev, cancel));
  holdBtn.addEventListener('contextmenu', (e) => e.preventDefault());
  holdBtn.addEventListener('keydown', (e) => {
    if ((e.key === 'Enter' || e.key === ' ') && !e.repeat) { e.preventDefault(); begin(); }
  });
  holdBtn.addEventListener('keyup', (e) => {
    if (e.key === 'Enter' || e.key === ' ') cancel();
  });

  /* Отправка */
  async function submit() {
    sending = true;
    holdBtn.classList.add('sending');
    holdText.textContent = 'Вердикт выносится…';
    const body = new FormData(form);
    body.append('_csrf', csrf);
    body.append('duration_ms', String(Math.round(performance.now() - openedAt)));
    try {
      const res = await fetch(document.body.dataset.voteUrl || 'api/vote.php', {
        method: 'POST',
        body,
        headers: { Accept: 'application/json', 'X-CSRF-Token': csrf },
        credentials: 'same-origin',
      });
      let data = null;
      try { data = await res.json(); } catch (_) { /* не JSON */ }
      if (!res.ok || !data || !data.ok) throw new Error(data?.error || 'Не удалось сохранить вердикт. Попробуйте ещё раз.');

      window.VerdictFX?.boost(1);
      document.body.classList.remove('shockwave-flash');
      void document.body.offsetWidth;
      document.body.classList.add('shockwave-flash');
      setTimeout(() => document.body.classList.remove('shockwave-flash'), 900);

      resultBox.innerHTML = data.html;
      form.hidden = true;
      if (!data.preview) updateWorld(data.world);
      bindResult(true);
      window.Juice?.result(resultBox, 'full');
    } catch (err) {
      showError(err.message, 'Не удалось вынести вердикт', 'danger');
    } finally {
      sending = false;
      holdBtn.classList.remove('sending');
      holdText.textContent = defaultHoldText;
      setProgress(0);
    }
  }

  /* Состояние мира */
  function updateWorld(world) {
    if (!world) return;
    const panel = document.querySelector('[data-world]');
    if (!panel) return;
    const count = panel.querySelector('[data-world-count]');
    const word = panel.querySelector('[data-world-word]');
    if (count) count.textContent = world.count;
    if (word) word.textContent = world.word;
    Object.entries(world.metrics || {}).forEach(([key, value]) => {
      const meter = panel.querySelector(`[data-metric="${key}"]`);
      if (!meter) return;
      meter.querySelector('.meter-bar i').style.width = `${value}%`;
      meter.querySelector('[data-value]').textContent = value;
      const delta = meter.querySelector('[data-delta]');
      const d = (world.deltas || {})[key];
      if (d) {
        delta.textContent = d > 0 ? `+${d}` : `${d}`;
        delta.className = `meter-delta show ${d > 0 ? 'up' : 'down'}`;
        meter.classList.remove('flash');
        void meter.offsetWidth;
        meter.classList.add('flash');
        setTimeout(() => delta.classList.remove('show'), 4500);
      }
    });
  }

  /* Результат */
  function bindResult(fresh) {
    const result = resultBox.querySelector('#result');
    if (!result) return;

    if (fresh) {
      requestAnimationFrame(() => requestAnimationFrame(() => result.classList.add('animated')));
      setTimeout(() => {
        result.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
        result.focus({ preventScroll: true });
      }, 60);
    }

    result.querySelector('[data-revisit]')?.addEventListener('click', () => {
      form.hidden = false;
      form.classList.add('in');
      form.querySelectorAll('input[name="option"]').forEach((i) => { i.checked = false; });
      form.querySelectorAll('.option').forEach((o) => o.classList.remove('is-selected'));
      holdBtn.disabled = true;
      reasoning.value = '';
      result.remove();
      form.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
    });

    const share = result.querySelector('[data-share]');
    share?.addEventListener('click', async () => {
      const url = new URL(share.dataset.shareUrl, window.location.href).href;
      const text = share.dataset.shareText;
      try {
        if (navigator.share) {
          await navigator.share({ title: 'VERDICT', text, url });
          return;
        }
        await navigator.clipboard.writeText(`${text} ${url}`);
        const label = share.lastChild;
        const prev = label.textContent;
        label.textContent = 'Скопировано!';
        setTimeout(() => { label.textContent = prev; }, 2000);
      } catch (_) { /* отменено пользователем */ }
    });
  }

  bindResult(false);
})();
