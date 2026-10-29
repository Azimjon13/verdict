"""Sign in, sign up, profile and the team's user list."""
import time

import pymysql
from flask import current_app, request, session, url_for

from ..auth import (ROLES, admins_count, auth_attempt, auth_login, auth_logout, current_user, current_user_id, is_admin,
                    is_logged_in, login_lock_seconds, login_register_failure, name_validate, password_validate,
                    registration_validate, user_create, user_find, user_set_password, user_set_role, user_update_name,
                    users_all)
from ..catalog import STATUSES
from ..repository import input_str, situations_list, vote_counts
from ..sessions import active_count, revoke_others
from ..players import on_login, on_logout, on_register
from ..web import csrf_valid, flash, page, redirect, require_login, safe_back, voter_id


def _home_for(user):
    return url_for('library') if user['role'] == 'admin' else url_for('create')


def login():
    back = safe_back(request.form.get('back') if request.method == 'POST' else request.args.get('back', ''))
    if is_logged_in():
        return redirect(back or _home_for(current_user()))

    error = ''
    login_name = ''
    if request.method == 'POST':
        login_name = input_str(request.form.get('login', ''), 40)
        password = request.form.get('password', '')
        wait = login_lock_seconds()
        if not csrf_valid():
            error = 'Сессия устарела. Попробуйте ещё раз.'
        elif wait > 0:
            error = 'Слишком много неудачных попыток. Попробуйте через %d сек.' % wait
        elif not login_name or not password:
            error = 'Введите логин и пароль.'
        else:
            user = auth_attempt(login_name, password)
            if user:
                auth_login(user)
                on_login(int(user['id']), voter_id())
                flash('success', 'С возвращением, %s!' % user['display_name'])
                return redirect(back or _home_for(user))
            login_register_failure()
            time.sleep(0.3)
            error = 'Неверный логин или пароль.'

    return page('login.html', title='Вход', active='', body_class='page-auth', bg='high',
                back=back, error=error, login_name=login_name)


def register():
    back = safe_back(request.form.get('back') if request.method == 'POST' else request.args.get('back', '')) or url_for('create')
    if is_logged_in():
        return redirect(back)

    errors = {}
    values = {'login': '', 'display_name': ''}
    if request.method == 'POST':
        values['login'] = input_str(request.form.get('login', ''), 40)
        values['display_name'] = input_str(request.form.get('display_name', ''), 80)
        password = request.form.get('password', '')
        confirm = request.form.get('password_confirm', '')
        if not csrf_valid():
            errors = {'_csrf': 'Сессия устарела. Попробуйте ещё раз.'}
        else:
            errors = registration_validate(values['login'], values['display_name'], password, confirm)
        if not errors:
            try:
                new_id = user_create(values['login'], values['display_name'], password)
            except pymysql.err.IntegrityError:
                errors['login'] = 'Такой логин уже занят.'
            else:
                auth_login(user_find(new_id))
                on_register(int(new_id), voter_id())
                flash('success', 'Аккаунт создан. Добро пожаловать, %s! Ваши вердикты и прогресс теперь хранятся в аккаунте.'
                      % values['display_name'])
                return redirect(back)

    return page('register.html', title='Регистрация', active='', body_class='page-auth', bg='high',
                back=back, errors=errors, values=values)


def logout():
    from ..web import csrf_valid as valid
    if request.method == 'POST' and valid() and is_logged_in():
        auth_logout()
        on_logout()
        flash('success', 'Вы вышли из аккаунта.')
    return redirect(url_for('index'))


def account():
    gate = require_login(url_for('account'), 'Войдите, чтобы открыть профиль.')
    if gate:
        return gate
    me = current_user()
    uid = int(me['id'])
    lifetime = current_app.config['VERDICT']['session_lifetime']

    errors = {}
    if request.method == 'POST':
        act = request.form.get('action', '')
        if not csrf_valid():
            flash('error', 'Сессия устарела. Попробуйте ещё раз.')
            return redirect(url_for('account'))
        if act == 'name':
            name = input_str(request.form.get('display_name', ''), 80)
            errors = name_validate(name)
            if not errors:
                user_update_name(uid, name)
                flash('success', 'Имя обновлено. Подпись в ваших ситуациях тоже изменена.')
                return redirect(url_for('account'))
        elif act == 'password':
            current = request.form.get('current_password', '')
            new = request.form.get('new_password', '')
            confirm = request.form.get('new_password_confirm', '')
            if not auth_attempt(me['login'], current):
                errors['current_password'] = 'Текущий пароль указан неверно.'
            else:
                errors = {'new_' + k: v for k, v in password_validate(new, confirm).items()}
            if not errors:
                user_set_password(uid, new)
                closed = revoke_others(uid, session.sid)
                session.regenerate()
                flash('success', 'Пароль изменён.' + (' Другие сеансы входа завершены: %d.' % closed if closed else ''))
                return redirect(url_for('account'))
        elif act == 'profile':
            from ..social import save_profile
            save_profile(uid, input_str(request.form.get('bio', ''), 280), request.form.get('visibility', 'public'),
                         bool(request.form.get('in_ratings')))
            flash('success', 'Публичный профиль сохранён.')
            return redirect(url_for('account'))
        elif act == 'sessions':
            closed = revoke_others(uid, session.sid)
            flash('success', 'Завершено других сеансов: %d.' % closed if closed else 'Других активных сеансов нет.')
            return redirect(url_for('account'))

    mine = situations_list(user_id=uid)
    by_status = {k: 0 for k in STATUSES}
    for s in mine:
        by_status[s['status']] = by_status.get(s['status'], 0) + 1
    return page('account.html', title='Профиль', active='account', body_class='page-account', bg='calm',
                me=me, errors=errors, mine=mine, by_status=by_status, counts=vote_counts(),
                sessions=active_count(uid, lifetime), role_name=ROLES.get(me['role'], me['role']),
                name_value=request.form.get('display_name', me['display_name']) if request.method == 'POST' else me['display_name'])


def users():
    gate = require_login(url_for('users'))
    if gate:
        return gate
    if not is_admin():
        flash('error', 'Список пользователей доступен только команде.')
        return redirect(url_for('account'))

    if request.method == 'POST':
        try:
            target_id = int(request.form.get('id', 0))
        except ValueError:
            target_id = 0
        role = request.form.get('role', '')
        target = user_find(target_id) if target_id else None
        if not csrf_valid() or not target or role not in ROLES:
            flash('error', 'Не удалось изменить роль.')
        elif target['role'] == 'admin' and role != 'admin' and admins_count() <= 1:
            flash('error', 'Нельзя снять права с последнего участника команды.')
        else:
            user_set_role(target_id, role)
            flash('success', '%s: роль изменена на «%s».' % (target['display_name'], ROLES[role]))
        return redirect(url_for('users'))

    return page('users.html', title='Пользователи', active='users', body_class='page-users', bg='calm',
                users=users_all(), me_id=current_user_id())
