# VERDICT — project review

*29 October 2026. Written for the project owner and whoever works on the code next. Facts below were measured on
this date; opinions are marked as such.*

## In one paragraph

VERDICT is a complete, working product: a Russian-language judgment game with 48 cases and two story campaigns, a
career system, treasure hunts, a social layer (profiles, friends, ratings, communities), a team admin panel with
analytics, and a documented JSON API that a Unity client can use for everything the website does, including sign-in.
The code is small for what it does (7.3k lines of Python), clean (linter-clean, no TODO debt), and covered by 190
automated tests plus real-browser scenarios. It is live at https://verdict.azero.uz on cPanel. The weak spots are not
in the game logic but around it: **there is no version control, no backups and no monitoring**, a few security
corners need tightening before the player base grows, and the visual side still runs on generated comics rather than
real illustrations.

## What is here

| Area | Size | State |
|---|---|---|
| Server (Flask, `verdict/`) | 7,264 lines Python, 74 routes (30 game API, 12 admin) | solid |
| Front-end | 2,754 lines JS (11 plain scripts, no build step), 2,302 lines CSS (one file), 54 templates | solid, one big CSS file |
| Content | 48 cases, 2 campaigns × 3 chapters, catalog with ranks, events, achievements, gifts | good for an MVP; art is generated |
| Tests | 190 pytest tests (2,366 lines), 10 browser scenarios, screenshots at desktop and phone width | strong; browser tests live outside the repo |
| Docs | README (deploy, every feature), docs/API.md (with a C# sample), docs/ARCHITECTURE.md | thorough |
| Database | MySQL, schema v8, 17 tables, self-upgrading; manual `schema.sql` | fine |
| Legacy | 39 PHP files of the old site still in the folder, PHP zips still built | dead weight |

## Strengths (keep these)

- **One source of truth.** XP, ranks, the world, the judge style and the ratings are computed from the votes, not
  stored; a withdrawn case or an edited verdict can't leave stale numbers behind.
- **Players never lose progress.** Anonymous play first; an account picks up what the device did; signing in on a
  second device merges it; the game client shares the same player.
- **The team can run the game without a developer:** case of the day, hunts and gifts, player management, reports,
  analytics with return rates. Content (cases, campaigns, catalog) is JSON that a non-programmer can edit.
- **Safety basics are right:** CSRF on every form including admin, parameterised SQL everywhere, bcrypt passwords,
  hashed API tokens, HMAC-signed hunt claims, invite codes compared in constant time, private pages never cached by
  the host's nginx, source folders closed to the web.
- **Tests are behavioural**, not cosmetic: they register users, vote, run whole campaigns, claim spots, bar players.
- **Deploy is boring in the good way:** one zip, extract, restart; the database upgrades itself; a startup failure
  prints its reason on the page.

## Findings

Severity: **High** — fix before promoting the game; **Medium** — fix in the next few weeks; **Low** — when convenient.

### Process and operations

1. **High — no version control.** The project folder is not a git repository. One wrong save or a failed upload and
   there is no way back; there is also no record of what changed when. `git init`, commit, push to a private
   repository (GitHub/GitLab). `.gitignore` already exists; `dist/`, `.venv/`, `config.json` must stay out.
2. **High — no database backups.** The live database holds every verdict, account and gift; the host's own backups
   are unknown. Turn on cPanel's backup or a daily `mysqldump` cron job, and download a copy weekly.
3. **Medium — browser tests are not in the repo.** The 10 headless-Chrome scenarios (vote, quick, comic, play,
   create, remove, judge, hunt, place, screenshots) live in a temporary folder of the development machine. Move them to
   `tests/e2e/` with the proxy and the runner script, so they survive and others can run them.
4. **Medium — no monitoring.** Nobody is told when the site is down or erroring. A free uptime check (e.g. every
   5 minutes on `/api/v1/`) and a look at the Passenger log after each deploy are enough for now.
5. **Low — PHP leftovers.** 39 PHP files and the `--php` zips are no longer used by the live site. Keep one archive
   zip for history and delete them from the project; it halves the root folder and removes a second copy of game
   rules that can drift.
6. **Low — no CI.** Tests need a MySQL server, which is why they aren't automated. A GitHub Actions job with a MySQL
   service would run the 190 tests on every push in about a minute.

### Security

7. **Medium — website login lockout is per browser session.** Five failures lock the *session*; an attacker who
   drops the cookie starts fresh. The game API already locks per login (10 failures / 15 minutes in `auth_failures`).
   Use the same per-login lock for the website form (`verdict/views/accounts.py` → `gameauth.locked/failed`).
8. **Medium — registration has no brake.** Neither the site nor the API limits sign-ups per IP or asks a question a
   bot can't answer. Fake accounts would pollute ratings and communities. Options, cheapest first: a hidden honeypot
   field, a per-IP limit (e.g. 5 sign-ups per hour), an "invite-only registration" switch in the admin panel.
9. **Medium — game tokens never expire and survive a password change.** `api_tokens` rows live forever; «Сменить
   пароль» ends website sessions but not game sessions. Expire tokens unused for 90 days and delete the account's
   tokens on password change (one `DELETE` in `user_set_password`).
10. **Medium — no password reset.** There is no email sending, so a player who forgets the password is stuck, and
    the team has no "set a new password" button either. Short term: a reset button on admin → player (shows a
    one-time password). Long term: email with SMTP from the host.
11. **Low — the player cookie is not `Secure`.** `verdict_sid` is sent with `Secure` on the live site (checked);
    `verdict_vid` is not (`verdict/web.py: remember_voter`). Add `secure=request.is_secure` — the id is the key to
    the player's verdicts.
12. **Low — default admin password.** `verdict-admin` is the fallback when `VERDICT_ADMIN_PASSWORD` is unset. A
    warning on the admin dashboard when the `admin` account still has that password would catch a forgotten step.
13. **Known and accepted:** the player id (`X-Voter-Id` / cookie) is a bearer secret; hidden spots can be found
    with browser developer tools (mitigated by accounts-only gifts and finder limits); hunt placement selectors are
    trusted admin input.

### Game logic and content

14. **Low — a campaign chapter can be moved into the archive by mistake.** On the review board a chapter with
    status «В кампании» shows the usual «В игру / Отклонить / На отбор» buttons; «В игру» would publish it as a
    stand-alone case. Hide those buttons for `status == 'campaign'` (`view.html`, `library.html`) and add a
    `.status-campaign` colour (none exists, the chip falls back to the default grey).
15. **Medium (design) — seasons end with nothing.** The monthly rating resets, but nobody gets anything for winning
    it, and last month's board disappears. Automatic end-of-season trophies for the top places (the gift system can
    do it) and a "past seasons" page would turn the rating into a reason to come back.
16. **Medium (design) — no notifications.** A friend request, an approved community request, a found-all-spots
    prize, a new case of the day: players learn about them only by stumbling on the right page. A small bell with a
    count in the header (and later Telegram/email) is the single most valuable retention feature missing.
17. **Low (design) — communities have no place to talk.** Rules, members and a rating exist, but the arguing about
    cases — the point of the game — happens elsewhere. Per-case comments with the existing report/ban tools would
    close that loop; it needs moderation capacity first.
18. **Content:** 48 cases is enough for 2–3 weeks of daily play; the two campaigns are short (3 chapters). The
    comics are procedurally drawn SVG — functional, but the game's look would change most from real illustrations
    (even one key image per case). New campaigns are pure content work now (one JSON file each).

### Code quality

19. **Medium — the XP formula lives in four places.** `career.xp_of`, `players._xp_sql`, `analytics.by_rank` and
    `social._xp` all know "verdict ×10 + right guess ×5 + daily ×15 + gifts". They agree today; a change to one is a
    bug in waiting. Keep one Python function and one SQL fragment in `career.py` and import them.
20. **Low — ratings are recomputed from scratch on every view**, including the profile page, which builds the whole
    season board to find one player's place (`social.profile`). Fine up to a few thousand accounts; past that, add
    the `ratings` summary table sketched in ARCHITECTURE.md and refresh it after each verdict. Add an index on
    `votes.first_at` at the same time.
21. **Low — one write per page view.** Activity tracking (`player_days`) does an upsert on every request. Harmless
    now; at thousands of requests a minute, sample it or batch it.
22. **Low — `style.css` is 2,300 lines in one file**, grown by appending sections. Still manageable; split by area
    (base, game, admin, social) before the next big feature.
23. **Low — Russian strings are hard-coded in templates.** Fine for a Russian game; a second language would mean
    extracting them to a catalog.

### UX

24. The pages were checked at desktop and phone widths and have no horizontal scroll; forms validate with clear
    messages; keyboard works on the quick court and the charts. The animated background is heavy for old phones —
    a "fewer effects" switch (or honouring `prefers-reduced-motion` for the canvas too) would help. There is no
    installable (PWA) version and no offline mode.

## Recommended order of work

**This week (protect what exists)**
1. `git init`, first commit, private remote. (1 hour)
2. Daily database backup on the host + a downloaded copy. (1 hour)
3. Move the browser tests into `tests/e2e/`. (2 hours)
4. Security quick wins: per-login lockout on the web form, token expiry and revoke-on-password-change, `Secure`
   on the player cookie, hide moderation buttons for campaign chapters. (half a day, with tests)
5. Delete the PHP files and the `--php` build; keep one archive zip. (1 hour)

**Next 2–4 weeks (make players come back)**
6. End-of-season trophies and a past-seasons page.
7. In-site notifications (header bell): friend requests, community approvals, hunt prizes, case of the day.
8. Registration brake (honeypot + per-IP limit) and an admin "set password" button.
9. One XP formula; uptime monitor; CI with MySQL.

**Later (grow the game)**
10. Real illustrations for cases (start with the case-of-the-day candidates and campaign chapters).
11. More campaigns; per-case comments with moderation; ratings cache; PWA; the Unity client itself.

## How this review was done

- Counted files and lines; ran `pyflakes` over `verdict/`, `tests/`, `scripts/` (clean); searched for TODO/FIXME
  (none).
- Ran the full test suite earlier the same day: 190 passed in ~40 s against a throwaway MySQL 8.
- Read the security-relevant code paths (CSRF, sessions, tokens, hunt claims, invite codes, SQL building) and
  checked the live site's cookie flags and link previews from outside.
- Checked the review-board templates for what the team can do to campaign chapters.
- Not done: load testing, a test on real phones, a check of the host's backup settings, and any review of the
  (not yet existing) Unity client.
