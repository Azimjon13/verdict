/* VERDICT — форма «Создать ситуацию». */
(() => {
  'use strict';

  const form = document.querySelector('[data-create-form]');
  if (!form) return;

  // Уровень заполнения (1 Идея, 2 Дело, 3 Досье) задаёт, какие разделы видны: data-lvl / data-lvl-only.
  const layout = form.closest('[data-level]') || form;
  const levelOf = () => parseInt(layout.dataset.level, 10) || 3;

  /* ---------- Повторяющиеся блоки ---------- */

  function refresh(rep) {
    const items = rep.querySelectorAll(':scope > .rep-list > .rep-item');
    const min = parseInt(rep.dataset.min, 10) || 0;
    const max = parseInt(rep.dataset.max, 10) || 99;
    items.forEach((item, i) => {
      const num = item.querySelector('.rep-num');
      if (num) num.textContent = i + 1;
      const letter = item.querySelector('.rep-letter');
      if (letter) letter.textContent = String.fromCharCode(65 + i);
    });
    rep.classList.toggle('at-min', items.length <= min);
    const add = rep.querySelector(':scope > .rep-add');
    if (add) add.disabled = items.length >= max;
  }

  function addItem(rep, focus = true) {
    const tpl = rep.querySelector(':scope > template');
    const list = rep.querySelector(':scope > .rep-list');
    const next = parseInt(rep.dataset.next, 10) || 0;
    rep.dataset.next = next + 1;
    const wrap = document.createElement('div');
    wrap.innerHTML = tpl.innerHTML.replaceAll('__i__', `n${next}`);
    const item = wrap.firstElementChild;
    list.appendChild(item);
    refresh(rep);
    syncWitnesses();
    if (focus) {
      item.querySelector('input, textarea')?.focus();
      markDirty();
    }
  }

  document.querySelectorAll('.repeater').forEach((rep) => {
    refresh(rep);
    rep.querySelector(':scope > .rep-add')?.addEventListener('click', () => addItem(rep));
  });

  const votesWord = (n) => {
    const n10 = n % 10;
    const n100 = n % 100;
    if (n10 === 1 && n100 !== 11) return 'игрок';
    return n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14) ? 'игрока' : 'игроков';
  };

  form.addEventListener('click', async (e) => {
    const btn = e.target.closest('.rep-remove');
    if (!btn) return;
    const rep = btn.closest('.repeater');
    const item = btn.closest('.rep-item');
    const min = parseInt(rep.dataset.min, 10) || 0;
    if (rep.querySelectorAll(':scope > .rep-list > .rep-item').length <= min) return;
    // За этот вариант уже голосовали — удаление сотрёт их голоса после сохранения.
    const votes = parseInt(item.dataset.votes, 10) || 0;
    if (votes > 0 && window.VerdictModal) {
      const ok = await window.VerdictModal.confirm({
        tone: 'danger',
        title: 'Удалить вариант с голосами?',
        text: `Этот вариант уже выбрали ${votes} ${votesWord(votes)}. После сохранения их голоса будут удалены. Голоса за остальные варианты останутся при своих вариантах, даже если сменятся буквы.`,
        ok: 'Удалить вариант',
        cancel: 'Оставить',
      });
      if (!ok || !item.isConnected) return;
    }
    item.remove();
    refresh(rep);
    markDirty();
  });

  /* ---------- Свидетели зависят от типа ---------- */

  const witnessSection = form.querySelector('[data-witness-section]');
  const witnessRep = witnessSection?.querySelector('.repeater');

  function syncWitnesses() {
    if (!witnessSection) return;
    const type = form.querySelector('[data-type-input]:checked')?.value || 'private';
    const isPrivate = type === 'private';
    witnessSection.classList.toggle('is-disabled', isPrivate);
    witnessSection.querySelectorAll('.witness-fields input, .witness-fields textarea').forEach((el) => { el.disabled = isPrivate; });
    if (witnessRep) {
      witnessRep.dataset.max = type === 'witness' ? 5 : 8;
      refresh(witnessRep);
    }
  }
  form.querySelectorAll('[data-type-input]').forEach((r) => r.addEventListener('change', syncWitnesses));
  syncWitnesses();

  /* ---------- Продолжение ---------- */

  const contText = form.querySelector('[data-cont-text]');
  function syncCont() {
    if (contText) contText.hidden = form.querySelector('[data-cont-input]:checked')?.value !== 'yes';
  }
  form.querySelectorAll('[data-cont-input]').forEach((r) => r.addEventListener('change', syncCont));

  /* ---------- Счётчики слов и предложений ---------- */

  const countWords = (s) => (s.match(/[\p{L}\p{N}]+(?:['’-][\p{L}\p{N}]+)*/gu) || []).length;
  const countSentences = (s) => (s.trim() ? s.split(/[.!?…]+(?:\s|$)/u).filter((x) => x.trim()).length : 0);

  const counters = [];
  form.querySelectorAll('[data-counter]').forEach((ta) => {
    const field = ta.closest('.field');
    const out = field.querySelector('[data-counter-out]');
    const bar = field.querySelector('.counter-bar');
    const words = ta.dataset.counter === 'words';
    const update = () => {
      // На уровне «Идея» у завязки свой, короткий объём (data-range-idea="20-80").
      const idea = levelOf() === 1 && ta.dataset.rangeIdea;
      const [min, max] = idea ? ta.dataset.rangeIdea.split('-').map(Number) : [parseInt(ta.dataset.min, 10), parseInt(ta.dataset.max, 10)];
      const n = words ? countWords(ta.value) : countSentences(ta.value);
      const ok = n >= min && n <= max;
      const unit = words ? 'слов' : 'предложений';
      let msg = `${n} ${unit} · ${idea ? 'для идеи хватит' : 'рекомендуемый объём:'} ${min}–${max}`;
      if (n > max) msg += ' — попробуйте сократить';
      out.textContent = msg;
      out.classList.toggle('ok', ok);
      out.classList.toggle('warn', n > 0 && !ok);
      if (bar) {
        bar.classList.toggle('ok', ok);
        bar.querySelector('i').style.width = `${Math.min(100, (n / max) * 100)}%`;
      }
    };
    ta.addEventListener('input', update);
    counters.push(update);
  });

  /* ---------- Ползунки влияния ---------- */

  form.addEventListener('input', (e) => {
    if (e.target.type !== 'range') return;
    const out = e.target.parentElement.querySelector('.effect-out');
    const v = parseInt(e.target.value, 10);
    out.textContent = v > 0 ? `+${v}` : `${v}`;
    out.className = `effect-out ${v > 0 ? 'up' : v < 0 ? 'down' : ''}`;
  });

  /* ---------- Быстрая проверка ---------- */

  const ring = form.querySelector('[data-check-ring]');
  const checks = form.querySelectorAll('input[name="checklist[]"]');
  function updateRing() {
    const done = [...checks].filter((c) => c.checked).length;
    if (!ring) return;
    ring.querySelector('[data-check-count]').textContent = done;
    ring.querySelector('.ring-fill').style.strokeDasharray = `${(done / checks.length) * 100} 100`;
  }
  checks.forEach((c) => c.addEventListener('change', updateRing));
  updateRing();

  /* ---------- Отметки заполненных разделов ---------- */

  function sectionDone(section) {
    const fields = [...section.querySelectorAll('input[type="text"], textarea, input[type="radio"]:checked, input[type="checkbox"]:checked')]
      .filter((el) => !el.disabled && el.offsetParent !== null);
    return fields.some((el) => (el.type === 'radio' || el.type === 'checkbox') ? true : el.value.trim() !== '');
  }
  function updateNav() {
    form.querySelectorAll('[data-section]').forEach((s) => {
      const link = document.querySelector(`[data-nav="${s.id}"]`);
      if (!link) return;
      const disabled = s.classList.contains('is-disabled');
      link.classList.toggle('done', disabled || sectionDone(s));
    });
  }
  form.addEventListener('input', updateNav);
  form.addEventListener('change', updateNav);
  updateNav();

  /* ---------- Предупреждение о несохранённых данных ---------- */

  let dirty = false;
  function markDirty() {
    dirty = true;
    scheduleSave();
  }
  form.addEventListener('input', markDirty);
  form.addEventListener('change', markDirty);
  window.addEventListener('beforeunload', (e) => {
    if (!dirty) return;
    flushSave();
    if (savedOk) return; // копия формы уже в браузере — уходить со страницы безопасно
    e.preventDefault();
    e.returnValue = '';
  });

  /* ---------- Отправка ---------- */

  const val = (name) => (form.elements[name]?.value || '').trim();
  const rowsOf = (key) => [...form.querySelectorAll(`[data-repeater="${key}"] > .rep-list > .rep-item`)];
  const rowValue = (row, field) => (row.querySelector(`[name$="[${field}]"]`)?.value || '').trim();
  const rowFilled = (row) => [...row.querySelectorAll('input[type="text"], textarea')].some((el) => el.value.trim() !== '');
  const jump = (target) => () => {
    const el = typeof target === 'string' ? form.querySelector(target) : target;
    if (!el) return;
    // Поле может быть в разделе следующего уровня — сначала показываем его.
    const need = parseInt(el.closest('[data-lvl]')?.dataset.lvl, 10) || 1;
    if (need > levelOf()) setLevel(need);
    const field = el.closest('.field, .rep-item, fieldset, .form-section');
    field?.classList.add('has-error');
    if (window.VerdictForms && el.matches('input, textarea')) {
      window.VerdictForms.focusField(el);
    } else {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.focus?.({ preventScroll: true });
    }
  };

  const storyField = form.elements.story;
  const ideaMinWords = parseInt(storyField?.dataset.rangeIdea, 10) || 20;
  const withText = () => rowsOf('decisions').filter((r) => rowValue(r, 'text'));

  /**
   * Чего не хватает до уровня `level` (только требования самого уровня).
   * Те же правила на сервере: situation_level(); уровень 2 — это situation_validate.
   * key — чтобы при отправке не показывать одно и то же дважды (story, decisions есть на двух уровнях).
   */
  function problemsFor(level) {
    const list = [];
    const add = (key, text, target) => list.push({ key, text, onClick: jump(target) });

    if (level === 1) {
      if (!form.querySelector('input[name="category"]:checked')) add('category', 'Выберите категорию', 'input[name="category"]');
      if (!val('title')) add('title', 'Укажите название ситуации', 'input[name="title"]');
      if (countWords(val('story')) < ideaMinWords) add('story', `Ситуация: опишите завязку — хотя бы ${ideaMinWords} слов`, 'textarea[name="story"]');
      const n = withText().length;
      if (n < 2) add('decisions', `Предложите хотя бы 2 варианта решения (сейчас ${n})`, '#s7');
      return list;
    }

    if (level === 2) {
      const type = form.querySelector('[data-type-input]:checked')?.value || '';
      if (!type) add('type', 'Выберите тип ситуации', '[data-type-input]');
      if (!val('world[place]')) add('place', 'Мир: укажите, где происходит ситуация', 'input[name="world[place]"]');
      if (!val('world[circumstances]')) add('circumstances', 'Мир: опишите обстоятельства', 'textarea[name="world[circumstances]"]');
      if (countWords(val('story')) < 40) add('story', 'Ситуация: минимум 40 слов (рекомендуется 100–250)', 'textarea[name="story"]');

      const people = rowsOf('participants').filter(rowFilled);
      if (!people.length) add('people', 'Добавьте хотя бы одного участника', '#s4 input');
      const noName = people.find((r) => !rowValue(r, 'name'));
      if (noName) add('names', 'У каждого участника должно быть имя', noName.querySelector('input'));

      if (!rowsOf('facts').some((r) => r.querySelector('textarea').value.trim())) add('facts', 'Укажите хотя бы один факт', '#s5 textarea');

      if (type === 'witness' || type === 'public') {
        const witnesses = rowsOf('witnesses').filter(rowFilled);
        if (!witnesses.length) add('witnesses', 'Добавьте хотя бы одного свидетеля', '#s6 input');
        const incomplete = witnesses.find((r) => !rowValue(r, 'name') || !rowValue(r, 'claim'));
        if (incomplete) add('witness-fields', 'У каждого свидетеля должно быть имя и показания', incomplete.querySelector('input'));
        if (type === 'witness' && witnesses.length > 5) add('witness-max', 'В ситуации со свидетелями — не больше 5 свидетелей', '#s6');
      }

      const decisions = rowsOf('decisions').filter(rowFilled);
      const noText = decisions.find((r) => !rowValue(r, 'text'));
      if (noText) add('decisions', 'У каждого варианта должна быть формулировка решения', noText.querySelector('input'));
      else if (decisions.length < 4) add('decisions', `Предложите минимум 4 варианта решения (сейчас ${decisions.length})`, '#s7');

      if (!val('ambiguity[conflict]')) add('conflict', 'Опишите главный конфликт ситуации', 'input[name="ambiguity[conflict]"]');
      return list;
    }

    // Уровень 3 — полное досье.
    const rows = withText();
    const consequences = rows.filter((r) => [...r.querySelectorAll('details.conseq textarea')].some((t) => t.value.trim()));
    const effects = rows.filter((r) => [...r.querySelectorAll('input[type="range"]')].some((x) => x.value !== '0'));
    const target = (list2) => (rows.find((r) => !list2.includes(r)) || rows[0])?.querySelector('details.conseq textarea') || '#s7';
    if (consequences.length < 2) add('consequences', `Опишите последствия хотя бы для 2 решений (сейчас ${consequences.length})`, target(consequences));
    if (effects.length < 2) add('effects', `Задайте влияние на мир хотя бы для 2 решений (сейчас ${effects.length})`, target(effects));
    if (!val('hidden')) add('hidden', 'Скрытая информация: что произошло на самом деле', 'textarea[name="hidden"]');
    if (!val('ambiguity[for_one]') || !val('ambiguity[for_other]')) {
      add('arguments', 'Неоднозначность: аргументы в пользу обоих решений', `textarea[name="ambiguity[${val('ambiguity[for_one]') ? 'for_other' : 'for_one'}]"]`);
    }
    return list;
  }

  /** Всё, что нужно для отправки на отбор: уровни 1 и 2, без повторов. */
  function submitProblems() {
    const byKey = new Map();
    [...problemsFor(1), ...problemsFor(2)].forEach((p) => byKey.set(p.key, p));
    return [...byKey.values()];
  }

  /** Достигнутый уровень: 0–3, как situation_level() на сервере. */
  function achievedLevel() {
    let n = 0;
    while (n < 3 && !problemsFor(n + 1).length) n++;
    return n;
  }

  /* ---------- Уровни ---------- */

  const tabs = [...document.querySelectorAll('[data-level-tab]')];
  const levelDesc = document.querySelector('[data-level-desc]');
  const LEVEL_DESC = Object.fromEntries(tabs.map((t) => [t.dataset.levelTab, t.dataset.desc || '']));
  const CHECK = '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>';

  function setLevel(n, scroll = false) {
    const prev = levelOf();
    layout.dataset.level = String(n);
    tabs.forEach((t) => t.setAttribute('aria-pressed', String(Number(t.dataset.levelTab) === n)));
    if (levelDesc) levelDesc.textContent = LEVEL_DESC[n] || '';
    // Для «Дела» нужно 4+ варианта решения — добавляем пустые строки, чтобы было куда писать.
    if (n >= 2) {
      const rep = form.querySelector('[data-repeater="decisions"]');
      while (rep && rowsOf('decisions').length < 4) addItem(rep, false);
    }
    counters.forEach((u) => u());
    updateNav();
    updateLevels();
    if (scroll && n !== prev) {
      const first = n > prev ? form.querySelector(`[data-section][data-lvl="${n}"]`) : null;
      (first || document.querySelector('.level-bar'))?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  function updateLevels() {
    let allDone = true;
    tabs.forEach((t) => {
      const n = Number(t.dataset.levelTab);
      const missing = problemsFor(n).length;
      allDone = allDone && missing === 0;
      t.classList.toggle('is-done', allDone);
      const state = t.querySelector('[data-level-state]');
      if (state) state.innerHTML = allDone ? `${CHECK}Готово` : (missing ? `Осталось: ${missing}` : `Сначала уровень ${n - 1}`);
    });
  }

  tabs.forEach((t) => t.addEventListener('click', () => setLevel(Number(t.dataset.levelTab), true)));
  form.querySelector('[data-level-next]')?.addEventListener('click', () => setLevel(2, true));
  let levelsQueued = false;
  const queueLevels = () => {
    if (levelsQueued) return;
    levelsQueued = true;
    requestAnimationFrame(() => { levelsQueued = false; updateLevels(); });
  };
  form.addEventListener('input', queueLevels);
  form.addEventListener('change', queueLevels);
  form.addEventListener('click', (e) => { if (e.target.closest('.rep-remove, .rep-add')) queueLevels(); });

  const intentInput = form.querySelector('[data-intent]');
  const draftBtn = form.querySelector('[data-intent-value="draft"]');

  function send(intent) {
    // Копия в браузере остаётся, пока сервер не подтвердит сохранение (data-autosave-clear).
    flushSave();
    dirty = false;
    intentInput.value = intent;
    form.querySelectorAll('button[type="submit"]').forEach((b) => { b.disabled = true; });
    const btn = form.querySelector(`[data-intent-value="${intent}"]`);
    if (btn) btn.lastChild.textContent = intent === 'draft' ? 'Сохраняем…' : 'Отправляем…';
    HTMLFormElement.prototype.submit.call(form);
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const modal = window.VerdictModal;
    // Enter в текстовом поле «нажимает» первую кнопку формы — «Сохранить черновик».
    const intent = e.submitter?.dataset.intentValue || 'submit';

    if (intent === 'draft') {
      if (!val('title')) {
        if (modal) {
          await modal.alert({
            tone: 'warn',
            title: 'Дайте черновику название',
            text: 'Для черновика нужно только название — по нему вы найдёте его в профиле.',
            items: [{ text: 'Указать название', onClick: jump('input[name="title"]') }],
          });
        }
        return;
      }
      send('draft');
      return;
    }

    const issues = submitProblems();
    if (issues.length) {
      if (!modal) return;
      const title = issues.length === 1 ? 'Осталось одно поле' : `Не заполнено: ${issues.length}`;
      if (draftBtn) {
        const saveDraft = await modal.confirm({
          tone: 'warn',
          title,
          text: 'Эти поля нужны, чтобы отправить ситуацию на отбор. Нажмите на пункт, чтобы перейти к нему, — или сохраните черновик и допишите позже.',
          items: issues,
          ok: 'Сохранить черновик',
          cancel: 'Дописать сейчас',
        });
        if (saveDraft) {
          if (form.requestSubmit) form.requestSubmit(draftBtn);
          else draftBtn.click();
        }
      } else {
        await modal.alert({ tone: 'warn', title, text: 'Эти поля обязательны по шаблону. Нажмите на пункт, чтобы перейти к нему.', items: issues });
      }
      return;
    }

    // Быстрая проверка — часть уровня 3: спрашиваем о ней, только если автор её видел.
    const unchecked = [...checks].filter((c) => !c.checked);
    if (unchecked.length && levelOf() === 3) {
      const ok = modal ? await modal.confirm({
        tone: 'warn',
        title: `Проверка: ${checks.length - unchecked.length} из ${checks.length}`,
        text: 'Не все пункты быстрой проверки отмечены. Отправить ситуацию на отбор всё равно?',
        items: unchecked.map((c) => ({ text: c.closest('.check').textContent.trim() })),
        ok: 'Отправить всё равно',
        cancel: 'Вернуться к проверке',
      }) : true;
      if (!ok) {
        document.getElementById('sc')?.scrollIntoView({ behavior: 'smooth' });
        return;
      }
    }
    send('submit');
  });

  /* ---------- Автосохранение в браузере ----------
     Пока автор пишет, копия формы лежит в localStorage. Она переживает закрытую вкладку,
     перезагрузку и сбой сети; сервер просит удалить её после успешного сохранения. */

  const KEY = form.dataset.autosave || '';
  const store = (() => {
    try {
      const s = window.localStorage;
      s.setItem('verdict:probe', '1');
      s.removeItem('verdict:probe');
      return s;
    } catch (_) {
      return null;
    }
  })();
  const statusEl = form.querySelector('[data-autosave-status]');
  let saveTimer = 0;
  let savedOk = false;

  // participants[n0][name] → [name], facts[2] → '', decisions[1][effects][trust] → [effects][trust]
  const suffix = (name) => name.replace(/^[^[]+\[[^\]]*\]/, '');
  const ownField = (el) => el.name && el.name !== '_csrf' && el.name !== 'intent' && !el.closest('.repeater');
  const clock = (ts) => new Date(ts).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });

  function snapshot() {
    const reps = {};
    form.querySelectorAll('.repeater').forEach((rep) => {
      reps[rep.dataset.repeater] = rowsOf(rep.dataset.repeater).map((row) => {
        const o = {};
        row.querySelectorAll('input[name], textarea[name]').forEach((el) => { o[suffix(el.name)] = el.value; });
        return o;
      });
    });
    const fields = {};
    [...form.elements].forEach((el) => {
      if (!ownField(el)) return;
      if (el.type === 'radio') {
        if (el.checked) fields[el.name] = el.value;
      } else if (el.type === 'checkbox') {
        fields[el.name] = fields[el.name] || [];
        if (el.checked) fields[el.name].push(el.value);
      } else {
        fields[el.name] = el.value;
      }
    });
    return { fields, reps };
  }

  const hasText = () => [...form.querySelectorAll('input[type="text"], textarea')].some((el) => el.value.trim() !== '');

  function save() {
    clearTimeout(saveTimer);
    saveTimer = 0;
    if (!store || !KEY) return;
    try {
      if (hasText()) {
        const at = Date.now();
        store.setItem(KEY, JSON.stringify({ v: 1, at, data: snapshot() }));
        if (statusEl) statusEl.textContent = `Копия сохранена в браузере в ${clock(at)}.`;
      } else {
        store.removeItem(KEY);
      }
      savedOk = true;
    } catch (_) {
      savedOk = false; // переполнено хранилище или запрещено — сработает обычное предупреждение
    }
  }
  function scheduleSave() {
    savedOk = false;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(save, 800);
  }
  function flushSave() {
    if (saveTimer) save();
  }
  window.addEventListener('pagehide', flushSave);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') flushSave(); });

  function restore(data) {
    Object.entries(data.reps || {}).forEach(([key, rows]) => {
      const rep = form.querySelector(`[data-repeater="${key}"]`);
      if (!rep || !Array.isArray(rows)) return;
      const min = parseInt(rep.dataset.min, 10) || 0;
      let items = rowsOf(key);
      while (items.length < rows.length && items.length < 50) {
        addItem(rep, false);
        items = rowsOf(key);
      }
      while (items.length > Math.max(rows.length, min)) {
        items.pop().remove();
      }
      items.forEach((row, i) => {
        const saved = rows[i] || {};
        row.querySelectorAll('input[name], textarea[name]').forEach((el) => {
          const v = saved[suffix(el.name)];
          el.value = typeof v === 'string' ? v : (el.type === 'range' ? '0' : '');
        });
        // Раскрываем последствия, если они были заполнены.
        const conseq = row.querySelector('details.conseq');
        if (conseq && [...conseq.querySelectorAll('textarea')].some((t) => t.value.trim())) conseq.open = true;
      });
      refresh(rep);
    });

    const f = data.fields || {};
    [...form.elements].forEach((el) => {
      if (!ownField(el) || !(el.name in f)) return;
      const v = f[el.name];
      if (el.type === 'radio') el.checked = el.value === v;
      else if (el.type === 'checkbox') el.checked = Array.isArray(v) && v.includes(el.value);
      else if (typeof v === 'string') el.value = v;
    });

    // Обновляем всё, что зависит от значений: неоновые списки, счётчики, ползунки, разделы.
    form.querySelectorAll('select').forEach((s) => s.dispatchEvent(new Event('change', { bubbles: true })));
    form.querySelectorAll('textarea[data-counter], input[type="range"]').forEach((el) => el.dispatchEvent(new Event('input', { bubbles: true })));
    syncWitnesses();
    syncCont();
    updateRing();
    // Показываем уровень, следующий за достигнутым в восстановленном тексте.
    setLevel(Math.max(levelOf(), Math.min(3, achievedLevel() + 1)));
  }

  async function offerRestore() {
    if (!store || !KEY) return;
    let saved = null;
    try { saved = JSON.parse(store.getItem(KEY) || 'null'); } catch (_) { saved = null; }
    if (!saved || !saved.data) return;

    if ('freshInput' in form.dataset) {
      // Сервер только что вернул отправленный текст (ошибки или вход после конца сессии) — он и есть самый свежий.
      save();
      return;
    }
    const serverAt = parseInt(form.dataset.savedAt, 10) || 0;
    if (saved.at <= serverAt || JSON.stringify(saved.data) === JSON.stringify(snapshot())) {
      store.removeItem(KEY); // на сервере версия не старше копии
      return;
    }
    const when = new Date(saved.at).toLocaleString('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' });
    const ok = window.VerdictModal
      ? await window.VerdictModal.confirm({
        tone: 'info',
        icon: 'question',
        kicker: 'Автосохранение',
        title: 'Продолжить с того же места?',
        text: `В этом браузере есть несохранённая копия формы от ${when}. Вернуть её?`,
        ok: 'Вернуть текст',
        cancel: 'Не сейчас',
      })
      : window.confirm(`Вернуть несохранённую копию формы от ${when}?`);
    if (ok) {
      restore(saved.data);
      if (statusEl) statusEl.textContent = `Текст восстановлен из копии от ${when}.`;
    }
  }

  /* Если есть ошибки — показываем их сразу */
  const summary = form.querySelector('[data-error-summary]');
  if (summary) {
    summary.scrollIntoView({ block: 'center' });
    summary.focus({ preventScroll: true });
  }
  setLevel(levelOf());
  offerRestore();
})();
