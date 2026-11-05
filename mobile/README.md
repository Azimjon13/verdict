# VERDICT — mobile app

The game on Android (and iOS, built on a Mac) — written in Flutter on top of the site's game API (`/api/v1`,
`docs/API.md`). The same cases, verdicts, career and account as on the website: what a player does in the app counts
on the site and the other way round.

## What's in it

- **Играть** — the rank and its progress, the case of the day with its countdown and bonus, Быстрый суд, and the
  story campaigns.
- **A case** — swipeable frames like «Дело в кадрах» on the site (the world and the player's role, the story with
  speech bubbles, the people, what is known and unknown, the witnesses), then the verdict — the chosen option gets a
  «ВЕРДИКТ» stamp; in Быстрый суд also the guess of the majority. In the archive: one's own decision is possible too.
- **Кампании** — chapters played in order; before each new chapter, «Что было дальше» tells what the earlier verdicts
  led to; after it, the consequences and how the campaign's own world moved; at the end, one of the endings (and
  «Пройти заново»).
- **The result** — the guess, XP counting up, rank progress, rank-ups, streak, achievements and world events (with
  confetti for a rank-up, an achievement or a right guess), the consequences, how all judges split, why there is no
  right answer; next case, the discussion.
- **Архив** — every case in play by category, «только нерассуженные».
- **Судья** — the judge style, where the player's verdicts push the world, the world's meters and events (and
  «начать заново»), gifts and trophies with codes, the title to wear, achievements.
- **Рейтинг** — season, all time, instinct, streak — everyone or only friends — and past seasons with their podium
  and what the current one will give. Tapping a judge opens their profile.
- **A judge's profile** — rank, XP, verdicts, streak, season place, style, trophies, communities (as much as the owner
  shows), and the friendship button: add, accept, withdraw, remove.
- **Войти / Аккаунт** — sign in or sign up (the phone's anonymous progress joins the account, as on the site),
  friends (requests to accept or decline, friends with their rank and streak, pending requests, finding a judge by
  login), notifications (the tab shows the unread count), signing out (the phone gets a fresh anonymous player), and
  the server address (default `https://verdict.azero.uz`).
- **Обсуждение** — comments under a case after one's own verdict; backing them and writing need an account.

The player id (32 hex) is made once and kept on the phone (`shared_preferences`); the account's token likewise.

## Build

Flutter 3.47+ (`flutter doctor`). From this folder:

```
flutter pub get
flutter test                      the app against saved real API answers (test/fixtures)
flutter build apk --release       → build/app/outputs/flutter-apk/app-release.apk
flutter run                       on a connected phone or an emulator
```

Another server: `--dart-define=VERDICT_API=https://example.com` (the address can also be changed in the app:
Аккаунт → Сервер). Debug builds may use plain `http` (an emulator reaches the PC as `http://10.0.2.2:<port>`); release
builds need `https`.

**Publishing.** The release APK is signed with the debug key — fine for installing by hand («установка из
неизвестных источников»), not for Google Play. For Play: create an upload key (`keytool -genkey …`), add a
`signingConfig` in `android/app/build.gradle.kts` and build an app bundle (`flutter build appbundle`). The app id is
`uz.azero.verdict`. iOS needs a Mac with Xcode: `flutter build ipa`, after setting the bundle id, the team and the app
icons there.

Icons are drawn from the site's logo by `scripts/make_icons.py` (in the project root; it needs Chrome). The fonts
(Manrope, Unbounded) are bundled under the SIL Open Font License (`assets/fonts/OFL-*.txt`, also on the app's
licenses page).

## Code

```
lib/main.dart          start-up (dictionaries from /catalog), the tabs, SessionScope
lib/api.dart           /api/v1 client: X-Voter-Id, Bearer token, Russian error messages
lib/session.dart       player id, sign-in, unread count, server address
lib/theme.dart         the site's colours and fonts; lib/icons.dart — the site's icon names → Material icons
lib/widgets.dart       panels, buttons, letters, bars, avatars, loading and error states
lib/fx.dart            the verdict stamp and the confetti (still when the phone asks to reduce motion)
lib/screens/           home, case_screen (frames + verdict), result_screen, campaigns, archive, judge, ratings (and
                       seasons), profile, account (and friends), talk
tool/showcase.dart     opens any screen with real data from a server, for screenshots and design review
test/app_test.dart     widget tests against test/fixtures (real answers saved from the site)
```
