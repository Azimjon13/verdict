/* VERDICT — «Быстрый суд»: вердикт → догадка о большинстве → результат. */
(() => {
  'use strict';

  const root = document.querySelector('[data-quick]');
  const resultBox = document.querySelector('[data-quick-result]');
  if (!root || !resultBox) return;

  const openedAt = performance.now();
  const csrf = document.body.dataset.csrf || '';
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const step1 = root.querySelector('[data-step="1"]');
  const step2 = root.querySelector('[data-step="2"]');
  const pickedText = root.querySelector('[data-picked-text]');
  let pick = null;
  let sending = false;

  function showStep(n) {
    step1.hidden = n !== 1;
    step2.hidden = n !== 2;
    const step = n === 2 ? step2 : step1;
    const selected = step.querySelector('.is-selected') || step.querySelector('.quick-option');
    selected?.focus({ preventScroll: true });
    if (step.getBoundingClientRect().top < 80) step.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
  }

  function choose(btn) {
    pick = btn.dataset.pick;
    root.querySelectorAll('[data-pick]').forEach((b) => b.classList.toggle('is-selected', b === btn));
    pickedText.textContent = `${pick} — ${btn.querySelector('.opt-text').textContent}`;
    showStep(2);
  }

  async function submit(guess) {
    if (!pick || sending) return;
    sending = true;
    root.classList.add('is-sending');
    const body = new FormData();
    body.append('_csrf', csrf);
    body.append('situation_id', root.dataset.situation);
    body.append('option', pick);
    body.append('guess', guess);
    body.append('mode', 'quick');
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
      root.hidden = true;
      resultBox.innerHTML = data.html;
      const result = resultBox.querySelector('#quick-result');
      if (result) {
        result.classList.add('is-fresh');
        requestAnimationFrame(() => requestAnimationFrame(() => result.classList.add('animated')));
        result.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
        result.querySelector('[data-quick-next]')?.focus({ preventScroll: true });
      }
    } catch (err) {
      if (window.VerdictModal) window.VerdictModal.alert({ tone: 'danger', title: 'Не удалось вынести вердикт', text: err.message });
    } finally {
      sending = false;
      root.classList.remove('is-sending');
    }
  }

  root.addEventListener('click', (e) => {
    const p = e.target.closest('[data-pick]');
    if (p) { choose(p); return; }
    const g = e.target.closest('[data-guess]');
    if (g) { submit(g.dataset.guess); return; }
    if (e.target.closest('[data-repick]')) showStep(1);
  });

  /* Клавиши 1–9 выбирают вариант на текущем шаге, Esc возвращает к вердикту. */
  document.addEventListener('keydown', (e) => {
    if (root.hidden || e.ctrlKey || e.metaKey || e.altKey || e.target.closest?.('input, textarea, select')) return;
    if (window.VerdictModal?.isOpen()) return;
    if (e.key === 'Escape' && !step2.hidden) {
      showStep(1);
      return;
    }
    const n = parseInt(e.key, 10);
    if (!n) return;
    const btn = (step2.hidden ? step1 : step2).querySelectorAll('.quick-option')[n - 1];
    if (btn) {
      e.preventDefault();
      btn.click();
    }
  });
})();
