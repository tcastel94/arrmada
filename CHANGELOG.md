# Changelog

All notable changes to ArrMada will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Kodi add-on 1.13.0 — Apps, live TV and NAS videos inside ArrMada (ADR-004, phase 4.3)

#### Added
- **Apps & sources screen** (*Apps* in the main menu, `?action=apps`): tabs *Video* (Kodi video add-ons: YouTube, IPTV add-ons…), *Live TV* (channels of Kodi's PVR with the current programme, its end time, a progress bar and the next programme), *Music* (audio add-ons and music sources), *Folders* (video sources declared in Kodi: NAS shares, home videos), *Favourites* (Kodi favourites, ArrMada's own shortcuts hidden) and *Android apps* (Shield only). Tabs without content on the device are hidden (no live TV add-on, not Android)
- Add-ons and folders are **browsed inside ArrMada** (`Files.GetDirectory`): list with a preview (thumbnail, plot, duration, "Resume at…", "Watched"), breadcrumb, Back goes up one level. Videos play through Kodi's player (`Player.Open`, resume offered for started videos); channels through `Player.Open {channelid}`. Long press: *Open in Kodi* (always available, for add-ons that need Kodi's own interface), *Add-on settings*, *Kodi TV guide*
- **"Your apps" row** on the media home (2nd row): Kodi favourites first, then a *Live TV* tile, then video add-ons; OK on an add-on opens it directly, Back returns home. Favourites are read from `favourites.xml` (Kodi's API reports add-on favourites — `RunAddon` — as "unknown"); a favourite pointing to an add-on or a folder opens inside ArrMada, others run exactly as in Kodi
- **Search results in the ArrMada grid** instead of a SiLVO list: tabs *All*, *Movies*, *Series*, *New search*; a followed title opens its detail screen (or the series screen), a missing one the request window
- `lib/apps_data.py` (pure, tested) and `lib/kodi_sources.py` (JSON-RPC); the media home layout generator gets a square tile row and a 10th menu button
- Tests: add-ons (sorting, ArrMada hidden, scripts run), sources, Android apps (package names checked), directory entries (order kept, resume, `-1` season/episode ignored), channels (end time in local time, next programme), favourites (quoted commas, escapes, RunAddon), home row (favourites first, no duplicates), long press, search results. Bench: fake video add-on (folders, next page, playable items resolved by the add-on), IPTV Simple with 3 local channels and an XMLTV guide around the run time, a home videos source and Kodi favourites; home row, add-on browsing, playback from the add-on, live TV list and channel playback, folders, favourites, search grid, opening an add-on from the home row

#### Fixed (found on the bench)
- A list emptied while loading loses Kodi's focus and `getFocusId()` then raises: the apps screen restores the focus itself

### Kodi add-on 1.12.0 — Kodi starts on ArrMada (ADR-004, phase 4.2)

#### Added
- **Media home** (the "shell" that replaces Kodi's home screen): main menu (Home, Movies, Series, Discover, Search, Downloads, Living room, **Dashboard** — the former Home — and Settings), a header describing the selected item (fanart, title or logo, state such as "Resume at 12:34" / "Next episode", plot) and rows: *Resume* (Kodi library of the TV), *Recently added*, *For you*, *Coming soon*. Empty rows disappear; rows show instantly from the service cache and refresh after playback
- **Starts on ArrMada**: whenever Kodi's own home screen is shown (startup, back from an add-on), the service opens the ArrMada home. Never during a video, on top of a dialog, or in safe mode; stops after 3 openings in a minute; setting *Interface → Start on ArrMada and come back to it* (on by default)
- **Back** on the ArrMada home asks "Quit?": stay, switch to the Kodi interface (no automatic return until Kodi restarts), Kodi settings, quit Kodi — never locked in
- **Movies / Series / Discover grid** replacing SiLVO's views: tabs (A to Z, recently added, by genre, 4K, not yet available; for you, trending movies, trending series), 7 posters per row with *Watched* badge and resume bar, unavailable titles dimmed, the next 100-title page loaded two rows before the end. OK opens the detail screen, the **series screen** (series present on the TV) or the request window; long press: play, detail, better release, mark as watched / unwatched
- Plugin root: *Home* now opens the media home, *Dashboard* the former home; shortcut "ArrMada · Dashboard" added (`?action=shell` / `?action=home`)
- `kodi-addon/tools/make_shell_xml.py` generates the media home layout (4 rows and 9 menu buttons from one template); a test checks the committed XML is up to date
- Tests: menu / rows order, header (state shown once), page preloading, grid counter, automatic return rules (setting, safe mode, "Kodi interface", Kodi home only, no dialog, no video, retry delay, loop protection). Bench: Kodi starts on ArrMada, media home rows and header, row navigation, Movies grid (138 titles, page 2 preloaded, tabs), Series grid → series screen, "Quit?" menu, automatic return

#### Fixed (found on the bench)
- Rows inside the media home's vertical list did not receive Up / Down (Kodi does not pass them to nested lists): navigation is declared row by row, and Kodi skips an empty (hidden) row by following its navigation
- "Mark as watched" offered both "watched" and "unwatched" after a change in the same list
- Grid: Kodi re-binds the whole list when items are appended from Python (`ControlList.addItems` → `GUI_MSG_LABEL_BIND`), which put the selection back at the top when the next page arrived; the selection is restored

### Kodi add-on 1.11.0 — Series and resume without SiLVO (ADR-004, phase 4.1)

ADR-004: in the long run, ArrMada replaces Kodi's interface; Kodi stays hidden underneath as the player (passthrough, HDR, subtitles unchanged) and the local library (watched, resume points, third-party add-ons).

#### Added
- **Series screen** (replaces SiLVO's Videos window for series): seasons ("3 / 9 watched"), then episodes with thumbnail, *Watched* badge, resume progress bar, air date, runtime and plot. The season and episode to watch next are pre-selected; the top button says "Resume S01E04" / "Play S01E05" (or "Watch again from the start"). Long press: *Play from the start*, *Mark as watched / unwatched*, *Mark the whole season as watched*. Opened by *Play* / *Open the series* everywhere (home, detail, lists, Resume), and from a season of the detail screen directly on that season; `plugin://script.arrmada/?action=series&tvshowid=N`
- **Episodes chain**: the following episodes (up to 30, across seasons, specials excluded) play one after another
- **Movies**: *Play* asks "Resume at 42:10 / From the start" (Kodi does not ask when an app starts a video); the detail button shows "Resume at 42:10" or "Watch again"; long press: *Play from the start*, *Mark as watched / unwatched*
- **Resume** row (app root and SiLVO widget `?action=widget_continue`): movies and episodes in progress plus the **next episode** of every series being watched, most recent first, one entry per series. OK plays through ArrMada (resume, chaining, amp preset); long press: *Play from the start*, *Mark as watched*, *Open the series*
- Movies / Series / Recently added lists show the skin's **watched tick** and **resume bar** (Kodi library of this device, matched by TMDB / TVDB id), with *Mark as watched / unwatched* in the long press menu
- Tests: next episode (started first, never back before the last watched, specials ignored), chaining, seasons, Resume row (merge, order, one entry per series), list annotation. Bench: a real Kodi library (series + movie with `.nfo` files, local scraper) scanned at each run; detail "Resume at 0:40", series screen, season 2, long press menu, resume prompt, playback resumed at 0:30 with the following episodes queued, Resume row

#### Fixed (found on the bench, real Kodi)
- Starting a **playlist** through Kodi's API ignores the resume point: the episode is started alone (resume honoured), then the following ones are appended to Kodi's video playlist once playback has started
- **Kodi could crash at the end of pairing** (2 bench runs out of 3, present since 1.6): the background thread closing the pairing screen was still alive when the script ended ("waiting on thread", then a segmentation fault). Every add-on script now waits for its background threads before returning to Kodi (`ui_common.join_threads`, with a shutdown signal for threads waiting on playback)
- Plugin lists: Kodi replaced every label with the item's title (default `%T` label mask of `addSortMethod`, read in Kodi's source): "Severance · S01E04" showed as the episode title. Lists now keep their own labels (`%L`)

### Living-room ambient screen (tablet under the TV) + Kodi add-on 1.10.0

#### Added
- **Ambient screen** `/ecran` in the web app, for a tablet placed under the TV (Pixel Tablet with Fully Kiosk Browser): clock and date, and during playback the title, episode, poster, **start time**, **expected end time**, time left and a progress bar (paused: "end, if resumed"); the room's Yamaha amp (volume, input, sound program); active downloads; tonight's and tomorrow's releases. Full-screen page outside the app shell, readable from the couch, black background
- **Séance mode**: during playback the page dims itself and, in Fully Kiosk (PLUS licence, *Enable JavaScript Interface*), lowers the backlight through `fully.setScreenBrightness` (`/ecran?seance=6&repos=40`, 0-255, clamped). Touching the screen brings it back for 20 s. The brightness is never touched before the first answer (reloading during a film does not flash). Small periodic pixel shift; the position moves every second between two server answers, with the tablet/server clock offset corrected
- **"Screen" devices**: the tablet pairs like a TV (code + QR code, *Settings → Kodi → Devices*), with `kind: "screen"`. Its token allows **only** `GET /api/ambient` and `GET /api/devices/me` (no queue, no amp control, no search). LAN only. The devices panel shows a *Ambient screen* badge; a revoked token sends the tablet back to pairing. An admin logged in on a PC can preview the screen without pairing
- Backend: `GET /api/ambient` (now playing per room, amp, downloads, upcoming; each block independent and cached 5 s – 5 min); in-memory now-playing per room fed by the add-on's scrobbles (stale after 100 s, 3 h when paused; pause inferred for older add-ons whose position stops moving); `devices.kind` column added automatically to existing databases at startup (`ALTER TABLE`, idempotent); `X-Device-Token` allowed by CORS (browser device)
- Add-on 1.10.0: scrobbles read **the player** (`VideoPlayer.*`, `Player.Art`) instead of the selected list item (an auto-played next episode used to be reported as the previous one), send episode title, year, poster and fanart (web addresses only, `image://` unwrapped), a `paused` flag in the 30-second progress report, and the last known position on stop (watched from 90 % when stopping during the credits). `play` is sent on `onAVStarted`, when title and duration are known
- Tests: now-playing sessions (pause inference, new episode, stale), ambient endpoint, screen scope, column migration, artwork lookup; add-on payloads and image filtering. Bench: the test video is played as an identified episode and the mock server checks what the TV sent (play → pause → stop with series, episode and poster)

#### Changed
- **Ambient screen readable from the couch** (3-4 m from an 11-inch tablet): during playback the poster takes almost the whole height, the expected end time is huge (26 % of the screen height), start time and time left are large, with the title, clock and amp volume; downloads and releases wait for the end of the film. At rest: a large clock, releases, downloads and the amp in large panels. Sizes follow the screen through a CSS unit (`--u`, a fraction of the height or width, portrait and landscape), so the page fills the tablet, a PC (admin preview) or a phone without scrolling. With Fully Kiosk the backlight does the dimming and the text stays sharp (opacity 90 % instead of 60 %)

#### Documentation
- Zip install (`kodi-addon/README.md`, method 2): copy the zip under a **versioned name** (`script.arrmada-<version>.zip`). Kodi keeps the file list of every zip it has opened until it quits (`DIR_CACHE_ALWAYS`): a zip overwritten under the same name installs the new `addon.xml` with the old file list, so files added since are missing (1.10.0: `lib/playback_data.py`, the service fails at startup). Reproduced in a real Kodi; recovery steps documented

#### Fixed
- TV notifications fell back to the library poster through a table that is never filled, and the import error was swallowed: bubbles from webhooks without images had no poster since 1.8.0. The lookup now uses the cached library (TMDB id for movies, TVDB id for series, then the title)

### Kodi add-on 1.9.0 — Movies and Series: the whole library on the TV

#### Added
- **Movies** and **Series** at the root of the Kodi app: the whole Radarr / Sonarr library, not only the recently added row. Views: *All, A to Z*, *Recently added*, *By genre* (translated, with title counts), *In 4K* (movies), *Not yet available*. OK opens the ArrMada detail; long press: Play / Detail / Better release. Titles without a file say "not yet available" and offer no *Play*
- Server-side sort and filters over the whole library, 100 titles per page with a *Next page* entry (thousands of titles would make the Shield crawl); Kodi's own sorts (title, year, rating) stay available for the page shown
- SiLVO widgets: *Movies in 4K*, *Recently added movies*, *Recently added series*
- Backend: `/api/media?min_resolution=2160`; `/api/media/facets?type=movie|series` with `genre_counts`
- Tests: views, queries, pages, genres, unavailable titles; library sort. Bench: movies root, A to Z, page 2, genres, series (45 screenshots)

#### Fixed
- Library sort: `sort=size` was silently ignored (sorted by title); a title without a year made `sort=year` fail (int compared with ""); A to Z was case- and accent-sensitive ("Élémentaire" after "Zodiac"). Missing values now always go last
- Every app list now keeps the order prepared by the server or the app (Kodi used to pick its own default sort, by date for instance)

### Kodi app — phase 3 "finishing touches": QR codes, richer notifications, shortcuts, no admin password on the TV (add-on 1.8.0, ADR-003)

#### Added
- **QR codes to the web app**: `GET /api/qr?path=…` (a web app page) or `?youtube=…` (a trailer) returns `{url, png}`; only web app paths and YouTube ids are accepted (no `//`, no scheme, 300 chars max), allowed in the TV scope. Kodi shows them in a new dialog (*Open on the TV* button on Android). Used by: media detail → **Phone** button, trailer without the YouTube add-on, *NAS maintenance* in the legacy menu, a root entry *On your phone*
- **Richer TV notifications**: the backend's webhook events now carry the poster (`images` of Radarr 5 / Sonarr 4, or the library), episode title, upgrade flag, size and year; `ManualInteractionRequired` becomes `import_blocked`. The TV shows the poster as icon, says *Upgrade on the NAS*, *New title followed* (added to Radarr/Sonarr, no library scan) or *Import blocked*, merges more than 2 at once into one bubble, plays no sound, and **shows nothing during a film or an episode**: a "During your show" summary appears when playback stops (setting *Notifications during playback*)
- **Shortcuts**: menu entry that adds *ArrMada · Home / Downloads / Living room / Search* to Kodi favourites (JSON-RPC, never duplicated: Kodi's add is a toggle), to pin in SiLVO's main menu. A favourite launches a screen as playback (`PlayMedia`); the add-on now answers "nothing to play" and reopens the screen, without an error
- Tests: QR target filtering, endpoint and TV scope; enriched webhook events (poster, upgrade, size, episode, missing episode numbers); notification texts and grouping; shortcuts; migration decisions. Bench: QR dialog, poster bubble, favourites, favourite launch, no bubble during playback then summary (40 screenshots)

#### Changed
- **The TV never sends the admin password any more** (`X-Api-Key`): only its device token. A TV that still has the password in its settings **pairs itself** at startup (asks for a code, confirms it with the password, gets its token) and then **erases the password**; retried every 5 minutes while the server is unreachable. The password field is hidden from the add-on settings. The backend still accepts `X-Api-Key` for scripts and automations (owner's decision). Checked against the real backend

#### Fixed
- A Sonarr webhook with an episode lacking season/episode numbers answered HTTP 500 (`'?':02d`)

### Kodi add-on 1.7.2 — Shield: install by zip, clearer "not authorized" screen

#### Fixed
- The Home screen and the lists said "ArrMada is unreachable" for every error, including a server that answers but refuses the TV (401/403: not paired, revoked token, no password). They now say "This TV is not authorized" and point to *Pair this TV*; a real network failure keeps the "unreachable" screen with the address to check

#### Changed
- On the NVIDIA Shield (Kodi 21, Android), installing the add-on **from the ArrMada repository** still closes Kodi with 1.7.1, while the very same zip installed from a network share works (reported by the owner). Cause still under investigation: the server's repository responses were checked (headers, `HEAD` without body, standard zip). Until then, the web app panel and the README say to install by zip on the Shield and to remove the ArrMada repository from it

### Kodi add-on 1.7.1 — fix: Kodi closing on install (NVIDIA Shield)

#### Fixed
- Installing add-on 1.7.0 on a Shield (Kodi 21, Android) closed Kodi. Not reproduced on the Kodi 20.5 bench, including the 1.4.2 → 1.7.0 update against the real backend. The service goes back to the 1.4.2 model that worked on the Shield: **one loop, no background thread**. Each one-second tick does at most one events poll and one feed download, with short network timeouts (3–4 s)
- Settings changed while Kodi runs (safe mode, check interval, notifications) were not seen by the service until Kodi restarted: Kodi only reloads the *first* in-memory copy of an add-on's settings, and each module holds its own. The service now listens to `Monitor.onSettingsChanged()` and reloads its copy (checked on a real Kodi: unticking safe mode applies in under a second)
- Backend: real Radarr/Sonarr "Download" webhooks send the file quality as a plain string (`"quality": "Remux-2160p"`); the handler expected the REST API's nested object and answered HTTP 500, so imports were neither notified nor published to clients. Both shapes are now accepted (tested)

#### Changed
- "Real time" on the TV is now a poll of `/api/events/recent` every 5 s instead of a long-lived SSE connection (an import shows on screen within 5 s). The backend adds `boot_id` and `last_id` to that response so the TV detects a server restart (event ids start over at 1) and loses nothing; after a long outage, at most the 3 most recent events raise a notification
- Widget reload (`arrmada.reload`) is announced once per refresh batch, not once per feed
- The add-on's library scan after an import is skipped when a scan is already running

#### Added
- **Startup circuit breaker** (like systemd's `StartLimitBurst`): if Kodi closes twice in a row within 2 minutes of startup, the service starts in **safe mode** (1.4.2 behaviour: scrobble and legacy download alerts only) and says so on screen. Add-on settings → Advanced → "Safe mode" to turn it off, applied without restarting Kodi
- Docs: recovering a Shield where Kodi closes at startup (`adb force-stop`, fetch `kodi.old.log`, rename the add-on folder)
- Tests: events cursor (first poll, new events, server restart, malformed payloads), one-feed-per-tick scheduling, circuit breaker, real-shape *arr webhooks, `/api/events/recent` cursor fields

#### Removed
- The add-on's SSE client (`open_stream`, SSE parser) and the mock backend's SSE stream; the backend's `/api/events/stream` stays for the web app

### Kodi app — end of phase 1: background service, native navigation, SiLVO widgets (ADR-003)

#### Added
- Kodi add-on 1.7.0: the **service** keeps a local cache of six feeds (recently added, upcoming 7 days, downloads, for you, monitored missing, notifications), each on its own schedule, with a spaced retry when the server is down. Lists and widgets read the cache: instant display, even offline
- **Real time**: the service listens to `/api/events/stream` (SSE). An import or a grab shows an on-screen notification within a second, refreshes the affected feeds and triggers a Kodi library scan (at most once a minute). On disconnection it reconnects at once and catches up through `/api/events/recent`. The old polling of `/api/kodi/addon-status` only runs while the stream is down
- **Native navigation** mirroring the web app: Home, Discover (For you, trending movies, trending series), Missing, Search, Calendar, Downloads, Notifications (unread count; OK shows the text and marks it read), Living room, Pairing, Widgets, Tools (legacy menu). Items carry a full video info tag (Kodi 20+ `InfoTagVideo`, `setInfo` fallback on Kodi 19), poster, fanart and ClearLogo. Long-press menu: *Play*, *Detail*, *Better release*
- **Widgets for SiLVO's home screen**: `plugin://script.arrmada/?action=widget&feed=recent|upcoming|downloads|foryou|missing`; the `arrmada.reload` home property changes whenever a feed changes, for live-reloading widget paths
- Backend: paired TVs may now read `/api/events/stream|recent`, `/api/recommendations` and mark notifications as read
- Tests: feed cache, SSE parser, event-to-feed mapping, conversion of every feed into list entries (French dates, local time, badges, actions)
- Bench: calendar, missing, recommendations, notifications and a live SSE stream in the mock backend; the harness browses the new lists and publishes an import in real time (35 screenshots)

#### Changed
- The legacy global context-menu items ("ArrMada: …") are hidden inside the add-on's own lists, which have their own long-press menu
- The service stops cleanly with Kodi: the real-time thread is unblocked (socket shutdown) and joined, instead of being killed after 5 s

### Kodi app — phase 1: pairing, room and amplifier per TV, update repository (ADR-003)

#### Added
- **TV pairing** (like "connect your TV" on Netflix, RFC 8628): Kodi shows a 6-character code and a QR code; the web app validates it and picks the TV's name, room and Yamaha amplifier. The TV then gets its own token (only its SHA-256 hash is stored)
  - backend: `devices` table, `/api/devices/pair/start|poll|confirm`, `/api/devices/pair/qr/{code}.png`, list, edit, revoke, `/api/devices/me`;
  - auth: `X-Device-Token` header with a server-side "TV" scope (allow-list: playback, search, add, subtitles, read-only queue plus pause/resume, amplifier). No deletion, cleanup or configuration from a TV, even through the legacy menus;
  - pairing and device tokens are accepted from the local network only (RFC 1918, loopback, IPv6 local), including every `X-Forwarded-For` hop;
  - web app: Settings → Kodi → "Devices (TV)" panel (pair, edit room and amplifier, revoke, last seen); the QR code opens it with the code pre-filled;
  - Kodi add-on 1.6.0: "Pair this device" screen (code in 6 tiles, QR code, countdown, success screen), "Device" line in the Diagnostic panel. The legacy `X-Api-Key` keeps working during the transition
- **Room and amplifier per TV**: the Living room screen and the preset applied by *Play* always target the amplifier of the TV's room, enforced by the server
- **Kodi repository served by ArrMada** (`/kodi/repo/`: browsable listing, `addons.xml`, md5, zips, `repository.arrmada.zip` with this server's address written in). Built on the fly from the mounted `kodi-addon/` folder: a `git pull` is enough to offer a new version to every TV. Install and automatic update checked on a real Kodi 20.5
- Web app: Settings → Kodi → "Kodi app updates" panel with the exact repository address and the steps
- `PUBLIC_WEB_URL` (QR code target, optional) and `KODI_ADDON_DIR` settings; `docker-compose.yml` mounts `./kodi-addon` read-only into the backend
- Docs: the remote's volume buttons cannot reach a Kodi add-on on Android; set the Shield's volume control to HDMI-CEC (or IR) so each Shield drives its own room's amplifier

#### Fixed
- Kodi skin pitfalls caught by new tests: a purely numeric `<label>` is read as a localized string id; an image URL needs a `.png` path and `HEAD` support or Kodi shows nothing

### Kodi app — phase 2 "wow screens" (ADR-003)

#### Added
- Kodi add-on 1.5.0: three new full-screen windows, built like the Home window (on-device rendering, network calls in background threads, no UI freeze)
- **Media detail** (OK on a poster or on a download): Ken Burns fanart, ClearLogo, year · runtime · rating · genres, TMDB / IMDb / Rotten Tomatoes scores, 4K / HDR / Atmos / Remux badges, scrolling synopsis, director and composer, poster with status, file details and subtitles
  - movies: cast rail with round photos (initials when there is no photo);
  - series: season cards with per-season progress, and the latest downloaded episode as the reference file;
  - actions: **Play** (device's Kodi library, with resume, plus the Yamaha preset of the device's room), **Trailer** (YouTube add-on, movies), **Better release** (Radarr/Sonarr search), **Subtitles** (Bazarr search, movies)
- **Downloads** (`action=queue`): the whole Radarr/Sonarr queue with progress bars, percentage, time left, estimated speed (from the remaining bytes between two refreshes), size and colour-coded status (downloading, paused, queued, import pending, error with its reason). Refreshed every 5 s in place, without flicker or losing the selection. Buttons *Pause all* / *Resume all*
- **Living room** (`action=salon`, also listed in the add-on menu): now playing on this device (art, title, resolution, audio, elapsed / total, end time, paused pill; −30 s, play/pause, +30 s, stop), read from Kodi itself so it works offline. Yamaha amplifier state (power, volume in % and dB, input, sound program) with volume, mute and power buttons, refreshed every 3 s and right after each command. *Living room* / *Cinema room* presets, with the device's own room marked
- Home header: *Downloads* and *Living room* buttons; quick actions gain *Detail*
- Pre-rendered progress bar textures (`progress/bar-000…100.png`, 2 % steps): Kodi's progress control cannot read list item properties
- Bench: detail, downloads, living-room and playback steps (25 screenshots), mock backend for media detail, queue and amplifier; silent demo video (Xvfb has no audio output, and Kodi's busy dialog would block other windows for 10 s)
- Tests: phase 2 data logic, and XML ↔ Python checks for all four windows, including "only the focused control is solid accent"

#### Changed
- Only the focused control is solid blue. The main button of a screen (*Play*, *Vol +*) is a blue tint when the focus is elsewhere, and a selected card only looks active while its list has the focus
- `<defaultcontrol always="false">` on every window: focus is kept when coming back from a sub-window

#### Fixed
- A paused SABnzbd showed "Downloading": Radarr/Sonarr keep `trackedDownloadState = downloading` and report the pause in `status`. Status now wins while downloading, the import step wins once downloaded
- Home: when only the "recently added" call failed, the poster rail was emptied and the cache overwritten. Both calls must now succeed before the display and the cache are replaced

#### Known limitations
- *Pause all* / *Resume all* act on the whole SABnzbd queue: the backend endpoints are global, not per item. Radarr/Sonarr show the pause after about a minute
- No deletion from the TV (ADR-003 decision 1), except in the legacy "[TELECHARG.]" menu, to be removed later

### Kodi app — phase 0 prototype (ADR-003)

#### Added
- Kodi add-on 1.4.2: full-screen **Home** window (WindowXML, Aeon Nox SiLVO fonts). It shows a fleet summary, four KPI tiles, live downloads (refreshed every 20 s), a "recently added" poster rail with focus zoom and glow, fanart backdrop, ClearLogo, tech badges and service status
- The window opens instantly from an on-device cache, then refreshes in a background thread (no network call in the UI thread). It has an offline mode, and a **Diagnostic** panel (font and glyph bench, system info, measured open / network / render times)
- Motion: staggered opening cascade, KPI count-up and animated progress bars (Python tweens), Ken Burns fanart, focused poster lift with breathing glow and badge pop, direction-aware info slide, poster rail slide-in when data arrives
- **Intro** (≈ 2.4 s, once per Kodi session, any key skips it): the two legs of the "A" join, the play button pops, two shockwaves, a light sweep, then wordmark and tagline. The home screen is revealed with its cascade afterwards
- **Remote control**:
  - long-press OK (Android TV "context menu") or the Menu key opens quick actions: *Play*, *Search a better release* (Radarr/Sonarr);
  - the Play/Pause key plays the movie from the device's Kodi library, matched by TMDB/TVDB id, then by title and year, with resume; for a series it opens its seasons;
  - a key-hint row is shown under the rail;
  - a **Search** button opens Kodi's keyboard, whose microphone allows voice input on Android
- **New brand: "Lecture" logo** (an "A" whose crossbar is a play button), vector, in the UI accent colours. `branding/arrmada-mark.svg` is the single source, and `branding/export.py` derives every image from it: favicon, app icons, share image, README banner, Kodi icon, fanart and intro layers. The web app draws it inline (`BrandMark` / `BrandIcon`); on the login page, the splash screen and the dashboard hero, the "A" draws itself and the play button pops
- Entry "Accueil ArrMada (apercu v2)" in the add-on, also reachable from the SiLVO menu with `RunPlugin(plugin://script.arrmada/?action=home)`
- Media items expose `fanart_url`
- CI job "Kodi add-on — Tests": ruff + pytest, without Kodi. It checks the home logic, cache, XML ↔ Python ids, SiLVO font names, texture files and unsupported glyphs
- Visual bench `kodi-addon/bench/run.sh`: real Kodi under Xvfb, mock backend with realistic posters and backdrops, SiLVO fonts, remote-control script, 11 screenshots, optional video (`RECORD=1`)
- `kodi-addon/tools/make_textures.py`: dependency-free generator for the window textures

#### Fixed
- `/api/kodi/widgets/recent` was not sorted (it sorted on a missing `added_at` key)
- Kodi download queue: `timeleft` was always empty and `size` always 0 (wrong source keys). Items now also carry `id` and `size_left`

### Server features (developed on the Unraid host, merged into UI v2)

#### Added
- **Kodi add-on** (`kodi-addon/`, v1.3.2) and its API under `/api/kodi`: live scrobbling, add-on dashboard and status, home-screen widgets, media lookup/add, interactive releases, queue pause/resume/remove, subtitle search & audio sync (Bazarr), library maintenance. The add-on authenticates with `X-Api-Key` = `ARRMADA_AUTH_SECRET`
- **Docker logs**: aggregated, level-classified logs from the service containers (`/api/files/docker/logs`, needs `/var/run/docker.sock:ro`) and AI analysis grouping problems with causes and fixes (`POST …/logs/analyze`, local Ollama or OpenRouter)
- **Local AI assistant** (Ollama): weekly summary of added media
- **Yamaha room profiles** (Salon / Cinéma): sound program, dialogue lift, DRC, enhancer, extra bass; applied automatically when playing a movie on Kodi
- Recommendations: "because you have…" for series too, TMDB detail modal endpoint, targeted recommendations based on a library title
- Media items expose resolution, video/audio codecs, HDR, channels, studio/network and ClearLogo
- Auto-import: scans the folder as seen by *arr (`ARR_DOWNLOADS_PATH`), never overwrites an existing file unless `AUTO_IMPORT_ALLOW_OVERWRITE=true`, execution reports
- Scripts: orphan import/cleanup, cinema audio profile, weekly summary
- UI (ported to the v2 design): technical badges on posters and media sheet, studio/network marks, ClearLogo title, trailer modal, split "Play on Kodi · room" button that also tunes the amp, saved library filter presets; TMDB detail modal and "from a title of your library" recommendations in Discover; Docker log stream + AI diagnosis in System → Docker; room profile editor (Settings → Yamaha) and room presets in the Salon

#### Fixed
- Yamaha room profiles crashed on save (`cache.set` does not exist) and were kept in memory only: now persisted to `data/yamaha_room_profiles.json`
- Series "because you have…" recommendations queried TMDB with the Sonarr TVDB id (wrong show)
- API-key authentication uses a constant-time comparison

#### Security
- The add-on no longer ships a hard-coded default API key; `.gitignore` now covers `.env.*` copies and `*.bak` files

### UI v2 — « Neon Armada »

#### Added
- New dark-only design system: #4A9EFF / brand-cyan tokens, glassmorphism, animated aurora background, grain, shimmer skeletons, Geist fonts (bundled, no Google Fonts at build time)
- Motion kit: animated counters, ring gauges, 3D-tilt posters, mouse spotlight, gradient progress bars, page transitions, `prefers-reduced-motion` support
- App shell: floating animated sidebar with live badges (downloads, unread, missing), breadcrumb header with live (SSE) indicator and notifications popover, floating mobile tab bar, global mini-player following Kodi playback
- Command palette (⌘K / `/`): direct media sheets, all pages, actions (Kodi sync, refresh, mark all read, add a title)
- Keyboard shortcuts `g` + key, `[` (sidebar), `?` (cheat-sheet)
- Real-time toasts on imports, grabs and service outages
- **Dashboard** "command bridge": greeting + fleet summary, KPIs with gauges, services strip, recently-added carousel, unified activity, live queue, this week's releases, storage, TRaSH compliance
- **Salon** page (`/remote`): Kodi player (seekable slider, ±10/30 s, volume), Yamaha amp remote, Cast devices
- **Santé médiathèque** hub (`/health`): quality / duplicates / cleanup with health score and per-row actions
- Settings hub with sub-navigation (general, *arr services, Kodi, Cast & Jellyfin, Yamaha)
- Media library: URL state, grid/list views, filter chips, cross-page selection + floating action bar; Missing: bulk search with progress & stop; Search: manual add by TMDB/TVDB id, preview, streaming-style suggestion rails
- Media sheet split into components with cinematic hero, accessible seasons accordion with "upcoming" state, sortable/filterable releases
- Downloads hub (queue + imports), calendar month/agenda views, grouped notifications, unified indexers table, live server resources + Docker panel, analytics with table views
- `?refresh=1` on `/api/cleanup` and `/api/quality`; `start`/`end` on `/api/calendar`; `category` filter and `POST /api/services/test`; `PUT` for Kodi/Yamaha settings; version + default-secret flag in `/api/settings`

#### Changed
- Navigation reorganised; legacy URLs (`/quality`, `/duplicates`, `/cleanup`, `/fichiers`, `/docker`, `/requests`, `/recommendations`, `/services`, `/settings/profile-overrides`, `/settings/sabnzbd-config`) redirect to their new home
- French UI everywhere (tutoiement), French byte units (Go, To) from the backend too, genres displayed in French
- Kodi now-playing polling is adaptive (3 s while playing, 20 s idle, 60 s when unreachable)

#### Fixed
- Toasts from the legacy `useToast` hook were never rendered (TRaSH Guides, Settings)
- Naive UTC timestamps displayed 1–2 h off; calendar shifted by one day (UTC keys); past months empty
- Wrong series added from TMDB trending (TMDB id treated as TVDB); broken "because you have…" suggestions
- Series quality showed the numeric Sonarr profile id; movie crew always empty
- Kodi/Yamaha devices health-checked with the *arr client and listed as *arr services
- Media deletion without cache invalidation, scraper offered for series, stale edit dialogs, unaired episodes flagged as missing, duplicated imports in the activity timeline, Docker failures returned as HTTP 200
- `alert()`/`confirm()` replaced by toasts and confirmation dialogs everywhere; error states instead of blank pages
- Collapsing the sidebar left an empty gutter; menu double highlight; backend outage redirected to the setup wizard
- TypeScript errors that broke `tsc --noEmit` in CI

#### Security
- `GET /api/kodi/settings` no longer returns the decrypted Kodi password; empty password on update keeps the stored one

### Platform

#### Added
- Rate limiting on `/api/auth/login` (5 attempts/minute) to prevent brute force
- Security headers: HSTS, CSP, Permissions-Policy
- CI/CD pipeline via GitHub Actions (lint, test, build)
- Test coverage for media, downloads, analytics, duplicates, recommendations, requests, search endpoints
- Security-specific tests (headers, rate limiting)
- `.dockerignore` for smaller production images
- `pyproject.toml` with ruff, pytest, and coverage configuration
- OpenAPI examples in Pydantic schemas for better Swagger docs
- Docker resource limits in `docker-compose.yml`
- Explicit Docker network (`arrmada-network`)

#### Changed
- CORS: restricted `allow_methods` and `allow_headers` (was `*`)
- Dockerfile: multi-stage build, non-root user, Python-based healthcheck
- docker-compose: removed deprecated `version` field, Python-based healthcheck

#### Security
- Fixed overly permissive CORS configuration
- Added brute force protection via rate limiting
- Added HSTS header for transport security
- Added Content-Security-Policy header
- Docker container now runs as non-root user

## [0.1.0] — 2025-12-15

### Added
- Initial release
- Unified dashboard for all *arr services
- Cross-platform media search
- AI recommendations via scikit-learn
- Library analytics and charts
- Duplicate detection
- Overseerr-like media request system
- Real-time health monitoring
- Telegram notifications
- Dark mode UI
- JWT authentication with Fernet-encrypted API keys
- Docker Compose deployment
