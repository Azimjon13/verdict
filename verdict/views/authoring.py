"""Authors and the team: the creator form, the selection board, the full dossier, moderation actions."""
from flask import request, session, url_for

from .. import notify
from ..auth import can_edit_situation, can_save_draft, current_user, current_user_id, is_admin, is_logged_in, owns_situation
from ..catalog import CATEGORIES, LEVELS, SITUATION_TYPES, STATUSES
from ..forms import parse_nested, render_decision, render_line, render_participant, render_repeater, render_witness
from ..helpers import case_controversy, word_count
from ..repository import (situation_delete, situation_find, situation_form_defaults, situation_form_pad,
                          situation_from_input, situation_insert, situation_level, situation_set_status, situation_update,
                          situation_validate, situation_validate_draft, situations_list, vote_counts, vote_counts_for,
                          vote_duration_stats)
from ..web import autosave_clear, autosave_key, csrf_valid, flash, page, redirect, require_login, safe_back

# Template section => (number, name, level from which it shows).
SECTIONS = {
    's1': ('01', 'Основная информация', 1),
    's2': ('02', 'Мир / сеттинг', 2),
    's3': ('03', 'Ситуация', 1),
    's4': ('04', 'Участники', 2),
    's5': ('05', 'Доказательства', 2),
    's6': ('06', 'Свидетели', 2),
    's7': ('07–08', 'Решения и последствия', 1),
    's9': ('09', 'Скрытая информация', 3),
    's10': ('10', 'Неоднозначность', 2),
    's11': ('11', 'Продолжение', 3),
    's12': ('12', 'Заметки автора', 3),
    'sc': ('✓', 'Быстрая проверка', 3),
}
ERROR_ANCHORS = {
    'author': 's1', 'category': 's1', 'type': 's1', 'title': 's1',
    'world_place': 's2', 'world_circumstances': 's2', 'story': 's3',
    'participants': 's4', 'facts': 's5', 'witnesses': 's6', 'decisions': 's7', 'ambiguity': 's10',
}


def create(id=0):
    me_url = url_for('edit', id=id) if id else url_for('create')
    if request.method == 'POST' and not is_logged_in():
        # The session ended while the author was writing: keep the text and put it back into the form after login.
        session['create_stash'] = {'edit': id, 'form': situation_from_input(parse_nested(request.form))}
        return require_login(me_url, 'Сессия завершилась. Войдите снова — ваш текст сохранён и вернётся в форму.')
    gate = require_login(me_url, 'Войдите или зарегистрируйтесь, чтобы добавлять ситуации.')
    if gate:
        return gate
    me = current_user()

    editing = situation_find(id) if id else None
    if id and not editing:
        flash('error', 'Ситуация для редактирования не найдена.')
        return redirect(url_for('library'))
    if editing and not can_edit_situation(editing):
        flash('error', 'Редактировать ситуацию может команда или автор, пока ситуация на отборе.')
        return redirect(url_for('view', id=editing['id']))

    can_draft = can_save_draft(editing)
    is_draft = bool(editing) and editing['status'] == 'draft'
    save_key = autosave_key(editing['id'] if editing else None, current_user_id())

    errors = {}
    restored = False
    as_draft = False
    if request.method == 'POST':
        form = situation_from_input(parse_nested(request.form))
        as_draft = can_draft and request.form.get('intent') == 'draft'
        # The author is the account owner; editing doesn't change the signature.
        form['author'] = editing['author'] if editing else me['display_name']
        if as_draft:
            # A draft may not have its category and type yet.
            form['category'] = form['category'] if form['category'] in CATEGORIES else ''
            form['type'] = form['type'] if form['type'] in SITUATION_TYPES else 'private'
        if not csrf_valid():
            errors = {'_csrf': 'Сессия устарела. Проверьте данные и отправьте форму ещё раз.'}
        else:
            errors = situation_validate_draft(form) if as_draft else situation_validate(form)
        if not errors:
            autosave_clear(save_key)
            if as_draft:
                if editing:
                    situation_update(editing['id'], form, 'draft')
                    new_id = editing['id']
                else:
                    new_id = situation_insert(form, 'draft', int(me['id']))
                level = situation_level(form)
                flash('success', 'Черновик «%s» сохранён' % form['title']
                      + (' — готов уровень %d из 3 («%s»)' % (level, LEVELS[level]['name']) if level > 0 else '')
                      + '. Его видите только вы — вернитесь к нему в любой момент из профиля.')
                return redirect(url_for('edit', id=new_id))
            if editing:
                remap = situation_update(editing['id'], form, 'pending' if is_draft else None)
                note = ''
                if remap['moved'] > 0:
                    note += ' Голоса за варианты, сменившие букву, перенесены вместе с ними (%d).' % remap['moved']
                if remap['deleted'] > 0:
                    note += ' Удалено голосов за убранные варианты: %d.' % remap['deleted']
                flash('success', ('Ситуация «%s» отправлена на отбор. Спасибо за вклад!' if is_draft
                                  else 'Изменения в ситуации «%s» сохранены.') % form['title'] + note)
                return redirect(url_for('view', id=editing['id']))
            new_id = situation_insert(form, 'pending', int(me['id']))
            flash('success', 'Ситуация «%s» отправлена на отбор. Спасибо за вклад!' % form['title'])
            return redirect(url_for('view', id=new_id))
        form = situation_form_pad(form)
    elif (session.get('create_stash') or {}).get('edit') == id and 'create_stash' in session:
        # Text sent after the session had already ended.
        form = situation_form_pad(session.pop('create_stash')['form'])
        form['author'] = editing['author'] if editing else me['display_name']
        restored = True
    else:
        form = situation_form_pad(editing) if editing else situation_form_defaults(me['display_name'])

    # How many votes each option has (by uid — letters in the form may have shifted already).
    if editing:
        counts = vote_counts_for(editing['id'])
        by_uid = {d['uid']: counts.get(d['key'], 0) for d in editing['decisions']}
        form['decisions'] = [{**d, 'votes': by_uid.get(d.get('uid', ''), 0)} for d in form['decisions']]

    # Which level of the form to show: the next one after the reached level, so the author sees what to add.
    # After a failed submission — at least «Дело», otherwise some errors would sit in hidden sections.
    achieved = situation_level(form)
    view_level = max(1, min(3, achieved + 1))
    if errors and not as_draft and '_csrf' not in errors:
        view_level = max(view_level, 2)

    repeaters = {
        'participants': render_repeater('participants', form['participants'], render_participant, 'Добавить участника', 1, 12),
        'facts': render_repeater('facts', form['facts'], render_line('facts', 'Факт', 'То, что игрок знает наверняка'), 'Добавить факт', 1, 20),
        'unknowns': render_repeater('unknowns', form['unknowns'], render_line('unknowns', 'Сомнение', 'Противоречия, неизвестные факты, сомнительные обстоятельства'), 'Добавить сомнение', 0, 20),
        'witnesses': render_repeater('witnesses', form['witnesses'], render_witness, 'Добавить свидетеля', 1, 8),
        'decisions': render_repeater('decisions', form['decisions'], render_decision, 'Добавить вариант решения', 2, 8),
    }
    return page('create.html', title='Редактирование ситуации' if editing else 'Создать ситуацию', active='create',
                body_class='page-create', bg='calm', scripts=['create.js'],
                form=form, editing=editing, is_draft=is_draft, can_draft=can_draft, autosave=save_key, errors=errors,
                restored=restored, achieved=achieved, view_level=view_level, sections=SECTIONS, error_anchors=ERROR_ANCHORS,
                story_words=word_count(form['story']), repeaters=repeaters,
                saved_at=_ms(editing['updated_at']) if editing else 0)


def _ms(timestamp):
    """A database time (UTC) as JavaScript milliseconds."""
    from datetime import datetime, timezone
    try:
        return int(datetime.strptime(timestamp[:19], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp() * 1000)
    except ValueError:
        return 0


SORTS = {
    'new': ('Сначала новые', 'calendar'),
    'old': ('Сначала старые', 'clock'),
    'votes': ('Больше вердиктов', 'gavel'),
    'heat': ('Самые спорные', 'flame'),
    'title': ('По названию, А–Я', 'file'),
}


def library():
    uid = current_user_id()
    status = request.args.get('status', 'all')
    if status != 'all' and status not in STATUSES and not (status == 'mine' and uid):
        status = 'all'
    category = request.args.get('category', '')
    if category and category not in CATEGORIES:
        category = ''

    # Drafts are seen only by their author (in the «Черновики» and «Мои» tabs).
    all_cases = [s for s in situations_list() if s['status'] != 'draft' or (uid and s['user_id'] == uid)]
    counts = vote_counts()
    admin = is_admin()

    # First sprint progress: categories × types (without drafts and rejected).
    matrix = {c: {t: 0 for t in SITUATION_TYPES} for c in CATEGORIES}
    tab_counts = {'all': 0, **{k: 0 for k in STATUSES}, 'mine': 0}
    for s in all_cases:
        tab_counts[s['status']] = tab_counts.get(s['status'], 0) + 1
        if s['status'] != 'draft':
            tab_counts['all'] += 1
        if uid and s['user_id'] == uid:
            tab_counts['mine'] += 1
        if s['status'] not in ('draft', 'rejected') and s['type'] in matrix.get(s['category'], {}):
            matrix[s['category']][s['type']] += 1
    target_per_category = sum(t['target'] for t in SITUATION_TYPES.values())

    items = [s for s in all_cases
             if ((status == 'all' and s['status'] != 'draft') or s['status'] == status or (status == 'mine' and s['user_id'] == uid))
             and (not category or s['category'] == category)]
    tabs = {'all': 'Все', **{k: v for k, v in STATUSES.items() if k != 'draft'}}
    if tab_counts['draft'] > 0:
        tabs['draft'] = 'Черновики'
    if uid:
        tabs['mine'] = 'Мои'

    sort = request.args.get('sort', 'new')
    if sort not in SORTS:
        sort = 'new'

    def heat(s):
        value = case_controversy(s, counts.get(s['id'], {}))['value']
        return -1 if value is None else value

    keys = {
        'new': lambda s: -s['id'],
        'old': lambda s: s['id'],
        'votes': lambda s: (-sum(counts.get(s['id'], {}).values()), -s['id']),
        'heat': lambda s: (-heat(s), -s['id']),
        'title': lambda s: s['title'].lower(),
    }
    items.sort(key=keys[sort])

    def qs(**over):
        params = {'status': status, 'category': category, 'sort': sort, **over}
        return url_for('library', **{k: v for k, v in params.items() if v not in ('', 'all', 'new')})

    return page('library.html', title='Отбор контента', active='library', body_class='page-library', bg='calm',
                uid=uid, status=status, category=category, items=items, counts=counts, admin=admin, matrix=matrix,
                tab_counts=tab_counts, target_per_category=target_per_category, tabs=tabs, sorts=SORTS, sort=sort,
                qs=qs, back=qs())


def view(id):
    from ..auth import can_view_situation
    s = situation_find(id)
    if not s or not can_view_situation(s):
        flash('error', 'Ситуация не найдена.')
        return redirect(url_for('library'))
    counts = vote_counts_for(s['id'])
    return page('view.html', title=s['title'] + ' — досье', active='library', body_class='page-view', bg='calm',
                s=s, admin=is_admin(), counts=counts, total=sum(counts.values()), contro=case_controversy(s, counts),
                back=url_for('view', id=s['id']), timing=vote_duration_stats(s['id']))


def action():
    if request.method != 'POST' or not csrf_valid():
        flash('error', 'Не удалось выполнить действие. Обновите страницу и попробуйте снова.')
        return redirect(url_for('library'))
    try:
        sid = int(request.form.get('id', 0))
    except ValueError:
        sid = 0
    act = request.form.get('action', '')
    back = safe_back(request.form.get('back', '')) or url_for('view', id=sid)
    s = situation_find(sid) if sid > 0 else None

    # An author may delete their own draft; everything else is for the team.
    own_draft_delete = bool(s) and act == 'delete' and s['status'] == 'draft' and owns_situation(s)
    if not is_admin() and not own_draft_delete:
        flash('error', 'Это действие доступно только команде.')
        return redirect(url_for('library') if is_logged_in() else url_for('login', back=url_for('library')))
    if not s:
        flash('error', 'Ситуация не найдена.')
        return redirect(url_for('library'))

    if act in ('approved', 'rejected', 'pending') and s['status'] == 'campaign':
        flash('error', '«%s» — глава сюжетной кампании: её статус не меняют на отборе.' % s['title'])
    elif act == 'approved':
        situation_set_status(sid, 'approved')
        flash('success', 'Ситуация «%s» добавлена в игру.' % s['title'])
        if s['status'] != 'approved' and s.get('user_id') and s['user_id'] != current_user_id():
            notify.send(s['user_id'], 'case_approved', 'Ваше дело «%s» в игре — игроки уже могут его судить.' % s['title'],
                        url_for('case', id=sid))
    elif act == 'rejected':
        situation_set_status(sid, 'rejected')
        flash('success', 'Ситуация «%s» отклонена.' % s['title'])
        if s['status'] != 'rejected' and s.get('user_id') and s['user_id'] != current_user_id():
            notify.send(s['user_id'], 'case_rejected', 'Дело «%s» не прошло отбор. Его можно доработать и отправить снова.'
                        % s['title'], url_for('view', id=sid))
    elif act == 'pending':
        situation_set_status(sid, 'pending')
        flash('success', 'Ситуация «%s» возвращена на отбор.' % s['title'])
    elif act == 'delete':
        situation_delete(sid)
        flash('success', ('Черновик «%s» удалён.' if s['status'] == 'draft' else 'Ситуация «%s» удалена.') % s['title'])
        return redirect(url_for('account') if own_draft_delete else url_for('library'))
    else:
        flash('error', 'Неизвестное действие.')
    return redirect(back)
