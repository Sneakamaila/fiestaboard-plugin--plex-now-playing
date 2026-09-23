"""Plex Now Playing plugin for FiestaBoard with smart Note wrapping and centering."""

import logging
import os
import textwrap
from typing import Any, Dict, List, Tuple

import requests

from src.plugins.base import PluginBase, PluginResult

logger = logging.getLogger(__name__)

MAX_WIDTH = 15


class PlexNowPlayingPlugin(PluginBase):
    """Fetches current Plex playback session and exposes smart formatted lines for Vestaboard Note."""

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

    # ---------- Formatting Helpers ----------

    @staticmethod
    def _center(text: str, width: int = MAX_WIDTH) -> str:
        """Centers text cleanly within the given board width."""
        text = text.strip()
        if not text:
            return ""
        if len(text) >= width:
            return text[:width]
        left_pad = (width - len(text)) // 2
        right_pad = width - len(text) - left_pad
        return " " * left_pad + text + " " * right_pad

    def _format_two_line_title(self, text: str, width: int = MAX_WIDTH) -> Tuple[str, str]:
        """
        Formats a title over max 2 lines.
        - Single line (<= 15 chars): Centered.
        - Multi line (> 15 chars): Left-aligned, with '...' if it overflows line 2.
        """
        text = text.strip()
        if not text:
            return "", ""

        if len(text) <= width:
            return self._center(text, width), ""

        lines = textwrap.wrap(text, width=width, break_long_words=True, break_on_hyphens=False)
        if not lines:
            return "", ""

        if len(lines) == 1:
            return self._center(lines[0], width), ""

        line1 = lines[0]
        if len(lines) == 2:
            line2 = lines[1]
        else:
            # Overflows 2 lines -> append '...' to line 2
            line2 = lines[1]
            if len(line2) > width - 3:
                line2 = line2[: width - 3] + "..."
            else:
                line2 = line2 + "..."

        return line1, line2

    def _format_ep_title(self, text: str, width: int = MAX_WIDTH) -> str:
        """Formats episode title: Centered if fits, otherwise truncated with '...'."""
        text = text.strip()
        if not text:
            return ""
        if len(text) <= width:
            return self._center(text, width)
        return text[: width - 3] + "..."

    # ---------- Data Builders ----------

    def _idle_data(self, user: str = "") -> Dict[str, Any]:
        return {
            "is_playing": "NO",
            "media_type": "",
            "line1": self._center("PLEX MEDIA"),
            "line2": "",
            "line3": self._center("STANDBY"),
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

            line1, line2 = self._format_two_line_title(title, width=MAX_WIDTH)
            line3 = self._center(year, width=MAX_WIDTH)

            base["line1"] = line1
            base["line2"] = line2
            base["line3"] = line3
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
                base["line1"] = self._center(show, width=MAX_WIDTH)
                base["line2"] = self._center(se_str, width=MAX_WIDTH)
                base["line3"] = self._format_ep_title(ep_title, width=MAX_WIDTH)
            else:
                # Show wraps to Line 1 & Line 2
                line1, line2 = self._format_two_line_title(show, width=MAX_WIDTH)
                base["line1"] = line1
                base["line2"] = line2
                base["line3"] = self._center(se_str, width=MAX_WIDTH)

            base["show_name"] = show[:MAX_WIDTH]
            base["season_episode"] = se_str
            base["episode_title"] = ep_title[:MAX_WIDTH]

        return base
