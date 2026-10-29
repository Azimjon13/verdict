# VERDICT game API (`/api/v1`)

For game clients — Unity, mobile, anything that speaks HTTP and JSON. The website and the API share one database:
a verdict given in the game counts in the website's vote split and judge profile, and the other way round.

- Base URL: `https://<your-site>/api/v1`
- Responses are JSON, UTF-8. Every response has `ok` (`true`/`false`); errors carry `error` (a Russian message
  you can show to the player) and an HTTP status.
- CORS is open (`Access-Control-Allow-Origin: *`), so Unity WebGL builds work from any domain.
- No cookies and no login: the API serves players, not authors.

## Player identity

Send `X-Voter-Id: <32 lowercase hex characters>` with every request. The client makes the id once and keeps it
(Unity: `Guid.NewGuid().ToString("N")` saved in `PlayerPrefs`). The id is the player: their votes, Быстрый суд score
and judge profile follow it. Without it, `GET /cases` and `GET /cases/<id>` still work (no personal fields);
the other endpoints answer `400`.

Keep the id private: whoever knows it can play as that player.

**Accounts.** `POST /auth/register` `{login, display_name, password, device?}` or `POST /auth/login`
`{login, password, device?}` (send the device's `X-Voter-Id` too) returns `{token, voter_id, user}`. The device's
anonymous progress is merged into the account, and `voter_id` is the account's player — the same as on the website.
From then on send `Authorization: Bearer <token>`; verdicts, career and everything else go to the account whatever
`X-Voter-Id` says. Ten wrong passwords for a login in 15 minutes → `429`. `POST /auth/logout` forgets the device.

## Endpoints

| Method and path | Needs id | Returns |
|---|---|---|
| `GET /api/v1/` | — | list of endpoints, `version` |
| `GET /api/v1/catalog` | — | categories, situation types, world meters, world types, levels, judge styles |
| `GET /api/v1/cases` | optional | every case in play (summary) |
| `GET /api/v1/cases/<id>` | optional | one case with its comic frames, no spoilers |
| `GET /api/v1/quick/next[?except=<id>]` | yes | a random case the player hasn't judged, or `done: true` |
| `POST /api/v1/cases/<id>/verdict` | yes | saves the verdict, returns consequences, the split, the guess result, the profile |
| `GET /api/v1/profile` | yes | judge profile, Быстрый суд score, career (XP, rank, streak, achievements) |
| `GET /api/v1/daily` | optional | the case of the day — the same for every player |
| `GET /api/v1/world` | yes | the player's world: meters and active world events |
| `POST /api/v1/world/reset` | yes | starts the world anew (meters back to 50); verdicts and career stay |
| `GET /api/v1/hunt` | yes | treasure hunts that are on: progress, hints, and the spots hidden in the game's scenes |
| `POST /api/v1/hunt/spots/<id>/claim` | yes | the player found a spot: the gift, progress, the main prize, career |
| `GET /api/v1/gifts` | yes | the player's gifts (XP, trophies, titles, codes, messages) and current title |
| `GET /api/v1/ratings?board=season\|all\|accuracy\|streak[&community=<slug>]` | — | a rating of players with an account |
| `GET /api/v1/users/<login>` | — | a public profile, as much as its owner shows to everyone |
| `GET /api/v1/communities` | — | every community: name, description, rules, access, emblem, members |
| `GET /api/v1/communities/<slug>` | — | one community with its members and season rating |
| `POST /api/v1/auth/register`, `/auth/login`, `/auth/logout` | — / Bearer | accounts, see above |
| `GET /api/v1/me`, `POST /api/v1/me/profile` | Bearer | the account, its player id, career, communities; `{bio, visibility, in_ratings}` |
| `GET /api/v1/friends`, `POST /api/v1/friends {login}` | Bearer | friends, requests in and out; ask (or accept) |
| `POST /api/v1/friends/<login>/accept\|decline\|cancel\|remove` | Bearer | answer or end a friendship |
| `POST /api/v1/communities/<slug>/join {accept_rules, code?}`, `/leave` | Bearer | join (rules must be accepted) or leave |
| `GET /api/v1/campaigns`, `/campaigns/<key>` | optional | story campaigns, progress, the current chapter with what earlier verdicts led to |
| `POST /api/v1/campaigns/<key>/start`, `/choose {option}` | yes | start or replay; judge the current chapter |

Only cases with status «В игре» (approved) are served.

### `GET /catalog`

The same data as `content/catalog.json` without moderation fields. Useful keys:

- `categories` — `{ "moral": {name, icon, hue, desc}, … }`; `hue` (0–360) is the case's accent colour.
- `situation_types` — `private` (no witnesses), `witness`, `public`.
- `metrics` — the five world meters: `reputation`, `authority`, `stability`, `resources`, `trust` (`name`, `icon`).
- `metric_step` — `5`: one effect point moves a meter by 5 on a 0–100 scale that starts at 50.
- `worlds` — the 8 world types (`name`, `icon`); a case's `world.setting` is one of these names.
- `judge.archetypes` — the 11 judge styles (`name`, `icon`, `desc`, `strength`, `blind`); `judge.min_verdicts` = 5.
- `xp` — XP per action: `verdict` 10 (once per case), `guess` 5 (a right majority guess), `daily` 15 (the case of the
  day judged on its day).
- `ranks` — 7 ranks by XP, from «Стажёр» (0) to «Верховный судья» (520): `key`, `name`, `icon`, `xp`.
- `world_levels` and `world_events` — a meter at ≤ 20 or ≥ 80 starts an event (`trust_low`, `trust_high`), at 0 or
  100 a stronger one (`trust_zero`, `trust_peak`): 20 events with `name` and `text`.
- `achievements` — 13 achievements: `name`, `desc`, `icon`.

Icon names refer to the website's line icons (`verdict/icons.py` holds their SVG paths).

### `GET /cases`

```json
{ "ok": true, "count": 46, "cases": [
  { "id": 1, "title": "Три ампулы", "category": "survival", "type": "private",
    "setting": "Поселение после апокалипсиса", "place": "Поселение «Последний Рубеж» у разрушенной плотины",
    "era": "Постапокалипсис, 31-й год после Обвала", "teaser": "Вы — смотритель поселения. Ночью…",
    "decisions": 6, "votes": 12, "controversy": 81, "my_verdict": null } ] }
```

`controversy` is 0–100 (how evenly players split; `null` with fewer than 2 votes). `my_verdict` is the player's
option key, `"other"`, or `null`.

### `GET /cases/<id>`

```json
{ "ok": true, "case": {
  "id": 2, "title": "…", "category": "crime", "type": "witness", "author": "Команда VERDICT",
  "world": { "setting": "Средневековое поселение", "place": "…", "era": "…", "circumstances": "…" },
  "story": "…",
  "participants": [ { "name": "Тобиас", "age": "24", "role": "Пришлый батрак", "relations": "…", "description": "…" } ],
  "facts": ["…"], "unknowns": ["…"],
  "witnesses": [ { "name": "…", "claim": "…", "trust": "…", "interest": "…" } ],
  "decisions": [ { "key": "A", "text": "Виновен — казнить, как требует деревня" } ],
  "allows_own_decision": true,
  "comic": { "cast": [ … ], "panels": [ … ] },
  "my_vote": null } }
```

Consequences, world effects and hidden information are **not** sent before the verdict.
`my_vote` is `{option, guess, guess_correct}` once the player has judged the case.

**Comic frames** — the same frames the website draws, so a client can show the case as a comic:

- `comic.cast[i]` — `{name, short, age, role, relations, hue, witness, claim, trust, avatar}`. `hue` is the
  character's colour; `avatar` holds what the website's portrait generator uses (`name`, `age`, `role`, `first`).
- `comic.panels[k]` — one frame, `kind` is one of:
  - `world` — `title`, `place`, `era`, `text` (circumstances), `role` (the player's role, «смотритель поселения»);
  - `story` — `segments`: `{type: "caption", text}` or `{type: "speech", who, text, tag}` where `who` is a cast
    index or `null` (an unnamed voice; `tag` like «спросил стражник» can label it);
  - `cast` — `people`: cast indexes of the participants;
  - `evidence` — `facts`, `unknowns`;
  - `witnesses` — `people`: cast indexes whose `claim` to show as speech;
  - `decide` — the verdict screen.
  Every frame has `present`: up to four cast indexes to put on stage (speakers first).

### `POST /cases/<id>/verdict`

Body (JSON, or a form):

| Field | |
|---|---|
| `option` | a decision key (`"A"`…), or `"other"` for the player's own decision |
| `reasoning` | optional text up to 1000 characters; **required** (10+ characters) with `"other"` |
| `mode` | `"quick"` (Быстрый суд — the guess counts) or `"full"` (default) |
| `guess` | in quick mode: the key the player thinks most others chose; empty to skip |
| `duration_ms` | time from opening the case to the verdict (for statistics) |

A player has one verdict per case; sending again replaces it (an earlier quick-mode guess is kept).

```json
{ "ok": true,
  "result": {
    "choice": "A",
    "consequences": { "immediate": "…", "longterm": "…", "characters": "…", "world": "…" },
    "effects": { "authority": 1, "stability": 2, "trust": -1, "reputation": -2 },
    "decisions": [ { "key": "A", "text": "…", "why": "…", "votes": 7, "share": 0.41 } ],
    "other_votes": 1, "total_votes": 17,
    "controversy": { "value": 74, "label": "Жаркий спор", "level": "hot" },
    "ambiguity": { "conflict": "…", "for_one": "…", "for_other": "…", "divide": "…" },
    "continuation": true },
  "guess": { "key": "B", "majority": ["A"], "correct": false },
  "stats": { "score": 3, "guesses": 5, "streak": 0 },
  "profile": { … same as GET /profile → profile … },
  "career": {
    "xp": 95, "xp_gained": 15,
    "rank": { "key": "magistrate", "name": "Мировой судья", "icon": "scale", "xp": 80, "level": 3, "levels": 7,
              "progress": 0.19, "next": { "key": "judge", "name": "Судья", "xp": 160 }, "to_next": 65 },
    "rank_up": true, "streak": 3, "streak_up": true, "daily": false,
    "events": [ { "key": "authority_high", "meter": "authority", "level": "high", "tone": "up", "icon": "shield",
                  "meter_name": "Авторитет", "name": "Железная рука", "text": "…" } ],
    "achievements": [ { "key": "first", "name": "Первый приговор", "desc": "…", "icon": "gavel" } ],
    "world": { "metrics": { "authority": 80, … }, "deltas": { "authority": 5 }, "count": 7, "active": [ … ] } },
  "next_case_id": 3 }
```

- `consequences` is `null` when the author didn't describe them (or for `"other"`).
- `effects` — only meters that change, −3…+3; multiply by `metric_step` for meter points.
- `guess.majority` — the leading option(s) among **other** players before this verdict (several on a tie);
  `correct` is `null` when there was nobody to compare with or no guess. `guess` is `null` in full mode.
- `stats` — Быстрый суд: right guesses, all guesses, current streak of right guesses.
- `career` — what this verdict did: XP gained, the rank (`rank_up` when it just changed), days in a row (`streak_up`
  on the first verdict of the day), `daily` when it was the case of the day, world `events` that just started
  (each event is announced once per world), new `achievements`, and the player's world after the verdict.
  Show these as rewards on the result screen.

Errors: `400` no/invalid `X-Voter-Id`, `404` case not found or not in play, `422` unknown option or `"other"` without
reasoning.

### `GET /profile`

```json
{ "ok": true, "profile": {
  "verdicts": 12, "decided": 11, "own": 1, "left": 0,
  "archetype": { "key": "mercy", "name": "Милосердный судья", "icon": "heart-whole", "desc": "…", "strength": "…", "blind": "…" },
  "leans": { "trust": { "lean": 0.62, "more": 7, "less": 1, "relevant": 9 }, … },
  "with_majority": 6, "compared": 10, "median_ms": 41000, "top_category": "survival",
  "boldest": { "id": 14, "title": "…", "share": 0.0, "others": 5 },
  "quick": { "score": 3, "guesses": 5, "streak": 0 } } }
```

- `archetype` is `null` until `decided` (verdicts on listed options, not `"other"`) reaches 5; `left` says how many remain.
- `leans[meter].lean` is −1…+1: how much more (or less) the player's choices raise this meter than the other options
  of the same cases. Draw it as a diverging bar; `relevant` is how many cases had a choice on this meter.
- `boldest` — the case where the fewest other players agreed (no more than a third), or `null`.

### `GET /daily`

```json
{ "ok": true, "case": { … same as GET /cases/<id> … }, "judged": false, "bonus_taken": false, "bonus_xp": 15, "seconds_left": 41230 }
```

One case of the day for everyone; it changes at midnight UTC (`seconds_left`) and doesn't repeat within 30 days.
`judged` — the player has a verdict on it (any day); `bonus_taken` — they got today's +15 XP. Without `X-Voter-Id`
both are `null`.

### `GET /world`, `POST /world/reset`

```json
{ "ok": true, "world": { "metrics": { "reputation": 55, "authority": 80, "stability": 60, "resources": 40, "trust": 35 },
  "count": 7, "active": [ { "key": "authority_high", "name": "Железная рука", "tone": "up", … } ] } }
```

The world is kept on the server: every verdict on a case in play since the last reset moves the meters (start 50,
`metric_step` per effect point, 0–100). `active` — the world events in effect now (one per meter, the strongest).
A reset puts the meters back to 50 and forgets announced events; verdicts, XP, rank and achievements stay.

### `GET /profile` → `career`

```json
"career": { "xp": 95, "rank": { … as above … }, "streak": 3, "best_streak": 5, "daily_done": 2,
            "achievements": [ { "key": "first", "name": "Первый приговор", "desc": "…", "icon": "gavel", "unlocked": true } ] }
```

`streak` is the number of days in a row with at least one verdict; it stays alive until the end of the next day.
`title` is the title the player wears (a gift), or `null`. XP includes the XP of gifts.

### `GET /hunt`

The team hides spots on the website and in the game; the website draws its own, the game draws the ones whose page
is `unity:<scene>` (set in the admin panel, «Где» → «Игра (Unity)»).

```json
{ "ok": true,
  "hunts": [ { "id": 3, "title": "Неделя тайников", "intro": "…", "total": 4, "found": 1, "seconds_left": 271000,
               "ends_at": "2026-10-31 11:22:00", "prize": { "name": "Искатель тайников", "icon": "crown", "kind": "title" },
               "prize_taken": false,
               "spots": [ { "id": 7, "found": true, "hint": "…", "page": "Главная", "gift": "+50 XP за зоркость", "empty": false }, … ] } ],
  "spots": [ { "id": 9, "hunt": 3, "scene": "courtroom", "x": 81.5, "y": 12.0, "size": 32, "icon": "key",
               "visibility": "faint", "opacity": 0.14, "hint": "За молотком судьи" } ] }
```

- `hunts[].spots` — every spot of the hunt with the player's progress and the hint (for a «hunt» panel); `empty` —
  others took all its gifts.
- `spots` — what the game should draw: spots of running hunts in the game's scenes that this player hasn't found.
  `x`, `y` are % of the scene's screen; `opacity` is how visible the team wants the spot (`visibility`:
  `faint` 0.14, `subtle` 0.34, `visible` 0.9); `icon` is an icon name from the catalog, `size` in px at 1× scale.
- `catalog.hunt` lists the possible icons, sizes and visibility levels; `catalog.gift_kinds` the kinds of gifts.

### `POST /hunt/spots/<id>/claim`

```json
{ "ok": true, "found": 2, "total": 4,
  "gift": { "id": 51, "kind": "code", "kind_name": "Код", "name": "Код на футболку", "icon": "ticket", "xp": 10,
            "text": "Покажите код на стенде…", "link": "", "code": "TEE-7Q2K", "code_missing": false, "source": "spot",
            "created_at": "2026-10-28 06:22:31" },
  "prize": null,
  "career": { … as in GET /profile … } }
```

`gift` is `null` for a spot without a gift (it still counts towards the hunt). `prize` is the hunt's main prize when
this was the last spot. `code_missing` — the pool ran out (the team sees it in the admin panel). Errors: `404` no such
spot in the game (spots on the website are found on the website), `409` `code: "found"` (already found) or
`"empty"` (others took all its gifts), `410` `"gone"` (the hunt is over or the spot was removed), `401` `"account"`
(the gift is for players with an account), `403` `"blocked"` (the team barred the player from hunts).

### `GET /gifts`

```json
{ "ok": true, "title": "Искатель тайников", "gifts": [ { … as in the claim answer … } ] }
```

Newest first; gifts the team took back are not listed.

### `GET /ratings`

```json
{ "ok": true, "board": "season", "season": "ноябрь 2026", "days_left": 12, "total": 57,
  "rows": [ { "place": 1, "login": "anna", "display_name": "Анна Ветрова", "title": "Искатель тайников", "value": 140,
              "note": "", "xp": 380, "rank": { "key": "senior", "name": "Старший судья", "icon": "landmark", "level": 5 } } ] }
```

`board`: `season` (XP this calendar month, UTC, counting cases judged for the first time this month), `all` (all XP),
`accuracy` (% of right majority guesses, from 10 guesses; `note` = «9 из 10»), `streak` (days in a row now). Ties share
a `place`. `community=<slug>` limits the rating to its members. Only accounts that agreed to be rated; the first 100.

### `GET /users/<login>`

```json
{ "ok": true, "user": { "login": "anna", "display_name": "Анна Ветрова", "visible": true, "friends": 3, "bio": "…",
  "xp": 380, "title": "…", "streak": 4, "best_streak": 9, "verdicts": 31, "daily_done": 6, "season_place": 1,
  "rank": { … }, "style": { "key": "balance", "name": "Взвешенный судья", … },
  "achievements": ["first", "ten"], "trophies": [ { "kind": "badge", "name": "…", "icon": "medal" } ],
  "communities": [ { "slug": "klub-strogikh-sudey", "name": "Клуб строгих судей", "role": "owner" } ] } }
```

When the owner shows the profile only to friends or to nobody, `visible` is `false` and only `login`, `display_name`
and `friends` come back. Codes and messages from gifts are never part of a profile.

### `GET /communities`, `GET /communities/<slug>`

```json
{ "ok": true, "community": { "slug": "klub-strogikh-sudey", "name": "…", "description": "…", "rules": "…",
  "access": "request", "icon": "gavel", "hue": 260, "members": 12, "owner": { "login": "anna", "display_name": "…" },
  "created_at": "2026-10-28 09:12:00", "people": [ { "login": "anna", "display_name": "…", "role": "owner" } ] },
  "rating": [ … as in GET /ratings … ] }
```

`access`: `open` | `request` | `invite`; the invite code is never sent. `catalog.social` lists access modes, roles,
boards, emblems and colours. With a token, `POST /cases/<id>/verdict` also returns `friends` — how the player's friends
judged that case — and `GET /ratings?scope=friends` gives the friends' rating.

### `GET /campaigns/<key>`

```json
{ "ok": true, "campaign": { "key": "rubezh", "title": "Последний Рубеж", "teaser": "…", "intro": "…", "icon": "tent",
  "category": "survival", "chapters": ["Три ампулы", "Пленник из лагеря", "Весенний паводок"],
  "progress": { "started": true, "run": 1, "chapter_index": 1, "finished": false,
                "meters": { "authority": 60, "trust": 35, … }, "choices": [ { "chapter": "ampoules", "option": "F" } ],
                "ending": null },
  "chapter": { "index": 1, "bridges": [ { "from": "Три ампулы", "text": "Аран и Лея ушли за стены…" } ],
               "case": { … as GET /cases/<id>, allows_own_decision: false … } } } }
```

Show the `bridges` before the chapter, then the case. `POST /campaigns/<key>/choose {option}` answers with `result`
(`immediate`, `longterm`, `meters_delta` of this chapter) and the campaign again; when `progress.finished`, show
`progress.ending` (`tone`: `up` | `down` | `mid`). `POST /campaigns/<key>/start` starts a replay (`409` while a run is
still going).

## Unity example

```csharp
using System;
using System.Collections;
using UnityEngine;
using UnityEngine.Networking;

public class VerdictApi : MonoBehaviour
{
    const string Base = "https://your-site.example/api/v1";

    static string VoterId
    {
        get
        {
            if (!PlayerPrefs.HasKey("verdict_vid"))
                PlayerPrefs.SetString("verdict_vid", Guid.NewGuid().ToString("N"));
            return PlayerPrefs.GetString("verdict_vid");
        }
    }

    [Serializable] public class Decision { public string key; public string text; }
    [Serializable] public class Case { public int id; public string title; public string story; public Decision[] decisions; }
    [Serializable] public class NextResponse { public bool ok; public bool done; public Case @case; }
    [Serializable] class VerdictBody { public string option; public string guess; public string mode = "quick"; public int duration_ms; }

    public IEnumerator NextCase(Action<Case> onCase)
    {
        using var req = UnityWebRequest.Get(Base + "/quick/next");
        req.SetRequestHeader("X-Voter-Id", VoterId);
        yield return req.SendWebRequest();
        if (req.result != UnityWebRequest.Result.Success) { Debug.LogError(req.error); yield break; }
        var res = JsonUtility.FromJson<NextResponse>(req.downloadHandler.text);
        onCase(res.done ? null : res.@case);
    }

    public IEnumerator SendVerdict(int caseId, string option, string guess, int ms, Action<string> onResultJson)
    {
        var json = JsonUtility.ToJson(new VerdictBody { option = option, guess = guess, duration_ms = ms });
        using var req = new UnityWebRequest(Base + "/cases/" + caseId + "/verdict", "POST");
        req.uploadHandler = new UploadHandlerRaw(System.Text.Encoding.UTF8.GetBytes(json));
        req.downloadHandler = new DownloadHandlerBuffer();
        req.SetRequestHeader("Content-Type", "application/json");
        req.SetRequestHeader("X-Voter-Id", VoterId);
        yield return req.SendWebRequest();
        onResultJson(req.downloadHandler.text);   // parse with JsonUtility or Newtonsoft.Json
    }
}
```

`JsonUtility` can't read dictionaries (`effects`, `leans`, `categories`); use Newtonsoft.Json
(`com.unity.nuget.newtonsoft-json`) for those parts.

## Offline / bundled content

`content/catalog.json` and `content/cases/*.json` are the demo cases in the same shape as `GET /cases/<id>` plus the
author-side fields (consequences, effects, hidden info). A client can ship them for offline play and use the API
when online. Cases written by authors on the website exist only in the database: get them from the API
(or the team's `/api/export`).
