# VERDICT — project review

*29 October 2026. Written for the project owner and whoever works on the code next. Facts below were measured on
this date; opinions are marked as such.*

## In one paragraph

VERDICT is a complete, working product: a Russian-language judgment game with 48 cases and two story campaigns, a
career system, treasure hunts, a social layer (profiles, friends, ratings, communities), a team admin panel with
analytics, and a documented JSON API that a Unity client can use for everything the website does, including sign-in.
The code is small for what it does (7.3k lines of Python), clean (linter-clean, no TODO debt), and covered by 199
automated tests plus real-browser scenarios. It is live at https://verdict.azero.uz on cPanel. The weak spots are not
in the game logic but around it: **there was no version control until 29 October (fixed — the project is a git repository now), and there are
still no backups and no monitoring**, the registration brake is only half built, and the visual side still runs on generated comics rather than
real illustrations.

## What is here

| Area | Size | State |
|---|---|---|
| Server (Flask, `verdict/`) | 7,264 lines Python, 74 routes (30 game API, 12 admin) | solid |
| Front-end | 2,754 lines JS (11 plain scripts, no build step), 2,302 lines CSS (one file), 54 templates | solid, one big CSS file |
| Content | 48 cases, 2 campaigns × 3 chapters, catalog with ranks, events, achievements, gifts | good for an MVP; art is generated |
| Tests | 199 pytest tests, 11 browser scenarios (164 checks), screenshots at desktop and phone width | strong |
| Docs | README (deploy, every feature), docs/API.md (with a C# sample), docs/ARCHITECTURE.md | thorough |
| Database | MySQL, schema v8, 17 tables, self-upgrading; manual `schema.sql` | fine |
| Legacy | the old PHP site — removed on 29 October, kept in the first git commit | done |

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

1. **Done 29 Oct — version control.** The project is a git repository (branch `main`, first commit holds the PHP
   site too), pushed to https://github.com/Azimjon13/verdict.
2. **High — no database backups.** The live database holds every verdict, account and gift; the host's own backups
   are unknown. Turn on cPanel's backup or a daily `mysqldump` cron job, and download a copy weekly.
3. **Done 29 Oct — browser tests are in the repo.** `tests/e2e/run.py` builds and seeds its own database, serves
   the site in-process (no PHP proxy any more), runs 11 headless-Chrome scenarios and takes screenshots. The new
   phone-width scenario found the signed-in header 10 px too wide on 390 px phones; fixed.
4. **Medium — no monitoring.** Nobody is told when the site is down or erroring. A free uptime check (e.g. every
   5 minutes on `/api/v1/`) and a look at the Passenger log after each deploy are enough for now.
5. **Done 29 Oct — PHP leftovers removed** (the first commit keeps them; `build_dist.py` makes Python packages only).
6. **Done 29 Oct — CI.** A GitHub Actions job with a MySQL service runs the linter, pytest and the browser tests on
   every push to `main`.

### Security

7. **Done 29 Oct — website login lockout is per login now.** Besides the session lock, the website form uses the
   game API's per-login lock (10 failures / 15 minutes in `auth_failures`), so dropping the cookie doesn't help.
8. **Partly done 29 Oct — registration brake.** The website form has a hidden honeypot field and refuses a form
   sent less than 3 seconds after it was opened (`min_signup_seconds` in the config). Still open: the API sign-up has
   no brake, and there is no per-IP limit. Before adding one, check that the app sees the real visitor address
   behind the host's nginx (Engintron) — if every request comes from 127.0.0.1, a per-IP limit would stop all
   sign-ups. An "invite-only registration" switch in the admin panel is the fallback.
9. **Done 29 Oct — game tokens expire and end with a new password.** A token unused for 90 days is deleted on its
   next use; «Сменить пароль» and the team's reset delete all of the account's game tokens.
10. **Short term done 29 Oct — password reset by the team.** Admin → player → «Новый пароль» sets a random password,
    shows it once to the team member and ends all of the player's sessions on the site and in the game. Still open:
    a self-service reset by email (needs SMTP from the host).
11. **Done 29 Oct — the player cookie is `Secure` on HTTPS**, like the session cookie.
12. **Done 29 Oct — default admin password warning.** The admin dashboard shows a warning while the `admin` account
    still opens with `verdict-admin`.
13. **Known and accepted:** the player id (`X-Voter-Id` / cookie) is a bearer secret; hidden spots can be found
    with browser developer tools (mitigated by accounts-only gifts and finder limits); hunt placement selectors are
    trusted admin input.

### Game logic and content

14. **Done 29 Oct — campaign chapters stay out of moderation.** The review board hides «В игру / Отклонить / На
    отбор» for chapters, the server refuses those actions too, and the «В кампании» chip has its own colour.
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

19. **Done 29 Oct — one XP formula.** `career.xp_total` (Python) and `career.xp_sql` (the same as an SQL expression)
    are the only places that know "verdict ×10 + right guess ×5 + daily ×15 + gifts"; the header, the team's players
    list, ratings and the rank chart use them, and a test checks that all four agree for every player.
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
1. ~~`git init`, first commit, remote~~ done
2. Daily database backup on the host + a downloaded copy. (1 hour)
3. ~~Move the browser tests into `tests/e2e/`.~~ done
4. ~~Security quick wins: per-login lockout on the web form, token expiry and revoke-on-password-change, `Secure`
   on the player cookie, hide moderation buttons for campaign chapters.~~ done, with the honeypot, the admin
   "set password" button and the default-password warning
5. ~~Delete the PHP files and the `--php` build.~~ done

**Next 2–4 weeks (make players come back)**
6. End-of-season trophies and a past-seasons page.
7. In-site notifications (header bell): friend requests, community approvals, hunt prizes, case of the day.
8. Registration brake for the API and a per-IP limit (the honeypot and the "set password" button are done).
9. ~~One XP formula~~ done; uptime monitor; ~~CI with MySQL~~ done.

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
