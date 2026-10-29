/* Team edits a case with votes: deleting a decision that has votes asks first; new rows delete silently. */
(async () => {
  const st = JSON.parse(sessionStorage.getItem('e2e') || '{"stage":0,"out":[]}');
  const ok = (label, cond, extra = '') => st.out.push((cond ? 'PASS ' : 'FAIL ') + label + (extra !== '' ? '  [' + extra + ']' : ''));
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const persist = () => sessionStorage.setItem('e2e', JSON.stringify(st));
  const finish = () => { persist(); fetch('/__report', { method: 'POST', body: st.out.join('\n') }); };
  const modalTitle = () => document.querySelector('.modal-root:not([hidden]) .modal-title')?.textContent || '';
  try {
    await wait(400);
    if (st.stage === 0) { // /login?back=/create/1
      const form = document.querySelector('form[data-validate]');
      form.elements.login.value = 'admin';
      form.elements.password.value = 'verdict-admin';
      st.stage = 1; persist();
      form.querySelector('button[type="submit"]').click();
      return;
    }
    if (st.stage === 1) { // /create/1
      const rows = () => [...document.querySelectorAll('[data-repeater="decisions"] > .rep-list > .rep-item')];
      const voted = rows().find((r) => r.dataset.votes);
      ok('editor opened with vote counts', /\/create\/1$/.test(location.href) && !!voted && !!voted.querySelector('.rep-votes'), location.href);
      ok('every row has a hidden uid', rows().every((r) => r.querySelector('input[name$="[uid]"]')?.value));
      const before = rows().length;

      voted.querySelector('.rep-remove').click();
      await wait(250);
      ok('removing a voted decision asks first', modalTitle() === 'Удалить вариант с голосами?', modalTitle());
      ok('...and says how many players chose it', /уже выбрали \d+ игрок/.test(document.querySelector('.modal-root .modal-text')?.textContent || ''));
      document.querySelector('.modal-root [data-cancel]').click();
      await wait(350);
      ok('"Оставить" keeps the row', rows().length === before && voted.isConnected);

      voted.querySelector('.rep-remove').click();
      await wait(250);
      document.querySelector('.modal-root [data-ok]').click();
      await wait(350);
      ok('"Удалить вариант" removes it', rows().length === before - 1 && !voted.isConnected);
      ok('letters re-flow after removal', rows().map((r) => r.querySelector('.rep-letter').textContent).join('') === 'ABCDEFGH'.slice(0, before - 1));

      document.querySelector('[data-repeater="decisions"] > .rep-add').click();
      const fresh = rows().at(-1);
      ok('new row has an empty uid (server assigns one)', fresh.querySelector('input[name$="[uid]"]').value === '');
      fresh.querySelector('.rep-remove').click();
      await wait(250);
      ok('new row without votes is removed without asking', !fresh.isConnected && !modalTitle(), modalTitle());
      finish();
    }
  } catch (e) {
    st.out.push('ERROR ' + e.message + ' @stage ' + st.stage);
    finish();
  }
})();
