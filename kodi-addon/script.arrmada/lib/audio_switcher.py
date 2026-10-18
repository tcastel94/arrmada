# -*- coding: utf-8 -*-
"""Auto Audio Switcher module for ArrMada Kodi add-on."""

from __future__ import annotations

import xbmc
import xbmcaddon
from kodi_helper import get_setting_bool, show_notification

ADDON = xbmcaddon.Addon("script.arrmada")

def run_audio_switch(player: xbmc.Player):
    """Evaluate and switch audio stream based on the room profile."""
    if not get_setting_bool("auto_audio_switch", default=True):
        return

    room_profile = ADDON.getSetting("room_profile") or "cinema"
    room_profile = room_profile.lower()

    # Wait briefly for streams to be fully populated by Kodi
    xbmc.sleep(2500)

    try:
        if not player.isPlayingVideo():
            return
        streams = player.getAvailableAudioStreams()
        current_stream = player.getAudioStream()
    except Exception as e:
        xbmc.log(f"[ArrMada] AudioSwitcher error: {e}", level=xbmc.LOGDEBUG)
        return

    if not streams or len(streams) <= 1:
        return

    best_index = -1
    best_score = -9999

    for i, stream_name in enumerate(streams):
        stream_lower = stream_name.lower()
        score = 0

        # Language priority: VF or VO (English)
        if 'fre' in stream_lower or 'fra' in stream_lower or 'french' in stream_lower:
            score += 200
        elif 'eng' in stream_lower or 'english' in stream_lower:
            score += 100

        # Codec priority based on room profile
        if room_profile == "cinema":
            # Cinema room has full Atmos / DTS:X capabilities
            if 'atmos' in stream_lower or 'truehd' in stream_lower:
                score += 1000
            elif 'dts-x' in stream_lower or 'dtsx' in stream_lower:
                score += 900
            elif 'dts-hd' in stream_lower or 'dtshd' in stream_lower or 'ma' in stream_lower:
                score += 800
            elif 'eac3' in stream_lower or 'dd+' in stream_lower:
                score += 500
            elif 'ac3' in stream_lower or 'dts' in stream_lower:
                score += 300
        else:
            # Salon (living room) prefers DTS-HD / DTS or AC3 over TrueHD/Atmos if no eARC/Receiver
            if 'dts-hd' in stream_lower or 'dtshd' in stream_lower or 'ma' in stream_lower:
                score += 1000
            elif 'dts' in stream_lower:
                score += 800
            elif 'ac3' in stream_lower or 'eac3' in stream_lower or 'dd+' in stream_lower:
                score += 700
            elif 'truehd' in stream_lower or 'atmos' in stream_lower:
                # Still playable, but less prioritized than DTS for this specific setup
                score += 500

        # Channels priority
        if '7.1' in stream_lower or '8 channels' in stream_lower:
            score += 50
        elif '5.1' in stream_lower or '6 channels' in stream_lower:
            score += 30
        elif '2.0' in stream_lower or '2 channels' in stream_lower or 'stereo' in stream_lower:
            score -= 50  # Penalize stereo

        # Commentary tracks penalty
        if 'commentary' in stream_lower or 'commentaire' in stream_lower:
            score -= 5000

        if score > best_score:
            best_score = score
            best_index = i

    # Switch if a better track is found and it's not already the current one
    if best_index != -1 and best_index != current_stream:
        try:
            player.setAudioStream(best_index)
            # Short notification to confirm it worked
            stream_display = streams[best_index].split('-')[0].strip() if '-' in streams[best_index] else streams[best_index]
            show_notification("Auto Audio Switcher", f"Audio : {stream_display}", time_ms=3000)
            xbmc.log(f"[ArrMada] Auto switched to audio stream {best_index}: {streams[best_index]}", level=xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[ArrMada] Auto Audio Switcher failed to set stream: {e}", level=xbmc.LOGERROR)
