"""Plex Now Playing plugin for FiestaBoard with smart Note wrapping."""

import logging
import os
import textwrap
from typing import Any, Dict, List

import requests

from src.plugins.base import PluginBase, PluginResult

logger = logging.getLogger(__name__)

MAX_WIDTH = 15


class PlexNowPlayingPlugin(PluginBase):
    """Fetches current Plex playback session and exposes smart formatted lines."""

    @property
    def plugin_id(self) -> str:
        return "plex_now_playing"

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        errors = []
        plex_url = config.get("plex_url") or os.getenv("PLEX_URL")
        plex_token = config.get("plex_token") or os.getenv("PLEX_TOKEN")

        if not plex_url:
            errors.append("Plex Server URL is required")
        if not plex_token:
            errors.append("Plex Token is required")

        return errors

    def fetch_data(self) -> PluginResult:
        plex_url = (self.config.get("plex_url") or os.getenv("PLEX_URL", "")).rstrip("/")
        plex_token = self.config.get("plex_token") or os.getenv("PLEX_TOKEN")
        target_user = (self.config.get("target_user") or "").strip()

        if not plex_url or not plex_token:
            return PluginResult(available=False, error="Plex URL or Token not configured")

        try:
            response = requests.get(
                f"{plex_url}/status/sessions",
                headers={
                    "X-Plex-Token": plex_token,
                    "Accept": "application/json",
                },
                timeout=5,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as e:
            logger.warning("Plex connection failed: %s", e)
            return PluginResult(available=False, error=f"Plex connection failed: {e}")

        sessions = payload.get("MediaContainer", {}).get("Metadata", []) or []

        if not sessions:
            return PluginResult(available=True, data=self._idle_data())

        session = sessions[0]
        if target_user:
            match = next(
                (s for s in sessions if s.get("User", {}).get("title", "").lower() == target_user.lower()),
                None,
            )
            if match:
                session = match
            else:
                return PluginResult(available=True, data=self._idle_data(user=target_user))

        return PluginResult(available=True, data=self._build_data(session))

    def _idle_data(self, user: str = "") -> Dict[str, Any]:
        return {
            "is_playing": "NO",
            "media_type": "",
            "line1": "PLEX MEDIA",
            "line2": "",
            "line3": "STANDBY",
            "title": "PLEX MEDIA",
            "year": "",
            "show_name": "",
            "season_episode": "",
            "episode_title": "",
            "user": user.upper()[:MAX_WIDTH],
            "status": "STANDBY",
        }

    def _build_data(self, session: Dict[str, Any]) -> Dict[str, Any]:
        media_type = session.get("type", "")
        user = session.get("User", {}).get("title", "")

        base = {
            "is_playing": "YES",
            "media_type": media_type.upper()[:7],
            "user": user.upper()[:MAX_WIDTH],
            "status": "PLAYING",
            "line1": "",
            "line2": "",
            "line3": "",
            "title": "",
            "year": "",
            "show_name": "",
            "season_episode": "",
            "episode_title": "",
        }

        if media_type == "movie":
            title = (session.get("title") or "").upper().strip()
            year = str(session.get("year")) if session.get("year") else ""

            # Movie title wrapped over max 2 lines
            m_lines = self._wrap_to_lines(title, width=MAX_WIDTH, max_lines=2)

            base["line1"] = m_lines[0]
            base["line2"] = m_lines[1]
            base["line3"] = year  # Year without parentheses
            base["title"] = title[:MAX_WIDTH]
            base["year"] = year

        elif media_type == "episode":
            show = (session.get("grandparentTitle") or "SERIE").upper().strip()
            season = str(session.get("parentIndex", 1)).zfill(2)
            episode = str(session.get("index", 1)).zfill(2)
            ep_title = (session.get("title") or "").upper().strip()
            se_str = f"S{season} E{episode}"

            if len(show) <= MAX_WIDTH:
                # Show fits in Line 1
                base["line1"] = show
                base["line2"] = se_str
                base["line3"] = self._truncate_with_dots(ep_title, max_len=MAX_WIDTH)
            else:
                # Show takes Line 1 & Line 2
                s_lines = self._wrap_to_lines(show, width=MAX_WIDTH, max_lines=2)
                base["line1"] = s_lines[0]
                base["line2"] = s_lines[1]
                base["line3"] = se_str

            base["show_name"] = show[:MAX_WIDTH]
            base["season_episode"] = se_str
            base["episode_title"] = ep_title[:MAX_WIDTH]

        return base

    @staticmethod
    def _wrap_to_lines(text: str, width: int = 15, max_lines: int = 2) -> List[str]:
        if not text:
            return [""] * max_lines
        lines = textwrap.wrap(text, width=width, break_long_words=True, break_on_hyphens=False)
        while len(lines) < max_lines:
            lines.append("")
        return lines[:max_lines]

    @staticmethod
    def _truncate_with_dots(text: str, max_len: int = 15) -> str:
        if not text:
            return ""
        if len(text) > max_len:
            return text[: max_len - 3] + "..."
        return text
