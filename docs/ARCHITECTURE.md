# VERDICT architecture

How the game is put together today, and where the social layer — friends, communities with their own rules,
shared results, ratings — will attach. Written for whoever builds the next part, on the website or in Unity.

## The pieces

| Layer | Where | Notes |
|---|---|---|
| Game content | `content/catalog.json`, `content/cases/*.json`, the `situations` table | The catalog (categories, meters, ranks, achievements, world events, gift kinds, hunt settings) is a file both the site and game clients read. Cases written on the site live in the database. |
| Verdicts | `votes` | One row per player and case (a second verdict replaces the first). Everything that can be computed from votes is computed from them: the split, the judge profile, XP, the world. |
| Player | `players`, `player_days` | Only what votes can't tell: when the world was restarted, day streak, cases of the day, announced events, achievements, title, the hunt ban, the account link; activity by day. |
| Account | `users`, `sessions` | Login, display name, role (`author` or `admin`). |
| Hunts and gifts | `challenges`, `spots`, `spot_finds`, `gifts`, `gift_codes`, `gift_grants` | Run by the team in `/admin`. |
| Social | `friendships`, `communities`, `community_members`; `users.bio`, `users.visibility`, `users.in_ratings` | `verdict/social.py`: profiles, friends, ratings, communities. Ratings are computed from votes. |
| Site | `verdict/` (Flask) | Pages, the team's admin panel, JSON for the site's own scripts. |
| Game API | `/api/v1` (`verdict/views/api_v1.py`) | Same database and rules as the site, see [API.md](API.md). |

## Player identity

There are two identities, on purpose:

- **The player id** (`voter`, 32 hex characters) is in the `verdict_vid` cookie on the website and in the
  `X-Voter-Id` header in game clients. It is the key to the player's verdicts, so it is a **secret**: it is never
  shown to other players, never put in a URL another player could see, never used as a public profile address.
  Anyone can start playing without signing up.
- **The account** (`users`) is the public side: a display name, and later friends, communities, ratings.
  `players.user_id` links one player to one account.

How the link behaves (`verdict/players.py`):

- **Sign up** → the browser's current player becomes the account's player (nothing is lost).
- **Sign in on another device** → that browser switches to the account's player. Whatever it did anonymously before
  is merged in: verdicts (the account's verdict wins where both judged the same case), gifts, hunt finds, activity,
  the best streak, achievements.
- **Sign out** → the browser gets a fresh anonymous player, so the next person at a shared computer doesn't play as you.
- **Two accounts on one device** → each keeps its own player.

For the game client the same link is the next step: `POST /api/v1/auth/login` (login + password → a token and the
account's player id). The client then uses that player id in `X-Voter-Id`, and progress is shared between the
website and the game. Until then a game client's id is a player of its own.

## What is computed, what is stored

The rule so far: **store events, compute views.** XP, rank, the judge style, the world meters and the vote split are
computed from `votes` (+ a few counters in `players` and the XP in `gift_grants`) on each request. That keeps them
correct when a case is withdrawn, re-edited or a vote is replaced, and it is fast enough for thousands of players.

When it stops being fast enough (ratings over tens of thousands of players are the first candidate), add **summary
tables refreshed in the background** — not new sources of truth. For example `player_stats(voter, xp, verdicts,
right_guesses, last_day, …)` updated after each verdict and rebuilt nightly from `votes`. Pages and ratings read the
summary; the votes stay the record.

## The admin panel and analytics

`/admin` reads only existing tables (`verdict/analytics.py`). Days are UTC, like the case of the day. Activity
(`player_days`) is one row per player and day with a page-view count; it is what «active», «new» and «returned»
mean. A visit counts once the browser kept its cookie, so crawlers don't inflate the numbers.

New numbers should follow the same pattern: a function in `analytics.py` that returns plain data, a chart shape
from `charts.py`, and a table view next to every chart.

## Treasure hunts

A spot is tied to an element of a page (CSS selector) and a point inside it (x, y in %), or to a scene of the game
client (`unity:<scene>`, x, y in % of the screen). A web spot is claimed with an HMAC token of the spot and the
player, so ids can't be enumerated; finding is still a client-side act, so valuable gifts should be limited to
accounts and to the first N finders, and the team can ban a cheater from hunts.

## The social layer

Built (schema 7, `verdict/social.py`): public profiles with privacy, friends (one row per direction, `requested` →
`accepted`), friends' verdicts on the result screen, ratings (season, all time, accuracy, streak; everyone / friends /
community), communities with rules, access modes (open / request / invite link), founder and moderators. The monthly
season counts a case by `votes.first_at` — when it was judged first — so re-voting can't farm a season.

Also built (schema 8): sign-in from the game client (`api_tokens`, only SHA-256 of a token is stored;
`auth_failures` slows down guessing) with friends, communities and the friends' rating in `/api/v1`; reports to the
team (`reports`) with a ban that keeps a player out of ratings, hunts and social actions; story campaigns
(`campaign_runs`, content in `content/campaigns/`).

Still to build: shared snapshots with images (`shares` below), season results kept per month (`ratings` below) once
boards need caching, notifications (a friend request, an approved join request).
Everything hangs off **accounts** (`users.id`), never off player ids. The original plan, for reference:

```sql
-- Friends: one row per direction keeps queries simple («my friends» = WHERE user_id = me).
CREATE TABLE friendships (
    user_id    INT UNSIGNED NOT NULL,
    friend_id  INT UNSIGNED NOT NULL,
    status     VARCHAR(10)  NOT NULL,          -- requested | accepted | blocked
    created_at DATETIME     NOT NULL,
    PRIMARY KEY (user_id, friend_id)
);

-- Communities («суды»): a group with its own rules and ratings.
CREATE TABLE communities (
    id          INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    slug        VARCHAR(60)  NOT NULL UNIQUE,
    name        VARCHAR(120) NOT NULL,
    description TEXT         NOT NULL,
    rules       TEXT         NOT NULL,          -- the group's own rules, shown on joining
    visibility  VARCHAR(10)  NOT NULL,          -- open | request | invite
    owner_id    INT UNSIGNED NOT NULL,
    created_at  DATETIME     NOT NULL
);
CREATE TABLE community_members (
    community_id INT UNSIGNED NOT NULL,
    user_id      INT UNSIGNED NOT NULL,
    role         VARCHAR(10)  NOT NULL,         -- owner | moderator | member
    status       VARCHAR(10)  NOT NULL,         -- active | requested | invited | banned
    joined_at    DATETIME     NOT NULL,
    PRIMARY KEY (community_id, user_id)
);

-- Shared results: a snapshot a player chooses to publish (a verdict, a judge style, a hunt prize, a rank).
CREATE TABLE shares (
    id         INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id    INT UNSIGNED NOT NULL,
    kind       VARCHAR(20)  NOT NULL,           -- verdict | style | rank | achievement | gift
    payload    TEXT         NOT NULL,           -- JSON snapshot, so later edits don't change what was shared
    audience   VARCHAR(10)  NOT NULL,           -- friends | community | public
    community_id INT UNSIGNED NULL,
    created_at DATETIME     NOT NULL
);

-- Ratings: computed, stored per season so a board doesn't move under the reader.
CREATE TABLE ratings (
    board      VARCHAR(40)  NOT NULL,           -- global | friends:<user> | community:<id>
    season     VARCHAR(10)  NOT NULL,           -- e.g. 2026-11
    user_id    INT UNSIGNED NOT NULL,
    score      INT          NOT NULL,
    place      INT UNSIGNED NOT NULL,
    updated_at DATETIME     NOT NULL,
    PRIMARY KEY (board, season, user_id)
);
```

How the existing parts feed it:

- **Ratings** can rank by XP (already computable per player), right majority guesses, days in a row, cases of the
  day, hunt finds, or a community's own formula. Seasons (a month) keep boards fresh for newcomers. Only players
  with an account appear on a board.
- **Community rules** are the group's text plus, later, settings the game enforces: which categories count, a
  private case of the day for the group, whether members see each other's verdicts.
- **Sharing** already exists for judge styles (`/judge?a=<style>`); `shares` generalises it with an audience.
- **Comparing with friends** reuses the vote split: «how my friends judged this case» is the same query as the
  global split, filtered to friends' player ids.
- **Moderation**: the admin panel gets «Сообщества» and «Жалобы» sections; the `blocked` flag on players becomes a
  general ban list.

API endpoints to add alongside (all need an account token): `/api/v1/auth/login`, `/friends`, `/friends/requests`,
`/communities`, `/communities/<slug>`, `/communities/<slug>/members`, `/ratings/<board>`, `/shares`.

## Conventions

- Schema changes are versioned steps in `verdict/db.py` (`SCHEMA_VERSION`), mirrored in `database/schema.sql`.
  Schema steps 1–4 date from the original PHP site; a database created by it upgrades in place.
- Game data the client needs goes in `content/catalog.json` and `/api/v1/catalog`.
- Times are stored in UTC.
- Every page and API change comes with tests (`tests/`), and pages are checked in a real browser before release.
