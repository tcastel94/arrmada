# Changelog

All notable changes to ArrMada will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### "Bureau" room without an amplifier, pairing from the ArrMada home (Kodi add-on 1.19.1)

#### Added
- **Room "Bureau"** (office) for paired devices, **without an amplifier**: the server drops any amplifier when a device is paired in, or moved to, the office (`AMP_ROOMS` = salon, cinema); devices are serialized with `has_amp`; `/api/yamaha/state`, `/control` and `/preset/apply` answer `no_amp` to a TV without an amplifier, and the ambient screen shows no amplifier for that room
- **Web app**: "Bureau" in the pairing form and the device editor (amplifier list disabled: "Pas d'ampli dans cette pièce"), labels in "Sur la TV" and the ambient screen preview
- **Add-on 1.19.1 — pairing from the ArrMada home**: an unpaired TV (and no legacy password) opens the pairing screen by itself on the home, once per Kodi session; the home *Réglages* button now opens a list: *Appairer cette TV* / *Refaire l'appairage (…)*, add-on settings, Kodi settings. After pairing, the service polls events and refreshes every feed at once, and the home reloads as soon as a feed changes (`arrmada.reload`) instead of every 2 minutes
- **Add-on 1.19.1 — no amplifier in the office**: no room preset when playback starts, no *Ampli* section in the in-player panel, the Salon screen hides volume, mute, power and presets ("Pas d'ampli dans cette pièce"); the TV re-reads its name, room and amplifier (`/api/devices/me`) on each reconnection to the server
- Tests: backend (office device never gets an amplifier, moving a TV to the office drops it, `no_amp` answers, ambient screen); add-on (`has_amp`, pairing offer once and only when unpaired, settings menu). Bench: automatic pairing offer on the home, office TV paired, settings menu, Salon screen and playback without any preset

#### Fixed
- A paired TV without a chosen amplifier no longer falls back to the first active amplifier (the living-room one) when it sits in a room without an amplifier

### Shared watched state in the web app, "Play on TV" (Kodi add-on 1.19.0)

#### Added
- **Web app — library badges from the TVs**: "Vu", "⏵ 27 %" (started film) and "8 ép." (episodes watched in a series) come from the watched / resume states the paired TVs already share (`watch_states`), for films (TMDB) and now series (TVDB); the *Watched / Not watched / In progress* filters use them (a partly watched series counts as in progress). Falls back to the direct Kodi reading (films only) when no TV has shared anything. Refreshed live on the `watch_state` event
- **Web app — "Reprendre" page** (`/media/continue`, *Library* menu, `g e`): films and episodes started on the TVs, most recent first, with the stop time, time left, the TV and when; each poster has a TV button
- **Web app — "Sur la TV"**: on a film with a file, on a series ("S02E05 sur la TV": the episode in progress, else the one after the last watched) and on each "Reprendre" poster: pick a paired TV, *Reprendre à 42:10* or *Depuis le début*; TVs not seen for 2 min 30 are marked "absente"
- **Backend**: `GET /api/kodi/watch-summary` (films by TMDB, series by TVDB with watched / in-progress counts and last episode, "Reprendre" rows with poster and sheet link from the cached library; not open to TVs) and `POST /api/kodi/play-on-device` (admin only: TV id + title as in the shared state; publishes `play_request` with the target device id, the time and a request id; `online` tells whether the TV was seen recently). `services/watch_summary.py` (pure, tested)
- **Add-on 1.19.0**: the service takes a `play_request` only when it targets this TV **and** is less than 2 minutes old (no surprise playback when a TV wakes up or the server replays its history), then runs the playback in a separate plugin call (the service loop never waits): the title is found in this TV's Kodi library by its public ids and played the ArrMada way (resume or from the start, next episodes queued, room amplifier preset); a bubble says when the title is not in this TV's library. `lib/remote_data.py` (pure, tested: target, age and clock skew, URL flags, library lookup)
- Tests: backend (summary from TV states, series counts, "Reprendre" rows with posters, play request validation, online flag, TV scope, admin only); add-on (remote play). Bench: request for another TV ignored, episode started from the beginning with the next ones queued, expired request ignored, title missing → bubble. Web app checked with Playwright (desktop and phone)

### Kodi add-on 1.18.0 — "Tonight": what ends before the chosen time

#### Added
- **"Ce soir" (Tonight)** in the home menu (also `plugin://script.arrmada/?action=tonight`): the ArrMada grid with end-time tabs — five times every 30 minutes, the first at least 45 minutes from now ("Avant 22:00", "Avant 22:30"…), then "Sans limite"; the tab opened by default is the first one leaving 2 hours. Each tab only shows what will be **finished** before that time, starting now: started films and episodes (time left = duration − resume point), the next episode of each series in progress, then never-watched films of the library, most recently added first. Each poster says "Reprise à 42:10 · reste 1 h 53 · fini vers 22:40" or "1 h 25 · fini vers 22:12". OK plays like the Continue row (resume prompt, chained episodes, amplifier preset); long press offers From the beginning, Mark as watched, Open the series. Titles without a known duration only appear in "Sans limite" ("durée inconnue")
- The time comes from the TV clock (`System.Time`), not from Python's local time (not always right on Android). Found on the bench: Kodi lowercases the format and follows the regional 12 h / 24 h setting whatever is asked (`HH:mm:ss` gave 05:43 at 17:43), so the add-on asks for `hh:mm:ss xx` and converts "05:43:58 PM" to 17:43:58
- `lib/tonight_data.py` (pure, tested: TV clock reading, tabs across midnight, default tab, candidate order without duplicates, end times rounded to the minute, unknown durations, entries) and `kodi_library.unwatched_movies` / `tonight_candidates`; home menu has 11 buttons (text padding 16 → 12 px so that they still fit)
- Bench: library durations in the `.nfo` files; "Ce soir" from the menu, first time slot (a 2 h 58 film left out) and "Sans limite" (the film is there)

### Kodi add-on 1.17.0 — Skip intro, end credits, automatic subtitles

#### Added
- **"Skip intro" / "Skip recap" button**: when the current chapter of the file is named *Intro*, *Opening*, *Générique*, *Title sequence*, *Previously on*, *Recap*…, a button appears bottom right for 10 s, already focused: OK jumps to the start of the next chapter, Back or nothing hides it. Once per chapter; nothing for files without named chapters (no guessing). Setting *Playback → "Skip intro" button* (on by default)
- **Chapters read from MKV files**: Kodi 20 does not update its "current chapter" during normal playback (only after a seek) and its API has no chapter list, so for MKV files (local, `smb://`, `nfs://`) the add-on reads the chapter table from the file header itself (64 KB blocks, once per playback, Chapters element found before the clusters or through the SeekHead, default edition, hidden chapters skipped) and compares it with the playback position. Other formats keep Kodi's chapter information
- **End credits**: in an episode, as soon as the *End Credits* / *Ending* / *Générique de fin* chapter starts, the "Next episode" card opens without waiting for the last 20 seconds
- **Automatic subtitles**: 8 s after a library film or episode starts, when the audio is in another language than yours (*Subtitle language* setting) and no full subtitle track in your language exists (forced ones do not count), Bazarr searches on its own; the file found is loaded and shown without restarting the film. Silent when Bazarr is missing or the title is unknown (log line only). Setting *Playback → Automatic subtitles* (on by default)
- `lib/chapter_data.py` (pure, tested: chapter names in French and English, once per chapter, last chapter, chapter at a position, skip target), `lib/mkv_chapters.py` (pure EBML reader, tested with synthetic files: chapters before the clusters, via the SeekHead, no chapters, MP4, truncated file) and `lib/skip_window.py`; `player_data.needs_subtitles` (tested: original version, forced only, already there, French audio, unknown audio)
- Bench: a library MKV episode with English audio, no subtitles and named chapters (*Previously on*, *Opening*, *Episode*, *End Credits*): skip recap, skip intro, French subtitles found and shown automatically, next-episode card at the start of the end credits

### Kodi add-on 1.16.0 — Panel during playback (ADR-004, phase 4.5)

#### Added
- **Long press OK during playback** opens an ArrMada panel at the bottom of the screen, the video keeps playing above it (a short press still opens Kodi's own seek bar). Header: title, episode, position, **end time** and time left (live, from Kodi's player). Sections:
  - **Audio**: the file's tracks in plain words ("French · Dolby Digital Plus 5.1 · VFF", "English · Dolby TrueHD 7.1 · Original"), current one marked;
  - **Subtitles**: off, the file's tracks (forced, hearing impaired), **Search in French with Bazarr** and **Sync with the audio (Bazarr)**: the panel closes at once, and as soon as Bazarr's file appears next to the video (`Movie.fr.srt`), Kodi loads and shows it without restarting the film (up to 1 min 30 of waiting, notification either way);
  - **Amplifier**: volume − / +, mute, room presets (the amplifier of the TV's room);
  - **Playback**: next episode, stop after this one, next / previous chapter, restart from the beginning.
- The shortcut is a Kodi **keymap file** written by the service (`userdata/keymaps/arrmada.xml`, `FullscreenVideo`: `return` / `enter` / `select` long press) and reloaded at once (`Action(reloadkeymaps)`); setting *Playback → ArrMada panel: long press OK during playback* (on by default); unticked or in safe mode, the file is removed. Also reachable with `plugin://script.arrmada/?action=player`
- `lib/player_data.py` (pure, tested: language and codec names, channel layouts, track lists, sections, new subtitle file detection, keymap content) and `lib/player_window.py`
- Bench: test video with 2 audio tracks, 2 subtitle tracks and 3 chapters (generated by ffmpeg); long press OK, panel, audio and subtitle switch, "Bazarr" subtitle loaded without restarting, amplifier volume, next chapter, Back

### Kodi add-on 1.15.0 — Shared watched state, next episode card, missing episodes (ADR-004, phase 4.4)

#### Added
- **Watched / resume shared between the TVs** (living room ↔ cinema): stop a film at 42:10 on one Shield, the other offers "Resume at 42:10"; finish an episode or mark it watched, the other TV knows a few seconds later. The server is the meeting point: `watch_states` table (one row per film or episode, keyed by public ids — TMDB for films, series TVDB + season + episode — never Kodi's internal numbers, which differ between TVs), `POST /api/kodi/watch-state` (a TV posts what changed; `ON CONFLICT` upsert; unchanged states publish nothing), `GET /api/kodi/watch-state?since=<cursor>` (changes after a strictly increasing cursor, paged) and a `watch_state` event. Both routes allowed for paired TVs
- Add-on: posts what Kodi actually recorded (3 s after a stop or the end of a video, and every "marked watched / unwatched" seen through `VideoLibrary.OnUpdate`, in ArrMada, Kodi or another add-on — library scans are ignored); reads the other TVs' changes at startup, on each `watch_state` event and after a server outage, and applies them with `VideoLibrary.Set*Details`. **First pass** of a TV: only adds (a "watched", a resume point where there is none), then posts what it has already watched (server-side merge: "watched" wins, nothing is undone); afterwards the latest action wins. Echo of its own changes ignored; one minute pause after a network failure (older server). Setting *Playback → Share watched and resume points between TVs* (on by default)
- **"Next episode" card**: 20 s before the end of a library episode (setting *Playback → "Next episode" card*: 0, 10, 20, 30, 45 or 60 s), bottom right: thumbnail, "S01E05 · Title", countdown bar. *Play now* marks the current episode as watched (even when its credits are longer than Kodi's 10 % "watched" margin) and jumps to the next one, *Cancel* stops after this one (the rest of the queue is removed), Back or nothing lets the next episode start as usual. When nothing is queued (episode started from Kodi's interface), the next episode of the series is queued
- **Missing episodes in the series screen**: episodes Sonarr knows and Kodi does not are inserted in place, empty thumbnail and badge — *Missing* (aired, no file; OK asks "Search in Sonarr?"), *On the NAS* (downloaded, not yet scanned; OK starts a Kodi library scan), *Coming soon* (air date in local time, "TBA" titles hidden). A whole missing season is added ("Coming soon" / "Missing"). Unmonitored episodes and specials are not shown. Backend `GET /api/kodi/series/{tvdb}/episodes` (Sonarr episodes, cached 2 minutes, allowed for paired TVs); the screen opens from Kodi's library first and adds the missing episodes a moment later, keeping the selected season and episode
- Tests: backend (merge rules, latest wins, first-pass merge, strictly increasing cursor, paging, two paired TVs, unchanged state publishes nothing, invalid states rejected, TV scope, Sonarr episodes); add-on (key choice and id precedence, Kodi → state, apply rules latest-wins and first-pass, library notifications filter, memory file; card timing, playlist next item, countdown, cancel; missing / NAS / upcoming / TBA, insertion order, start episode kept). Bench: shared state posted by the TV, another TV's watched episode and film resume applied to the local library, series screen with missing / upcoming episodes and the Sonarr search prompt, next-episode card (play now, then cancel and stop at the end)

### Kodi add-on 1.14.1 — smaller camera pop-up, top left, 5 s

#### Changed
- Eufy camera pop-up during a film: compact card (480 × 352 instead of 744 × 496, about a quarter of the screen width) in the **top left** corner instead of the bottom right, where films seldom have subtitles; it closes after **5 s** instead of 15 s (any key still closes it at once). Bubble outside playback unchanged

### Living-room tablet in kiosk mode during a film + Eufy camera pop-ups (Kodi add-on 1.14.0)

#### Added
- **Tablet kiosk mode during a film** (Fully Kiosk Browser, "Remote Admin" API, PLUS licence): when the TV of a room starts a film or an episode, the server brings the room's ambient screen to the foreground on `/ecran` and locks it in kiosk mode (`screenOn`, `toForeground`, `loadStartURL`, `lockKiosk`); when playback stops it unlocks it and sends it to the background (`unlockKiosk`, `toBackground`). Triggered by the scrobbles the TV already sends, in the background (the TV never waits for the tablet). Release only 20 s after a stop (the next episode starts without flapping); a TV switched off without a stop releases the tablet when playback is no longer reported; an unreachable tablet is retried after 5 minutes, not hammered
- Web app, *Settings → Kodi → Devices* → ambient screen: *Kiosk mode during a film* (switch, tablet address — empty: the last address seen — port, Remote Admin password), *Test* (Fully `deviceInfo`), *Release* (manual unlock, way out if the tablet stays locked); the device row shows *Kiosk: locked*
- Backend: `devices.kiosk_control`, `kiosk_host`, `kiosk_port`, `kiosk_password` (Fernet-encrypted, write-only: the API only says whether it is set) added automatically to existing databases; `POST /api/devices/{id}/kiosk/test|lock|release`; private (LAN) addresses only for the tablet, so the server never relays a password to the Internet
- **Eufy cameras**: the backend subscribes to **eufy-security-ws** (`EUFY_WS_URL`, WebSocket; optional `eufy-security-ws` service in `docker-compose.yml`, `eufy` profile, host network, listening on `EUFY_WS_PORT` — default 8424, as the bridge's own default 3000 is often taken on a NAS). A **person detected** (`EUFY_DETECTIONS`, default `person`; also `ring`, `motion`, `pet`, `vehicle`, `package`) waits up to 6 s for the event picture, keeps it in memory (20 pictures, 1 h) and publishes a `camera` event. At most one alert per camera per minute; reconnection with an increasing delay (5 s → 5 min)
- `GET /api/cameras/status` (web app), `GET /api/cameras/snapshot/{id}` (picture in base64, allowed for paired TVs), `POST /api/cameras/test` (fake detection); *Settings → Kodi → Eufy cameras* panel with the bridge state, cameras seen, last alert and a *Test the pop-up* button
- Add-on 1.14.0: **camera pop-up during a film** — bottom right, the picture, "Person detected", camera name and time, 15 s, any key closes it, the film keeps playing; outside playback a notification with the picture as icon. Camera alerts are never held for the "During your film" summary. Setting *Service → Camera alerts* (on by default). One pop-up at a time; the 5 latest pictures kept in the add-on cache
- Bench: Kodi's time limit raised from 8 to 15 minutes. Since the 1.13.0 apps walkthrough, the run was cut before its last part (playback with the living-room screen, server down, TV refused); the 1.13.0 note "71 captures" counted an incomplete run
- Tests: kiosk (lock once, release after the grace delay, next episode within the delay, silent TV, unreachable tablet and retry delay, wrong password, address checks, password never returned, TV refused, column migration, scrobble hook); Eufy (fake eufy-security-ws server: schema negotiation, camera names old and new schemas, picture after or just before the detection, filters, cooldown, missing picture, snapshot store, routes and TV scope); add-on pop-up texts in local time, bubble, one pop-up at a time. Bench: a camera event during a film opens the pop-up over the video, a key closes it without stopping the film, the same event outside playback shows a notification

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
