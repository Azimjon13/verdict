/* Registers through the real form, saves a level-1 idea, completes level 2 and submits it. */
(async () => {
  const st = JSON.parse(sessionStorage.getItem('e2e') || '{"stage":0,"out":[]}');
  const ok = (label, cond, extra = '') => st.out.push((cond ? 'PASS ' : 'FAIL ') + label + (extra !== '' ? '  [' + extra + ']' : ''));
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const persist = () => sessionStorage.setItem('e2e', JSON.stringify(st));
  const finish = () => { persist(); fetch('/__report', { method: 'POST', body: st.out.join('\n') }); };
  const type = (el, v) => { el.focus(); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
  const toast = () => [...document.querySelectorAll('.toast span')].map((s) => s.textContent).join(' | ');
  const f = () => document.querySelector('[data-create-form]');
  const rows = (k) => f().querySelectorAll(`[data-repeater="${k}"] > .rep-list > .rep-item`);
  try {
    await wait(300);
    if (st.stage === 0) { // /register
      const form = document.querySelector('form[data-validate]');
      type(form.elements.login, 'e2e' + Date.now().toString(36));
      type(form.elements.display_name, 'Браузерный автор');
      type(form.elements.password, 'password123');
      type(form.elements.password_confirm, 'password123');
      st.stage = 1; persist();
      form.querySelector('button[type="submit"]').click();
      return;
    }
    if (st.stage === 1) { // /create, level 1
      ok('registration form → create page', location.pathname === '/create' && !!f());
      ok('opens on level 1', document.querySelector('[data-level]').dataset.level === '1');
      f().querySelector('input[name="category"][value="family"]').click();
      type(f().elements.title, 'Чужое письмо');
      type(f().elements.story, 'Староста нашёл письмо, в котором сосед договаривается продать общий колодец купцам. Сосед говорит, что письмо подделали, а купцы уже ждут ответа у ворот деревни.');
      type(rows('decisions')[0].querySelector('input[name$="[text]"]'), 'Поверить соседу');
      type(rows('decisions')[1].querySelector('input[name$="[text]"]'), 'Изгнать соседа');
      await wait(1000);
      ok('level 1 marked done while typing', document.querySelector('[data-level-tab="1"]').classList.contains('is-done'));
      ok('autosave copy exists', Object.keys(localStorage).some((k) => k.startsWith('verdict:create:')));
      st.stage = 2; persist();
      f().querySelector('[data-intent-value="draft"]').click();
      return;
    }
    if (st.stage === 2) { // /create/<id> after the draft is saved
      ok('draft saved → back in the editor', /\/create\/\d+$/.test(location.href), location.href);
      ok('toast confirms level 1', /готов уровень 1 из 3/.test(toast()), toast());
      ok('browser copy cleared after server save', !Object.keys(localStorage).some((k) => k.endsWith(':new')));
      ok('reopens on level 2', document.querySelector('[data-level]').dataset.level === '2');
      ok('typed text kept', f().elements.title.value === 'Чужое письмо' && rows('decisions')[1].querySelector('input[name$="[text]"]').value === 'Изгнать соседа');
      ok('decision rows padded to 4', rows('decisions').length === 4, rows('decisions').length);
      // Level 2.
      type(f().elements['world[place]'], 'Деревня у старого колодца');
      type(f().elements['world[circumstances]'], 'Засуха третий год. Колодец — единственная вода.');
      type(f().elements.story, f().elements.story.value + ' Половина деревни верит соседу, половина требует суда, а купцы обещают зерно в обмен на воду до конца этой недели.');
      type(rows('participants')[0].querySelector('input[name$="[name]"]'), 'Тарас');
      type(rows('facts')[0].querySelector('textarea'), 'Письмо написано почерком соседа');
      type(rows('decisions')[2].querySelector('input[name$="[text]"]'), 'Созвать сход');
      type(rows('decisions')[3].querySelector('input[name$="[text]"]'), 'Отдать письмо купцам');
      type(f().elements['ambiguity[conflict]'], 'Доверие к соседу против выживания деревни');
      await wait(1000);
      ok('level 2 marked done', document.querySelector('[data-level-tab="2"]').classList.contains('is-done'),
        document.querySelector('[data-level-tab="2"] [data-level-state]').textContent.trim());
      st.stage = 3; persist();
      f().querySelector('[data-intent-value="submit"]').click();
      return;
    }
    if (st.stage === 3) { // /view/<id>
      ok('submitted → dossier page', /\/view\/\d+$/.test(location.href), location.href);
      ok('status is "На отборе"', !!document.querySelector('.status-pending'));
      ok('level badge "Ур. 2"', /Ур\. 2/.test(document.querySelector('.chip-level')?.textContent || ''));
      ok('content saved', document.body.textContent.includes('Деревня у старого колодца') && document.body.textContent.includes('Отдать письмо купцам'));
      ok('no browser copies left', !Object.keys(localStorage).some((k) => k.startsWith('verdict:create:')), Object.keys(localStorage).join());
      finish();
    }
  } catch (e) {
    st.out.push('ERROR ' + e.message + ' @stage ' + st.stage);
    finish();
  }
})();
