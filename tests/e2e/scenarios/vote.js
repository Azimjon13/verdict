/* Plays cases with the real hold-to-confirm button. */
(async () => {
  const st = JSON.parse(sessionStorage.getItem('e2e') || '{"stage":0,"out":[]}');
  const ok = (label, cond, extra = '') => st.out.push((cond ? 'PASS ' : 'FAIL ') + label + (extra !== '' ? '  [' + extra + ']' : ''));
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const persist = () => sessionStorage.setItem('e2e', JSON.stringify(st));
  const finish = () => { persist(); fetch('/__report', { method: 'POST', body: st.out.join('\n') }); };
  const modalTitle = () => document.querySelector('.modal-root:not([hidden]) .modal-title')?.textContent || '';
  const closeModal = () => document.querySelector('.modal-root:not([hidden]) [data-ok]')?.click();
  const hold = async (btn, ms) => {
    btn.dispatchEvent(new PointerEvent('pointerdown', { button: 0, pointerId: 1, bubbles: true, cancelable: true }));
    await wait(ms);
    btn.dispatchEvent(new PointerEvent('pointerup', { button: 0, pointerId: 1, bubbles: true }));
  };
  try {
    await wait(300);
    if (st.stage === 0) {
      const form = document.getElementById('verdict');
      const btn = form.querySelector('.hold-btn');
      ok('verdict form shown', form && !form.hidden);
      ok('hold button disabled before choosing', btn.disabled);
      form.querySelector('input[name="option"][value="B"]').click();
      ok('choosing an option enables it', !btn.disabled);

      await hold(btn, 300);
      await wait(500);
      ok('short press does NOT vote', !document.getElementById('result'));

      await hold(btn, 1200);
      await wait(800);
      const result = document.getElementById('result');
      ok('holding 1s votes and shows the result', !!result && form.hidden);
      ok('result shows chosen decision', result?.querySelector('.dist-row.is-mine .opt-letter')?.textContent.trim() === 'B');
      ok('world panel counter updated', document.querySelector('[data-world-count]')?.textContent === '1');

      result.querySelector('[data-revisit]').click();
      await wait(200);
      ok('"Пересмотреть" reopens the form', !form.hidden && btn.disabled);

      form.querySelector('input[name="option"][value="other"]').click();
      await hold(btn, 1200);
      await wait(300);
      ok('"other" without reasoning is stopped', /Опишите своё решение/.test(modalTitle()), modalTitle());
      closeModal();
      await wait(300);
      form.querySelector('textarea[name="reasoning"]').value = 'Созвать общий совет и решить вместе.';
      await hold(btn, 1200);
      await wait(800);
      ok('"other" with reasoning is accepted', /Другое решение/.test(document.querySelector('#result .result-choice h2')?.textContent || ''));
      const next = document.querySelector('#result .result-actions a.btn-primary');
      ok('"next case" link present', !!next && /^\/case\/\d+$/.test(next.getAttribute('href')));
      st.stage = 1;
      st.from = location.pathname;
      persist();
      next.click();
      return;
    }
    if (st.stage === 1) {
      ok('next case opened', /^\/case\//.test(location.pathname) && location.pathname !== st.from && !!document.getElementById('verdict'));
      st.stage = 2;
      persist();
      location.href = st.from;
      return;
    }
    if (st.stage === 2) {
      ok('revisiting shows my saved verdict', !!document.getElementById('result') && document.getElementById('verdict').hidden);
      finish();
    }
  } catch (e) {
    st.out.push('ERROR ' + e.message);
    finish();
  }
})();
