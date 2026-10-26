# -*- coding: utf-8 -*-
"""ArrMada API client for Kodi add-on.

Uses standard Python urllib to remain 100% dependency-free across any Kodi environment.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.parse
import urllib.error
import xbmc
import xbmcaddon

import device
import feeds

ADDON = xbmcaddon.Addon("script.arrmada")


class ArrMadaAPI:
    @staticmethod
    def get_config():
        url = (ADDON.getSetting("server_url") or "").strip().rstrip("/")
        if not url or "127.0.0.1" in url or "localhost" in url:
            url = "http://192.168.2.3:8420"
            try:
                ADDON.setSetting("server_url", url)
            except Exception:
                pass

        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"http://{url}"

        # If user accidentally configured the web frontend port (3420), auto-switch to backend API (8420)
        if ":3420" in url:
            url = url.replace(":3420", ":8420")

        # Clé = mot de passe ArrMada (ARRMADA_AUTH_SECRET du serveur), à saisir
        # dans les réglages de l'add-on. Aucune valeur par défaut en dur : le
        # dépôt est public, un défaut serait un mot de passe publié.
        api_key = (ADDON.getSetting("api_key") or "").strip()

        device_name = (ADDON.getSetting("device_name") or "Kodi").strip()
        language = (ADDON.getSetting("sub_language") or "fr").strip()
        return {
            "url": url,
            "api_key": api_key,
            "device_name": device_name,
            "language": language,
        }



    @classmethod
    def auth_headers(cls, config: dict | None = None) -> dict:
        """En-têtes d'authentification pour CE serveur : le jeton de la TV.

        Depuis la phase 3, la TV n'envoie plus jamais le mot de passe admin
        (une TV volée ne donne plus les droits admin). Une TV qui l'avait
        encore dans ses réglages s'appaire toute seule au démarrage
        (lib/migration.py), puis l'efface. Non appairée : aucun en-tête, le
        serveur répond 401 et l'écran propose « Appairer cette TV ».
        """
        config = config or cls.get_config()
        device_token = device.token_for(config["url"])
        return {"X-Device-Token": device_token} if device_token else {}

    @classmethod
    def _request(
        cls,
        path: str,
        method: str = "GET",
        data: dict | None = None,
        timeout: int = 15,
        headers: dict | None = None,
    ) -> dict:
        config = cls.get_config()
        full_url = f"{config['url']}{path}"
        extra_headers = headers or {}

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "ArrMada-Kodi-Addon/1.0.0",
        }
        auth = cls.auth_headers(config)
        headers.update(auth)
        headers.update(extra_headers)
        device_token = auth.get("X-Device-Token", "")

        req_body = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(full_url, data=req_body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                if not body:
                    return {"status": "ok"}
                # Images des dossiers des médias : adresse relative → absolue
                return feeds.absolute_urls(json.loads(body), config["url"])
        except urllib.error.HTTPError as err:
            err_body = ""
            try:
                err_body = err.read().decode("utf-8")
                err_json = json.loads(err_body)
                msg = err_json.get("detail") or err_json.get("message") or str(err)
            except Exception:
                msg = str(err)
            xbmc.log(f"[ArrMada] HTTPError on {path}: {err.code} - {msg}", level=xbmc.LOGERROR)
            if err.code == 401 and device_token:
                # Appareil révoqué dans la web app (ou base du serveur remise à
                # zéro) : on oublie le jeton, l'écran d'appairage le proposera.
                device.clear()
            return {"status": "error", "message": msg, "code": err.code}
        except urllib.error.URLError as err:
            reason = getattr(err, "reason", str(err))
            msg = f"Connexion impossible à {config['url']} ({reason})."
            xbmc.log(f"[ArrMada] URLError on {path}: {msg}", level=xbmc.LOGERROR)
            return {"status": "error", "message": msg}
        except Exception as exc:
            xbmc.log(f"[ArrMada] Request failed on {path}: {exc}", level=xbmc.LOGERROR)
            return {"status": "error", "message": str(exc)}


    # ── Flux en cache et événements (ADR-003 § 1) ───────────────────────

    @classmethod
    def get_feed(cls, path: str, timeout: int = 15):
        """Réponse brute d'une route (liste ou objet) ; {"status": "error"} en cas d'échec."""
        return cls._request(path, method="GET", timeout=timeout)

    @classmethod
    def get_library_sources(cls) -> dict:
        """{"movies": "data/media/movies", "tv": "data/media/tv"} : dossiers dans le partage SMB du NAS."""
        return cls._request("/api/kodi/library-sources", method="GET", timeout=5)

    @classmethod
    def get_media(cls, params: dict) -> dict:
        """Une page de la bibliothèque (Films / Séries, 1.9.0), triée et filtrée par le serveur."""
        return cls._request(f"/api/media?{urllib.parse.urlencode(params)}", method="GET", timeout=15)

    @classmethod
    def get_media_facets(cls, kind: str) -> dict:
        """Genres présents (et nombre de titres) pour un type : movie | series."""
        return cls._request(f"/api/media/facets?type={kind}", method="GET", timeout=15)

    @classmethod
    def get_qr(cls, path: str = "", youtube: str = "") -> dict:
        """QR code vers la web app ou YouTube : {"url", "png" (base64)} (phase 3)."""
        query = {"youtube": youtube} if youtube else {"path": path or "/"}
        return cls._request(f"/api/qr?{urllib.parse.urlencode(query)}", method="GET", timeout=10)

    @classmethod
    def mark_notification_read(cls, notification_id: str) -> dict:
        return cls._request(f"/api/notifications/{notification_id}/read", method="POST", timeout=8)

    # ── Appairage (ADR-003 § 4) ─────────────────────────────────────────

    @classmethod
    def pair_start(cls, platform: str) -> dict:
        """Demande un code d'appairage (route publique, réseau local)."""
        return cls._request("/api/devices/pair/start", method="POST", data={"platform": platform}, timeout=10)

    @classmethod
    def pair_poll(cls, device_code: str) -> dict:
        """« Le code a-t-il été validé ? » → jeton de l'appareil, une seule fois."""
        return cls._request("/api/devices/pair/poll", method="POST", data={"device_code": device_code}, timeout=10)

    @classmethod
    def pair_confirm_with_password(cls, user_code: str, name: str, room: str, password: str) -> dict:
        """Valide son propre code avec l'ancien mot de passe admin (migration, phase 3).

        Seul et unique usage du mot de passe par la TV : il est effacé des
        réglages dès que le jeton est reçu.
        """
        return cls._request(
            "/api/devices/pair/confirm",
            method="POST",
            data={"user_code": user_code, "name": name, "room": room},
            timeout=10,
            headers={"X-Api-Key": password},
        )

    @classmethod
    def device_me(cls) -> dict:
        """Nom, pièce et ampli de cette TV, tels que réglés dans la web app."""
        return cls._request("/api/devices/me", method="GET", timeout=8)

    @classmethod
    def absolute_url(cls, path: str) -> str:
        """URL complète d'une route du serveur (image du QR code)."""
        return f"{cls.get_config()['url']}{path}"

    @classmethod
    def trigger_subtitles(cls, payload: dict) -> dict:
        """Trigger Bazarr subtitle download."""
        config = cls.get_config()
        if "language" not in payload:
            payload["language"] = config["language"]
        return cls._request("/api/kodi/actions/subtitles", method="POST", data=payload, timeout=30)

    @classmethod
    def trigger_subtitles_sync(cls, payload: dict) -> dict:
        """Trigger Bazarr FFsubsync audio-aligned subtitle synchronization."""
        config = cls.get_config()
        if "language" not in payload:
            payload["language"] = config["language"]
        return cls._request("/api/kodi/actions/subtitles/sync", method="POST", data=payload, timeout=45)

    @classmethod
    def trigger_search(cls, payload: dict) -> dict:
        """Trigger Radarr/Sonarr release search."""
        return cls._request("/api/kodi/actions/search", method="POST", data=payload, timeout=25)


    @classmethod
    def post_watch_states(cls, states: list, merge: bool = False, timeout: int = 5) -> dict:
        """Dépose des états vu / reprise (phase 4.4) ; `merge` : premier passage de la TV."""
        return cls._request(
            "/api/kodi/watch-state",
            method="POST",
            data={"states": states, "merge": bool(merge)},
            timeout=timeout,
        )

    @classmethod
    def send_scrobble(cls, payload: dict) -> dict:
        """Send live playback scrobble."""
        config = cls.get_config()
        payload["device_name"] = config["device_name"]
        return cls._request("/api/kodi/scrobble", method="POST", data=payload, timeout=5)

    @classmethod
    def send_crash_report(cls, payload: dict) -> dict:
        """Fin du journal d'une session de Kodi arrêtée net (1.21.1, lib/crash_report.py)."""
        return cls._request("/api/kodi/crash-report", method="POST", data=payload, timeout=10)

    @classmethod
    def get_addon_status(cls) -> dict:
        """Fetch download queue and service status."""
        return cls._request("/api/kodi/addon-status", method="GET", timeout=10)

    @classmethod
    def trigger_sync(cls) -> dict:
        """Trigger Kodi scan in ArrMada."""
        return cls._request("/api/kodi/sync", method="POST", timeout=15)

    @classmethod
    def trigger_clean(cls) -> dict:
        """Trigger Kodi clean in ArrMada."""
        return cls._request("/api/kodi/clean", method="POST", timeout=15)

    # ── Media Discovery & Releases ────────────────────────────
    @classmethod
    def lookup_media(cls, query: str, media_type: str = "all") -> list:
        """Search for movies and series across Radarr/Sonarr."""
        encoded = urllib.parse.quote(query)
        res = cls._request(f"/api/kodi/media/lookup?q={encoded}&type={media_type}", method="GET", timeout=20)
        return res if isinstance(res, list) else []

    @classmethod
    def get_media_options(cls, media_type: str = "movie") -> dict:
        """Get quality profiles and root folders."""
        return cls._request(f"/api/kodi/media/options?type={media_type}", method="GET", timeout=15)

    @classmethod
    def add_media(cls, payload: dict) -> dict:
        """Add movie/series to Radarr/Sonarr."""
        return cls._request("/api/kodi/media/add", method="POST", data=payload, timeout=30)

    @classmethod
    def get_seasons(cls, title: str = "", tmdb_id=None, tvdb_id=None, season=None) -> dict:
        """Saisons d'une série et épisodes d'une saison (feuille « Télécharger »)."""
        params = {"title": title}
        for key, value in (("tmdb_id", tmdb_id), ("tvdb_id", tvdb_id), ("season", season)):
            if value not in (None, ""):
                params[key] = value
        query = urllib.parse.urlencode(params)
        return cls._request(f"/api/kodi/media/seasons?{query}", method="GET", timeout=25)

    @classmethod
    def get_segments(cls, tvdb_id, season, episode) -> dict:
        """Intro / récap / générique d'un épisode, repérés par Jellyfin (1.25.0)."""
        query = urllib.parse.urlencode({"tvdb_id": tvdb_id, "season": season, "episode": episode})
        return cls._request(f"/api/kodi/segments?{query}", method="GET", timeout=15)

    @classmethod
    def start_download(cls, payload: dict) -> dict:
        """Feuille « Télécharger » : film, série, saison ou épisodes (ADR-005)."""
        return cls._request("/api/kodi/media/download", method="POST", data=payload, timeout=30)

    # ── Écran Téléchargements (ADR-005, lot 3) ──────────────────────────────
    @classmethod
    def get_board(cls) -> dict:
        """Voie « Pour ce soir », reste de la file et état de SABnzbd, en un appel."""
        return cls._request("/api/kodi/downloads/board", method="GET", timeout=15)

    @classmethod
    def queue_action(cls, download_id: str, action: str) -> dict:
        """pause | resume | top sur UN téléchargement SABnzbd."""
        quoted = urllib.parse.quote(download_id, safe="")
        return cls._request(f"/api/kodi/queue/{quoted}/{action}", method="POST", data={}, timeout=15)

    @classmethod
    def cancel_request(cls, request_id: int) -> dict:
        """Annule SA demande « pour ce soir » (médiathèque jamais touchée)."""
        return cls._request(f"/api/kodi/tv-requests/{int(request_id)}/cancel", method="POST", data={}, timeout=20)

    @classmethod
    def retry_request(cls, request_id: int) -> dict:
        """Relance la recherche d'une demande (même portée)."""
        return cls._request(f"/api/kodi/tv-requests/{int(request_id)}/retry", method="POST", data={}, timeout=20)

    @classmethod
    def diagnose_download(cls, service_type: str, download_id: str) -> dict:
        """Pourquoi ce téléchargement est bloqué, et ce que « Débloquer » fera."""
        quoted = urllib.parse.quote(download_id, safe="")
        return cls._request(f"/api/kodi/downloads/{service_type}/{quoted}/diagnose", method="GET", timeout=20)

    @classmethod
    def unstick_download(cls, service_type: str, download_id: str) -> dict:
        """Débloquer : le serveur refait le diagnostic et applique le remède."""
        quoted = urllib.parse.quote(download_id, safe="")
        return cls._request(f"/api/kodi/downloads/{service_type}/{quoted}/unstick", method="POST", data={}, timeout=40)

    @classmethod
    def get_releases(cls, media_type: str, arr_id: int) -> dict:
        """Fetch candidate releases from indexers."""
        return cls._request(f"/api/kodi/media/{media_type}/{arr_id}/releases", method="GET", timeout=60)

    @classmethod
    def grab_release(cls, media_type: str, arr_id: int, payload: dict) -> dict:
        """Grab a selected release."""
        return cls._request(f"/api/kodi/media/{media_type}/{arr_id}/grab", method="POST", data=payload, timeout=30)

    @classmethod
    def get_recommendations(cls) -> dict:
        """Get trending and recommended movies/series from ArrMada backend."""
        res = cls._request("/api/kodi/media/recommendations", method="GET", timeout=20)
        return res.get("data", {}) if isinstance(res, dict) else {}

    @classmethod
    def get_dashboard(cls) -> dict:
        """Get full system dashboard, storage, services, and activities from ArrMada."""
        return cls._request("/api/kodi/dashboard", method="GET", timeout=35)

    # ── Queue Management & Actions ────────────────────────────
    @classmethod
    def remove_queue_item(cls, service_type: str, item_id: int, remove_from_client: bool = True, blocklist: bool = False) -> dict:
        """Cancel/remove a download item."""
        payload = {"remove_from_client": remove_from_client, "blocklist": blocklist}
        return cls._request(f"/api/kodi/downloads/{service_type}/{item_id}/remove", method="POST", data=payload, timeout=10)

    @classmethod
    def resume_queue_item(cls, service_type: str, item_id: int) -> dict:
        """Resume/unpause a download."""
        return cls._request(f"/api/kodi/downloads/{service_type}/{item_id}/resume", method="POST", timeout=20)

    @classmethod
    def pause_queue_item(cls, service_type: str, item_id: int) -> dict:
        """Pause a download."""
        return cls._request(f"/api/kodi/downloads/{service_type}/{item_id}/pause", method="POST", timeout=20)


    # ── Maintenance & Widgets ─────────────────────────────────
    @classmethod
    def clean_orphans(cls) -> dict:
        """Trigger orphan files and empty folders cleanup."""
        return cls._request("/api/kodi/maintenance/clean-orphans", method="POST", timeout=60)

    @classmethod
    def get_recent_media(cls) -> list:
        """Fetch recently added media for Kodi widgets."""
        res = cls._request("/api/kodi/widgets/recent", method="GET", timeout=15)
        return res if isinstance(res, list) else []

    @classmethod
    def get_recent_media_or_none(cls):
        """Comme get_recent_media, mais None en cas d'erreur (≠ liste vide) :
        l'Accueil ne doit pas vider sa rangée sur une panne passagère."""
        res = cls._request("/api/kodi/widgets/recent", method="GET", timeout=15)
        return res if isinstance(res, list) else None


    # ── Écrans de la phase 2 (fiche, téléchargements, Salon) ───
    @classmethod
    def get_media_detail(cls, kind: str, arr_id) -> dict:
        """Fiche complète d'un film (Radarr) ou d'une série (Sonarr), + Bazarr."""
        path_kind = "movie" if kind == "movie" else "series"
        return cls._request(f"/api/media/{path_kind}/{arr_id}", method="GET", timeout=20)

    @classmethod
    def get_downloads(cls) -> list:
        """File de téléchargement complète (Radarr + Sonarr)."""
        res = cls._request("/api/downloads", method="GET", timeout=15)
        return res.get("items", []) if isinstance(res, dict) else []

    @classmethod
    def yamaha_state(cls) -> dict:
        """État de l'ampli : marche, volume, entrée, programme sonore."""
        return cls._request("/api/yamaha/state", method="GET", timeout=8)

    @classmethod
    def yamaha_profiles(cls) -> dict:
        """Préréglages des pièces (Salon / Salle de cinéma)."""
        return cls._request("/api/yamaha/profiles", method="GET", timeout=8)

    @classmethod
    def yamaha_control(cls, action: str, value=None) -> dict:
        """Commande de l'ampli : volume_step, mute, power…"""
        return cls._request("/api/yamaha/control", method="POST", data={"action": action, "value": value}, timeout=8)

    @classmethod
    def yamaha_apply_preset(cls, room: str, media_type: str = "movie", audio_codec=None, audio_channels=None) -> dict:
        """Applique le préréglage audio de la pièce (avant de lancer un film)."""
        payload = {"room": room, "media_type": media_type}
        if audio_codec:
            payload["audio_codec"] = audio_codec
        if audio_channels:
            payload["audio_channels"] = audio_channels
        return cls._request("/api/yamaha/preset/apply", method="POST", data=payload, timeout=12)
