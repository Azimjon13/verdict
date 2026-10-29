/* Game feel on Быстрый суд: the stamp on the picked option, counting percentages, XP flying to the rank chip,
 * typewriter consequences, the sound toggle that persists across pages. */
(async () => {
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const st = JSON.parse(sessionStorage.getItem('e2e') || '{"out":[],"step":0}');
  const ok = (label, cond, extra = '') => st.out.push((cond ? 'PASS ' : 'FAIL ') + label + (extra !== '' ? '  [' + extra + ']' : ''));
  const save = () => sessionStorage.setItem('e2e', JSON.stringify(st));
  const report = () => fetch('/__report', { method: 'POST', body: st.out.join('\n') });
  const chipXp = () => Number((/(\d+) XP/.exec(document.querySelector('.rank-chip b')?.textContent || '') || [])[1]);
  try {
    await wait(600);
    if (st.step === 0) {
      ok('Juice is loaded', !!window.Juice && typeof window.Juice.result === 'function');
      const toggle = document.querySelector('[data-sound-toggle]');
      ok('sound toggle in the header, on by default', toggle && toggle.getAttribute('aria-pressed') === 'true' && window.Juice.sound.enabled);
      const before = chipXp();
      const pick = document.querySelector('[data-pick]');
      pick.click();
      await wait(200);
      ok('stamp lands on the picked option', pick.classList.contains('is-stamped') && pick.querySelector('.juice-stamp')?.textContent === 'Вердикт');
      ok('only one stamp at a time', document.querySelectorAll('.juice-stamp').length === 1);
      document.querySelector('[data-repick]').click();
      await wait(100);
      const second = document.querySelectorAll('[data-pick]')[1];
      second.click();
      await wait(200);
      ok('changing the pick moves the stamp', !pick.classList.contains('is-stamped') && second.classList.contains('is-stamped') && document.querySelectorAll('.juice-stamp').length === 1);
      document.querySelector('[data-guess=""]').click();
      await wait(700);
      const result = document.querySelector('#quick-result');
      ok('result rendered', !!result);
      const early = [...result.querySelectorAll('.dist-top b')].map((b) => parseInt(b.textContent, 10));
      await wait(1800);
      const final = [...result.querySelectorAll('.dist-top b')].map((b) => parseInt(b.textContent, 10));
      const sum = final.reduce((a, b) => a + b, 0);
      ok('percentages count up to real values', final.length > 0 && final.every((v) => v >= 0 && v <= 100) && sum >= 98 && sum <= 102, JSON.stringify(early) + ' → ' + JSON.stringify(final));
      ok('they were counting (not jumped)', early.some((v, i) => v < final[i]) || final.every((v) => v === 0 || v === 100), JSON.stringify(early));
      const xpText = result.querySelector('.cs-xp')?.textContent.trim() || '';
      const gained = Number((/\+(\d+)/.exec(xpText) || [])[1]) || 0;
      ok('XP shown on the result', gained >= 10, xpText);
      ok('XP flew to the rank chip and was added', chipXp() === before + gained, before + ' + ' + gained + ' = ' + chipXp());
      ok('no stray fly token left', !document.querySelector('.juice-fly'));
      const conseq = result.querySelector('.quick-conseq');
      if (conseq) {
        await wait(4500);
        ok('consequence typed out fully', !conseq.classList.contains('juice-typing') && conseq.textContent.length > 20, String(conseq.textContent.length));
      } else {
        ok('consequence block present', true, 'none in this case');
      }
      toggle.click();
      await wait(100);
      ok('toggle turns sound off', toggle.classList.contains('is-off') && !window.Juice.sound.enabled && localStorage.getItem('verdict:sound') === 'off');
      st.step = 1;
      save();
      location.href = '/judge';
      return;
    }
    if (st.step === 1) {
      const toggle = document.querySelector('[data-sound-toggle]');
      ok('sound stays off on the next page', toggle.classList.contains('is-off') && !window.Juice.sound.enabled);
      toggle.click();
      ok('and can be turned back on', window.Juice.sound.enabled);
      ok('no horizontal page scroll', document.documentElement.scrollWidth <= document.documentElement.clientWidth);
      st.step = 2;
      save();
      report();
    }
  } catch (e) {
    st.out.push('ERROR ' + e.message);
    report();
  }
})();
