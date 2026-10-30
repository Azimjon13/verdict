# VERDICT — judgment simulator

[![tests](https://github.com/Azimjon13/verdict/actions/workflows/tests.yml/badge.svg)](https://github.com/Azimjon13/verdict/actions/workflows/tests.yml)

A decision & judgment game: fictional worlds, disputed acts, witnesses who may lie, and the consequences of your
verdict. The website is in Russian, like the game content. Situations follow `Шаблон игровой ситуации.docx`;
the creator brief is `Content Creator Brief.docx`.

The site is written in **Python (Flask)**. The game data lives in plain JSON (`content/`) and there is a JSON API
for game clients (`/api/v1`, see [docs/API.md](docs/API.md)), so a Unity or mobile version can use the same cases,
votes and judge profiles as the website.

> Until October 2026 the site ran on PHP. The Python site took over its database in place: accounts, votes and
> old `.php` links all still work. The PHP code lives in the first commit of the git history.

## Run it locally

Python 3.9+ and MySQL 5.7+/8.0 (or MariaDB 10.3+).

```
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt        (Linux/macOS: .venv/bin/pip …)
set VERDICT_DB_PORT=3306                                 (only what differs from the defaults below)
.venv\Scripts\python run.py                              → http://127.0.0.1:8000
```

On the first request the site creates the database and tables, the first team account and 48 demo cases.

## Configuration

Environment variables win over `config.json` in the project root (copy `config.example.json`), which wins over the defaults.

| Setting | Default | Environment variable |
|---|---|---|
| MySQL host / port | `127.0.0.1` / `3306` | `VERDICT_DB_HOST`, `VERDICT_DB_PORT` |
| Database | `verdict` | `VERDICT_DB_NAME` |
| User / password | `root` / *(empty)* | `VERDICT_DB_USER`, `VERDICT_DB_PASSWORD` |
| First team password | `verdict-admin` | `VERDICT_ADMIN_PASSWORD` |
| Secret key | random per start | `VERDICT_SECRET_KEY` |
| Session lifetime | 14 days | `VERDICT_SESSION_LIFETIME` (seconds) |
| New accounts an hour, in all / from one address | 30 / 5 (0 = no limit) | `VERDICT_MAX_SIGNUPS_PER_HOUR`, `VERDICT_MAX_SIGNUPS_PER_IP` |
| Proxies to trust for the visitor's address | 0 | `VERDICT_TRUSTED_PROXIES` |
| Telegram bot token (from @BotFather) | *(none: no bot)* | `VERDICT_TELEGRAM_TOKEN` |
| Key in the hourly cron address `/cron/<key>` | made and kept in the database | `VERDICT_CRON_KEY` |
| Hour of the case-of-the-day reminder (UTC) | 14 (19:00 Tashkent) | `VERDICT_DAILY_HOUR_UTC` |

If your MySQL user cannot create databases, create one and import `database/schema.sql`.

## First login

| Login | Password | Role |
|---|---|---|
| `admin` | `verdict-admin` (or `VERDICT_ADMIN_PASSWORD`) | Team |

**Change this password right after the first login** (Профиль → Смена пароля). The config value is used only once,
when the account is created. Accounts made on the old PHP site keep working (same bcrypt hashes).

## Upload packages (`dist/`)

```
.venv\Scripts\python scripts\build_dist.py
```

| File | What it is |
|---|---|
| `dist/verdict-python/` | the Python site, unpacked: upload its contents to the application folder |
| `dist/verdict-python.zip` | the same as one zip (files at the top level) |
| `dist/verdict-python-no-js.zip` | without `assets/js/*.js`, for hosts whose virus scanner wrongly flags the zip; upload `assets/js/` separately |

Rebuild after every change; `dist/` is generated and can be deleted at any time.

## Deploy on cPanel («Setup Python App»)

1. **MySQL Databases**: create a database and a user, add the user to the database with all privileges.
2. **Setup Python App → Create application**: Python 3.9 or newer; *Application root* e.g. `verdict`;
   *Application URL* your domain (or a sub-path); *Application startup file* `passenger_wsgi.py`;
   *Application Entry point* `application`.
3. **File Manager**: open the application root, upload `verdict-python.zip` and extract it there.
4. Back in **Setup Python App**: add environment variables `VERDICT_DB_HOST` = `localhost`, `VERDICT_DB_NAME`,
   `VERDICT_DB_USER`, `VERDICT_DB_PASSWORD` (the cPanel names include your account prefix), `VERDICT_SECRET_KEY`
   (any long random text), `VERDICT_ADMIN_PASSWORD`. Then *Run Pip Install* with `requirements.txt`, and **Restart**.
5. Open the site. To update later: upload the new zip over the old files, then *Restart*.

A database created by the old PHP site upgrades in place on the first visit: the Python site adds its own tables
and columns and the demo cases it is missing (a case whose title already exists is skipped). Accounts and
verdicts carry over; old links such as `case.php?id=3` redirect to the new addresses.

**The application root is the folder that holds `passenger_wsgi.py`, `requirements.txt` and the folders `verdict`,
`content`, `assets` side by side** — not the inner `verdict` folder (that one is the code). Pointed one level too
deep, cPanel puts its own placeholder `passenger_wsgi.py` there and the site answers «Web application could not be
started». If the application folder has to stay inside the web folder (a subdomain's folder, say), the `.htaccess`
files shipped in `verdict/`, `content/`, `docs/` and `database/` keep those folders from being downloaded.

`VERDICT_DB_HOST=localhost` connects through the MySQL socket, like PHP did (shared hosts often allow the database
user only from localhost); set `VERDICT_DB_SOCKET` if the host keeps the socket somewhere unusual. Pages are sent
with `Cache-Control: private`, so a cache in front of the site (Engintron/nginx on many cPanel servers) doesn't hand
one visitor's page to another. Such a cache may still show an old page for a while after an error is fixed; adding
`?1` to the address shows what the site answers right now.

If a page shows «База данных недоступна», a `VERDICT_DB_*` value is wrong. If the site can't start at all, the page
says why in one line («VERDICT could not start …») and `startup-error.txt` in the application folder has the details;
if the page is Passenger's own grey error instead, the failure is before the site's code runs (Python version, packages
not installed) — see the *Passenger log file* set in the application's settings. Fix, then *Restart*. Set `VERDICT_SECRET_KEY` — without it the site
keeps a generated key in the database, which works, but a key of your own is cleaner.

### Hourly cron

Add one more cron job, *Once per hour*: admin → «Игра» shows the exact command with the site's key, like

```
curl -fsS https://verdict.azero.uz/cron/<key> > /dev/null
```

It closes finished seasons (a visit would do it too, but this doesn't wait for one), sends the Telegram reminder of
the case of the day once the reminder hour has come, and clears expired one-time codes.

### Telegram bot

1. In Telegram, open **@BotFather**, send `/newbot`, choose a name («VERDICT — суд») and a username ending in `bot`.
   It answers with a token like `123456:ABC…`.
2. «Setup Python App» → add `VERDICT_TELEGRAM_TOKEN` = that token → *Restart*.
3. Admin → «Игра» → «Подключить бота». The site asks Telegram for the bot's name, sets the webhook
   (`https://<site>/telegram/hook`, checked by a secret header derived from the token) and the command menu.
4. Profile → «Подключить Telegram» on your own account, «Запустить» in the bot, then admin → «Прислать мне проверку».

Players then link their chat in the profile (a one-time code in a `t.me` link, valid for an hour) and get there:
every notification (switchable), the case of the day after the reminder hour unless they judged it already
(switchable), and — from «Забыли пароль?» on the login page — a one-time link for a new password, valid for 30
minutes. Commands: `/today`, `/me` (rank, XP, streak, season place), `/stop`, `/help`. Messages go out after the
page has been answered, so a slow Telegram never slows the site; a player who blocks the bot is unlinked on the next
reminder. Without a token none of this shows, and «Забыли пароль?» tells the player to write to the team.

### Uptime monitor

`/health` answers `{"ok": true, "database": "ok", "schema": 9, …}` with status 200 while the site and its database
work, and 503 otherwise; it is never cached. Point a free monitor (UptimeRobot, Better Stack, cron-job.org) at
`https://<your site>/health`, every 5 minutes, alerting by e-mail or Telegram when the status isn't 200.

### Daily database backup

Everything players did lives in MySQL, so back it up every day. In cPanel → **Terminal** (or over SSH), once — with
your `VERDICT_DB_USER` and `VERDICT_DB_PASSWORD` in place of the two placeholders:

```
mkdir -p ~/backups && chmod 700 ~/backups
cat > ~/.my.cnf <<'EOF'
[mysqldump]
user=DB_USER
password=DB_PASSWORD
EOF
chmod 600 ~/.my.cnf
```

Then cPanel → **Cron Jobs** → *Once per day*, this command with your `VERDICT_DB_NAME` in place of `DB_NAME` (the
`\%` is how cron wants a `%`):

```
mysqldump --single-transaction --no-tablespaces DB_NAME | gzip > ~/backups/verdict-$(date +\%F).sql.gz; find ~/backups -name 'verdict-*.sql.gz' -mtime +14 -delete
```

That keeps two weeks of copies outside the web folder. Download one now and then (File Manager → `backups`) so a
copy also exists off the server. To restore: phpMyAdmin → the database → *Import* the `.sql.gz` file. cPanel's own
**Backup** page can also download a full database copy by hand.

The site needs a host with Python 3.9+ («Setup Python App» on cPanel, or any WSGI server).

## Game data — `content/`

- `content/catalog.json` — categories, situation types, world meters, world types, levels, statuses, judge styles.
  The site reads its dictionaries from here, and a game client can read the same file (or `GET /api/v1/catalog`).
- `content/cases/NNN.json` — the demo cases, one per file, with `batch` and `status`. Each batch is inserted into
  the database once (`meta.seeded_vN`), so deleted cases don't come back and a new batch reaches existing databases.
  Batch 1–2: the 28 original demo cases; batch 3: the 20 cases from classic legal and ethics problems.

To add demo content, put new files with the next batch number into `content/cases/`. Cases written on the site
live in the database; export them with `/api/export` (team only).

## Accounts and sessions

- **Authors** register at `/register` (login, display name, password of 8+ characters). Adding a situation needs an
  account; the author signature comes from it.
- The creator form has **three levels**; switching hides fields but never drops what was typed.
  The rules are in `situation_level()` (`verdict/repository.py`) and mirrored in `assets/js/create.js`.

  | Level | Adds | Required for the level |
  |---|---|---|
  | 1 · Идея (~3 min) | category, type, title, story, decision texts | category, title, story ≥ 20 words, 2+ decisions |
  | 2 · Дело (~15 min) | world, participants, facts, witnesses, "why", main conflict | everything `situation_validate()` checks — needed to submit |
  | 3 · Полное досье (~30 min) | consequences, world effects, hidden info, arguments, continuation, notes, checklist | consequences and effects for 2+ decisions, hidden info, both arguments |

- **Drafts** can be saved at any point (only the title is required), are visible to the author only, and can be
  deleted by the author. «Отправить на отбор» checks the full template and moves a draft to **pending**.
- Authors edit their own situations while they are **draft** or **pending**, and see their own hidden info.
- The form keeps a copy of itself in the browser (`localStorage`) and offers it back after a closed tab; the server
  clears that copy after a successful save. If the login session ended before sending, the text is kept in the
  session and returned to the form after logging in again.
- The **team** (role `admin`) approves or rejects situations, edits anything, sees hidden info and exports JSON, and
  promotes authors on `/users`. The last team member can't be demoted.
- Five failed logins lock the form with a growing delay; ten wrong passwords for one login in 15 minutes lock that
  login for everyone (the same lock as the game client's sign-in), so clearing cookies doesn't reset it.
- The sign-up form has a hidden field people don't see and refuses a form sent sooner than `min_signup_seconds`
  (3 by default) after it was opened — two cheap brakes on bots.
- Sign-ups on the site and in the game API are limited: `max_signups_per_hour` (30) in all and `max_signups_per_ip` (5)
  an hour from one address, kept only as a keyed hash for a day. The per-address limit works only when the site sees
  real visitor addresses — behind a proxy that hides them it switches itself off rather than stop everyone. Admin →
  «Игра» shows the address the site sees; `VERDICT_TRUSTED_PROXIES=1` takes it from `X-Forwarded-For` instead.
- **Sessions are stored in MySQL** (`sessions` table) for 14 days of inactivity. Each row records `user_id`, so
  changing the password or «Выйти на других устройствах» ends the user's other sessions. A new password also signs
  the account out of every game client.
- Players don't need an account. Votes use an anonymous cookie id (`verdict_vid`); game clients send their own id.
- **An account keeps the progress.** Signing up attaches the browser's player (verdicts, career, gifts) to the new
  account. Signing in on another device switches that browser to the account's player and merges whatever it did
  anonymously before (where both judged the same case, the account's verdict stays). Signing out gives the browser a
  fresh anonymous player, so the next person at a shared computer doesn't play as you. The player id is a secret
  (it is the key to the verdicts); the public side of a player is the account. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Pages

| URL | What it does |
|---|---|
| `/` | Landing page: **Дело дня**, how it works, formats, 10 categories, worlds, most controversial case, roadmap |
| `/quick`, `/quick/<id>` | **Быстрый суд** (the header «Играть» button): the case of the day first, then random unjudged cases, as a comic, then two taps — verdict, then a guess of the majority choice (keys 1–9 work). The reveal shows whether the guess matched the other players' votes before yours (ties count), the split, the consequence and a score/streak |
| `/judge`, `/judge?a=<style>` | **Профиль судьи**: career (rank, XP, title, days in a row, achievements), **gifts and trophies** (with the choice of title); after 5 verdicts also the judging style, which world meters the player pushes up or down, agreement with the majority, guess accuracy, decision time, boldest call; `?a=` shows a shared style |
| `/campaigns`, `/campaign/<key>` | **Story campaigns**: a few linked cases — before each chapter, what your earlier verdicts led to; several endings |
| `/ratings` | **Рейтинг**: season (this month), all time, majority-guess accuracy, day streak — among everyone, friends or a community |
| `/u/<login>` | A player's public profile: rank, XP, title, style, achievements, trophies, communities, season place; add to friends |
| `/friends` | Friends: add by login, requests in and out, the list |
| `/communities`, `/c/<slug>` | Communities: list, search, create; a community's rules, joining, members, requests, invite link, rating, settings |
| `/play` | Case archive with category/type filters, progress and world meters |
| `/case/<id>` | Case file (world and story as a comic, then participants, evidence, witnesses) and a hold-to-confirm verdict; the result shows consequences, the split, the controversy index and the debate |
| `/create`, `/create/<id>` | Creator form (login required): all 12 template sections plus the checklist; `/<id>` edits |
| `/library` | Selection board: sprint progress, status tabs, «Мои», moderation |
| `/view/<id>` | Full dossier; hidden info only for the team and the author |
| `/brief` | The creator brief |
| `/login`, `/register`, `/account` | Sign in, sign up, profile (rename, change password, end other sessions) |
| `/users` | Team only: accounts and roles (also «Команда» in the admin panel) |
| `/admin` | Team only: **admin panel** — overview with analytics, players, treasure hunts, gifts, the case of the day; see below |
| `/api/export` | Team only: approved situations as JSON (`?status=all`, `?id=N`) |
| `/api/v1/…` | Game-client API, see [docs/API.md](docs/API.md) |

Old addresses (`case.php?id=3`, `create.php?edit=5`, `api/vote.php` …) redirect to the new ones, so shared links keep working.

## Judge career

`verdict/career.py`, content in `content/catalog.json` (`xp`, `ranks`, `world_levels`, `world_events`, `achievements`).
Whatever the votes can tell is computed from them; the `players` table keeps only what they can't.

- **XP and ranks.** A verdict on a case gives 10 XP (once per case), a right majority guess 5, the case of the day
  on its day 15. Seven ranks from «Стажёр» (0) to «Верховный судья» (520) — about the whole archive played well.
- **Дело дня.** One case for everyone per day (UTC), stored in `meta` as `daily:YYYY-MM-DD`, not repeated within
  30 days, replaced if it leaves the game. Shown on the landing page and served first by «Играть».
- **Days in a row.** Counted on the first verdict of each day; the record is kept.
- **The world remembers.** Meters are computed from all the player's verdicts since their last «Начать мир заново»,
  so the world survives closed browsers and is the same in the game API. A meter at ≤ 20 / ≥ 80 starts a world event,
  at 0 / 100 a stronger one (20 events, each announced once per world, then listed in the «Состояние мира» panel).
- **Achievements.** 13, checked after every verdict and kept once unlocked.
- **Gifts** from treasure hunts or the team add their XP; a title gift is shown under the rank.
- After a verdict the result shows XP gained, the rank and the way to the next one, a rank-up, new events and
  achievements. Pacing was checked by simulating players: a consistent style reaches the first world event in
  4–6 cases, random play in 10–20.

## Story campaigns (`/campaigns`)

`verdict/campaigns.py`, content in `content/campaigns/*.json`. A campaign is a chain of cases. Before each chapter the
player reads what their earlier verdicts led to (`after`: texts per chapter and option, `*` for anything else); the
chapter's choice moves the campaign's own small world (meters from 50, like the player's world), and the ending is
the first in `endings` whose `when` matches (`min`/`max` meters, `chose` options), the last one being the default.

- The first chapter may be an archive case (`"title"`): a player who already judged it continues from that verdict,
  and its result screen in the archive invites to the campaign. Other chapters are cases of their own (`"case"`),
  put into the database once with status «В кампании» — they don't appear in the archive, Быстрый суд or the case of
  the day, and the team sees them on the review board.
- A verdict in a chapter counts in the case's split the first time only; replays («Пройти заново») change the run,
  not the split. The first ending brings a trophy and +40 XP (`xp.campaign`).
- Ships with «Последний Рубеж» (from «Три ампулы») and «Гелиос-7» (from «Протокол «Тихий час»»), 4 endings each;
  every ending was checked to be reachable by simulating all 96 paths.

## Players together (`/ratings`, `/u/<login>`, `/friends`, `/communities`)

`verdict/social.py`. Everything social belongs to accounts — a player without an account plays as before and is
invited to sign up (the progress made so far comes along).

- **Profiles.** `/u/<login>` shows the career (rank, XP, title, streak, cases of the day, season place), the judge
  style, unlocked achievements, trophies (badge and title gifts — never codes or messages) and communities. On
  «Профиль» (`/account#public`) a player writes a short bio, chooses who sees the profile (everyone / friends /
  only me) and whether to appear in ratings. Verdicts on particular cases are never on the profile.
- **Friends.** Requests by login or from a profile; asking someone who already asked you makes you friends. After a
  verdict the result shows **how your friends judged the same case** (friends with a private profile are left out).
- **Ratings.** Season = the calendar month (UTC): XP from cases judged *for the first time* this month (a re-vote
  doesn't move a case into the new season, so old cases can't be farmed), right majority guesses, cases of the day
  on their day, gifts. Also all-time XP, «Чутьё» (majority-guess accuracy, from 10 guesses) and the current day
  streak. Ties share a place. Shown for everyone, for you and your friends, or for a community. Players barred by
  the team (admin → player → «Отстранить») are left out, as are those who hid themselves.
- **Reports.** «Пожаловаться» on a profile, a community page and under a case result (accounts only, one open report
  per target). The team handles them in admin → «Жалобы»: bar the player, delete the community, take the case out of
  play, close or dismiss. A barred player is out of ratings and hunts and can't add friends or join/found communities.
- **Sharing.** Result screens and campaign endings have «Поделиться» (the phone's share sheet or a copied link) and a
  Telegram button; pages carry link-preview tags, so a shared case shows its title and story in messengers.
- **Communities.** Anyone with an account can found up to 5. Each has a description, **rules** (accepted when
  joining), an emblem and colour, and an access mode: open, by request (the founder or a moderator approves), or by
  invite link only. An invite link lets its holder straight in and can be replaced. The founder appoints moderators;
  moderators accept requests and remove members (not other moderators). Each community has its own rating. The team
  sees all communities in admin → «Сообщества» and can remove one.

## Discussion under a case (`/talk/<id>`)

- Opens after the player's own verdict (the arguments give away where the majority leans); the result screen shows
  how many comments there are, quotes the two most backed and links to the discussion.
- Accounts write; every comment carries the verdict its author had when writing, and comments from players who
  judged like you are marked «как вы». Others press «Поддерживаю» (once, not on their own comment); the author is
  told at 1, 5, 10, 25… backers. Sorted by backing or newest; filtered to friends or one of your communities.
- Brakes: 3–1000 characters, one comment per 15 seconds, 30 a day; a barred player can't write or back.
- Moderation: players report a comment like a profile; the team hides it (from the report, on the page or in admin →
  «Обсуждения», where the latest comments everywhere are listed) and the author is told. Hidden comments stay
  visible to the team only.

## Seasons and notifications

- **Seasons.** The season rating is a calendar month (UTC). The first visit after a month ends closes it: the final
  board (first 50 places) is kept on `/seasons` and `/seasons/<YYYY-MM>`, the top places get a trophy as a gift (1st:
  the title «Чемпион сезона «…»» +100 XP; 2nd–3rd and 4th–10th: badges +50 / +20 XP — set in `content/catalog.json`,
  `seasons`), and every placed account is told where it finished. A trophy counts in the career, not in the next
  season. Closing happens once even with several processes (the season row is claimed first), and only for months
  since this version first ran.
- **Notifications** for accounts — the bell in the header with the unread count, `/notifications` (seen = read),
  the game API, and the player's Telegram when they linked it (see «Telegram bot»). Sent when someone asks to be friends or accepts, asks to join a community (to its founder and
  moderators), is accepted or made a moderator, when the team approves or rejects an author's case, gives a gift,
  closes the player's report, and when a season closes. The page also reminds of the case of the day while it's
  waiting. Kept for 90 days.

## Admin panel (`/admin`)

Team accounts get «Админка» in the header. Sections:

- **Обзор** — the numbers, by UTC day: active players today / 7 / 30 days, new players, verdicts, return rate the
  next day (D1) and within a week (D7, only for players whose week is over), players with a verdict and with an
  account, situations waiting for review. Charts (each with a table view and values on hover): active players per
  day split into new and returning, verdicts per day, the player's path from the first visit to an account, verdicts
  by hour (when to run a hunt), Быстрый суд vs the full case file with the typical time to decide, the case of the
  day and how many judged it, verdicts by category, players by rank, achievements, the most played / most divisive /
  least played cases. Alerts: a hunt that is on, a gift whose codes run out.
- **Игроки** — every player: anonymous (cookie id) or with an account; search by login, name or the start of the id;
  filters (with verdicts, with an account, blocked, every visitor) and sorting. A player's page shows rank, XP,
  streak, activity, style, recent verdicts, gifts and finds, and lets the team give a gift by hand, take one back,
  bar the player from the hunt, start their world anew, or delete all their game data. For a player with an
  account, «Новый пароль» sets a random password, shows it once to the team member and ends all of the player's
  sessions — there is no email, so this is how a forgotten password is fixed. The dashboard warns while the `admin`
  account still has the setup password.
- **Охота** and **Подарки** — treasure hunts, see below.
- **Игра** — the case of the day for the next 7 days (pick any case for any day), XP and rank thresholds, links to
  the review board, the team and the JSON export.

Activity is recorded per player and day (`player_days`): a page view counts once the browser kept its cookie (so
bots and one-off hits don't inflate the numbers), and every call from the game client counts. Days with a verdict
before this table existed were filled in from the votes.

## Treasure hunts and gifts

`verdict/hunt.py`. From time to time the team hides spots on the site: a player who notices one and clicks it gets a
gift. Gifts are set by the team:

| Kind | What the finder gets |
|---|---|
| Опыт (`xp`) | XP towards the rank (any gift can also carry XP) |
| Трофей (`badge`) | a collectible card in «Подарки и трофеи» on the judge page |
| Титул (`title`) | a title shown under the rank; a player with several picks which one to wear |
| Код (`code`) | their own code from a pool the team uploads (one per line) — prizes, discounts, merch |
| Послание (`message`) | a text and a link from the team |

A gift can be limited to players with an account — they are offered to sign in first, so the team knows who won.
The player keeps a copy of the gift as it was when found; editing or deleting the gift later doesn't change it.

**Running a hunt:**

1. **Подарки** → create the gifts (for codes, paste the list).
2. **Охота** → «Новая охота»: title, an announcement (shown to players), start and end in UTC, optionally a main prize
   for finding every spot, and whether to show the hunt badge (bottom-left on every page: progress and hints).
3. Add spots: where (a page of the site, every page, or a scene of the game client), the gift inside, a hint, the
   icon, its size and how visible it is (почти невидимый / едва заметный / заметный), and how many finders get the
   gift (0 — all).
4. «Разместить»: the page opens in placement mode — hover and click where the spot should hide. The spot is tied to
   that element and a point inside it, so it stays in place on any screen width. Choose whether it shows only on
   this page, on every page of this kind, or on every page. «Посмотреть на странице» shows the spots as the team sees them.
5. «Запустить». Spots appear while the hunt is on and inside its dates; a found spot disappears for that player.
   «Кто что нашёл» lists finds, codes and players; a cheater can be barred from the hunt on their page.

Each spot carries a claim token tied to the player, so spot ids can't be tried one by one; the site is still a web
page, so for valuable prizes use «only for players with an account» and a limited number of finders. Spots are
not in the Tab order — they are found by eye.

The game client gets its own spots (page `unity:<scene>`, x/y in % of the screen) from `GET /api/v1/hunt` and claims
them with `POST /api/v1/hunt/spots/<id>/claim`, see [docs/API.md](docs/API.md).

## Judge profile

`verdict/judge.py`. For every verdict and every world meter, the chosen decision is ranked against the other options of
the same case: r = (options it beats − options that beat it) / (options − 1). The meter's **lean** is the average r
over the cases where the options differed on that meter, from −100% to +100%. Ranking against the alternatives
(not raw effects) means a random choice averages exactly 0 and rarely-used meters (resources) weigh the same as
common ones. The style comes from order (authority + stability) and trust together — 11 styles from
«Страж порядка» to «Мудрый правитель» — with resources or reputation deciding only when they are stronger than both.
Thresholds were tuned by simulating deliberate and random players on the cases.

## Editing cases that already have votes

Decision letters (A, B, …) are positions and change when a decision is removed or reordered; votes and Быстрый суд
guesses store the letter. Each decision therefore has a permanent `uid` (older decisions get `k` + their letter on
load). `situation_update()` moves votes and guesses to the new letters in the same transaction (`votes_remap()`);
votes for a removed decision are deleted. The editor shows each decision's vote count and asks before removing one
that has votes.

## Case as a comic («Дело в кадрах»)

Every case is shown as a comic built from its data — authors write nothing extra (`verdict/comic.py`,
`verdict/templates/partials/comic.html`, `assets/js/comic.js`). Frames: the world (with «Ваша роль»), one frame per
story paragraph, and in Быстрый суд also «Кто есть кто», «Что известно», witnesses and «Ваш вердикт». An animated
SVG scene per world type, portraits generated from name, age and role, «quoted» lines as speech bubbles of the
character who says them. The API returns the same frames, so a game client can draw them its own way.

## Game feel (`assets/js/juice.js`)

Small effects that make a verdict feel like one, all synthesised in the browser (no media files):

- Picking an option stamps «Вердикт» on it with a gavel sound and a short vibration on phones; the hold-to-confirm
  button ends with a screen strike. On a campaign chapter the stamp plays before the form is sent.
- On the result: percentages count up, the earned XP flies to the rank chip in the header and is added to it, the
  rank bar fills, confetti bursts on a rank-up, a new achievement, a found gift or a campaign ending, and the
  consequence types out (click to finish). Sounds: a chord for a right guess, a low note for a wrong one, a fanfare
  for a rank-up.
- Living details: comic characters breathe and the speaker bobs, option cards glow under the cursor, hidden spots
  glint every few seconds, the case-of-the-day timer ticks, pages cross-fade (View Transitions, where supported).
- The speaker button in the header mutes sounds; the choice is kept in `localStorage` (`verdict:sound`).
- With the system setting «reduce motion» only sounds and final values remain: no stamps flying in, confetti,
  typing or shaking.
- **«Меньше эффектов»** (the footer, and the menu on phones) does the same plus a still background without glow, blur
  or animations — for older phones. It's on by default on a weak device (≤ 2 GB memory or ≤ 2 cores) until the
  player chooses; the choice is kept in `localStorage` (`verdict:fx`) and applied before the page paints.

## Installable app

The site is a PWA: `assets/manifest.webmanifest` (name, icons, shortcuts to Быстрый суд, the judge profile and the
rating) and a service worker at `/sw.js`. Phones offer «Установить» / «На экран Домой», and Chrome's install button
appears; the footer shows «Установить приложение» where the browser allows it. The worker keeps styles, scripts,
images and fonts in a cache named after the newest file in `assets/` (a new upload starts a fresh cache) and serves
pages always from the network — they are personal and never stored. Without a network it shows `/offline`, a page
with nothing personal in it. The icons are drawn from the logo by `scripts/make_icons.py` (it needs Chrome).

`Juice.verdict(el)`, `Juice.strike(el)` and `Juice.result(container)` are the hooks pages call (`quick.js`, `case.js`).

## Dialogs and dropdowns

`assets/js/modal.js` replaces `alert()`/`confirm()`: `<form data-confirm="…" data-confirm-title data-confirm-ok
data-confirm-tone="danger|warn|success">` asks first; `<form data-validate novalidate>` lists missing fields.
`assets/js/select.js` turns every `<select class="vs">` into a neon dropdown (options may carry `data-icon` — the
template helper `option_icon('crown', 45)` — `data-hue`, `data-desc`; `data-autosubmit` submits on pick).

## Tests

```
set VERDICT_TEST_DB_PORT=3306       (server, user and password: VERDICT_TEST_DB_HOST / _USER / _PASSWORD)
.venv\Scripts\python -m pytest tests
```

The tests drop and recreate the database `verdict_pytest` (change with `VERDICT_TEST_DB_NAME`). They cover every page,
old-link redirects, drafts and levels, moderation, accounts and sessions, Быстрый суд scoring, vote remapping, the
judge profile, the career (case of the day, XP, streaks, world events, achievements), accounts carrying the progress
across devices, the admin panel and its numbers, treasure hunts and gifts (placement, dates, limits, code pools,
accounts-only gifts, blocked players, the main prize), profiles and their privacy, friends, ratings (season by first
verdict, scopes, ties, opt-out), communities (rules, access modes, roles, invite links, limits), story campaigns,
reports and bans, security (per-login lock, sign-up brake, token expiry, team password reset), seasons, notifications,
discussions, the installable app and the game API; a test keeps `database/schema.sql` equal to the migrations.
`tests/fixtures/comic_expected.json` was produced by the PHP comic engine; the Python engine must give exactly the
same frames, speakers, portraits and scenes for all 48 cases.

### Browser tests

```
.venv\Scripts\python tests\e2e\run.py                  all scenarios (about a minute)
.venv\Scripts\python tests\e2e\run.py hunt quick       some of them; -v prints every check
.venv\Scripts\python tests\e2e\run.py --shots shots    screenshots of the main pages, desktop and phone
.venv\Scripts\python tests\e2e\run.py --serve          the seeded test site on http://127.0.0.1:8099
```

GitHub runs the linter, pytest and the browser tests on every push to `main` (`.github/workflows/tests.yml`, MySQL 8
as a service); the badge at the top shows the last result. The browser tests need Chrome (or Chromium, Edge; set
`CHROME` for another path) and the same MySQL as pytest; the database
`verdict_e2e` (`VERDICT_E2E_DB_NAME`) is dropped and rebuilt, then filled with a running hunt, a hunt in preparation,
a player with a judge profile and a month of made-up activity. Each scenario in `tests/e2e/scenarios/` is a script
the runner adds to the real pages in headless Chrome: it clicks, types and holds buttons like a player and reports
PASS/FAIL lines. They cover the archive filters, the judge profile, Быстрый суд with keys and a change of mind, the
game-feel effects, the comic, the hold-to-confirm verdict, writing a case from sign-up to submission, removing a
decision that has votes, a whole treasure hunt, placing a spot by clicking, every main page at 360 px wide and the
header from phone to wide screen, the «Меньше эффектов» switch, a discussion from verdict to comment, and the
installable app (service worker, cache, manifest).
Headless Chrome on Windows won't make a window narrower than about 500 px, so phone widths are checked and
screenshotted inside a frame of the right width (`/__phone`); phone screenshots have a dark strip on the right.

## Structure

```
run.py                 local development server
passenger_wsgi.py      entry point for cPanel / any WSGI server
requirements.txt       Flask, PyMySQL, bcrypt, regex
verdict/               the application
  __init__.py          app factory, template helpers, error pages
  routes.py            every URL, and redirects from the old .php addresses
  config.py catalog.py db.py sessions.py auth.py repository.py web.py forms.py helpers.py icons.py
  comic.py judge.py    comic engine, judge profile
  career.py            XP and ranks, case of the day, day streak, the player's world and its events, achievements
  players.py           activity by day, players ↔ accounts (link, merge on sign-in), the team's view of players
  hunt.py              treasure hunts, hidden spots, gifts, code pools, finds
  social.py            public profiles, friends, ratings, communities, reports
  campaigns.py         story campaigns: chapters, bridges, the campaign's world, endings
  gameauth.py          sign-in from the game client (hashed tokens, slowed-down guessing)
  seasons.py notify.py signups.py  closing seasons with trophies; notifications; sign-up limits
  telegram.py          the bot: linking chats, notifications, the case-of-the-day reminder, password reset
  talk.py              the discussion under a case
  analytics.py charts.py  the admin overview: numbers and chart shapes
  views/               pages, authoring, accounts, social, campaigns, admin (the team's panel), api (site JSON), api_v1 (game clients)
  templates/           Jinja templates (layout, pages, partials)
content/               catalog.json, demo cases and story campaigns (shared with game clients)
assets/                CSS, JavaScript, images (served at /assets)
database/schema.sql    manual schema import (schema v11; a test keeps it equal to the migrations)
scripts/build_dist.py  builds dist/; scripts/make_icons.py draws the app icons
tests/                 pytest suite; tests/e2e/ — browser scenarios and their runner
docs/API.md            game-client API
docs/ARCHITECTURE.md   how the game is put together, and where friends, communities and ratings will go
```
