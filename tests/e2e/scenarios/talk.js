/* Discussion under a case: judge it in Быстрый суд, open the discussion from the result, write a comment, see it
 * marked as one's own and the result screen quoting it. */
(async () => {
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const st = JSON.parse(sessionStorage.getItem('e2e') || '{"out":[],"step":0}');
  const ok = (label, cond, extra = '') => st.out.push((cond ? 'PASS ' : 'FAIL ') + label + (extra !== '' ? '  [' + extra + ']' : ''));
  const save = () => sessionStorage.setItem('e2e', JSON.stringify(st));
  const report = () => fetch('/__report', { method: 'POST', body: st.out.join('\n') });
  const text = 'Выбираю A: правило одно для всех — иначе завтра его нарушит любой. ' + Date.now().toString(36);
  try {
    await wait(700);
    if (st.step === 0 && location.pathname === '/quick/7') {
      document.querySelector('[data-pick="A"]').click();
      await wait(200);
      document.querySelector('.quick-skip').click();
      await wait(1500);
      const teaser = document.querySelector('#quick-result .talk-teaser');
      ok('the result invites to the discussion', !!teaser && /пока никто не высказался/.test(teaser.textContent), teaser && teaser.textContent.trim().slice(0, 80));
      const link = teaser.querySelector('a[href="/talk/7"]');
      ok('…with a way in', !!link && /Начать спор/.test(link.textContent));
      st.step = 1;
      st.text = text;
      save();
      link.click();
      return;
    }
    if (st.step === 1 && location.pathname === '/talk/7') {
      ok('the discussion shows my verdict', /Ваш вердикт:\s*A/.test(document.querySelector('.talk-mine')?.textContent || ''));
      ok('nobody has written yet', !document.querySelector('.talk-item') && !!document.querySelector('.empty'));
      const area = document.querySelector('.talk-form textarea');
      area.value = st.text;
      area.dispatchEvent(new Event('input', { bubbles: true }));
      st.step = 2;
      save();
      document.querySelector('.talk-form').requestSubmit();
      return;
    }
    if (st.step === 2 && location.pathname === '/talk/7') {
      const mine = document.querySelector('.talk-item.is-mine');
      ok('the comment is there, as mine', !!mine && mine.textContent.includes(st.text));
      ok('the page jumped to it', !!mine && location.hash === '#' + mine.id && mine.matches(':target'), location.hash);
      ok('it carries my verdict', mine?.querySelector('.talk-verdict .opt-letter')?.textContent.trim() === 'A');
      ok('no backing my own comment', !mine?.querySelector('button.talk-like'));
      ok('a toast confirms it', /опубликован/.test([...document.querySelectorAll('.toast span')].map((s) => s.textContent).join(' ')));
      ok('no horizontal page scroll', document.documentElement.scrollWidth <= document.documentElement.clientWidth);
      st.step = 3;
      save();
      location.href = '/quick/7';
      return;
    }
    if (st.step === 3 && location.pathname === '/quick/7') {
      const teaser = document.querySelector('#quick-result .talk-teaser');
      ok('the result quotes the comment now', !!teaser && teaser.textContent.includes(st.text.slice(0, 40)) && /1 комментарий/.test(teaser.textContent),
        teaser && teaser.textContent.trim().replace(/\s+/g, ' ').slice(0, 120));
      report();
    }
  } catch (e) {
    st.out.push('ERROR ' + e.message);
    report();
  }
})();
