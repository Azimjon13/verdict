/* Plays «Быстрый суд» in the browser: clicks, keyboard, change of mind, next case. */
(async () => {
  const st = JSON.parse(sessionStorage.getItem('e2e') || '{"stage":0,"out":[]}');
  const ok = (label, cond, extra = '') => st.out.push((cond ? 'PASS ' : 'FAIL ') + label + (extra !== '' ? '  [' + extra + ']' : ''));
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const persist = () => sessionStorage.setItem('e2e', JSON.stringify(st));
  const finish = () => { persist(); fetch('/__report', { method: 'POST', body: st.out.join('\n') }); };
  const shown = (el) => !!el && el.offsetParent !== null;
  const key = (k) => document.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true }));
  try {
    await wait(400);
    const root = document.querySelector('[data-quick]');
    const step1 = root?.querySelector('[data-step="1"]');
    const step2 = root?.querySelector('[data-step="2"]');
    if (st.stage === 0) {
      ok('quick page shows a case', !!root && shown(step1) && !shown(step2));
      ok('comic shown above the verdict', !!document.querySelector('[data-comic].is-ready'));

      // Click A, change mind, pick B with keyboard.
      step1.querySelector('[data-pick="A"]').click();
      ok('picking a verdict shows the guess step', !shown(step1) && shown(step2));
      ok('chosen verdict echoed', /^A — /.test(root.querySelector('[data-picked-text]').textContent));
      root.querySelector('[data-repick]').click();
      ok('"изменить" goes back', shown(step1) && step1.querySelector('[data-pick="A"]').classList.contains('is-selected'));
      key('2');
      ok('key 2 picks option B', shown(step2) && /^B — /.test(root.querySelector('[data-picked-text]').textContent));
      key('Escape');
      ok('Esc goes back', shown(step1));
      key('2');
      key('1'); // guess A
      await wait(1200);
      const result = document.querySelector('#quick-result');
      ok('guess submits and reveals the result', !!result && root.hidden);
      ok('banner explains the guess', !!result?.querySelector('.guess-banner h2')?.textContent);
      ok('my verdict is B', result?.querySelector('.dist-row.is-mine .opt-letter')?.textContent.trim() === 'B');
      ok('my guess is marked', !!result?.querySelector('.em-guess'));
      ok('bars animated in', result?.classList.contains('animated'));
      ok('"Следующее дело" focused', document.activeElement === result?.querySelector('[data-quick-next]'));
      st.stage = 1;
      st.first = root.dataset.situation;
      persist();
      result.querySelector('[data-quick-next]').click();
      return;
    }
    if (st.stage === 1) {
      ok('next case is a different one', !!root && root.dataset.situation !== st.first, `${st.first} → ${root?.dataset.situation}`);
      ok('header counter went up', /Рассмотрено\s*1/.test(document.querySelector('.quick-stats').textContent));
      // Skip the guess this time.
      step1.querySelector('.quick-option').click();
      root.querySelector('.quick-skip').click();
      await wait(1200);
      ok('skipping the guess still reveals', /Вы не угадывали|Вы первый судья/.test(document.querySelector('.guess-banner h2')?.textContent || ''));
      st.stage = 2;
      persist();
      location.href = '/quick/' + st.first;
      return;
    }
    if (st.stage === 2) {
      ok('revisiting a judged case shows its result', !!document.querySelector('#quick-result') && document.querySelector('[data-quick]').hidden);
      finish();
    }
  } catch (e) {
    st.out.push('ERROR ' + e.message + ' @stage ' + st.stage);
    finish();
  }
})();
