"""Plex Now Playing plugin for FiestaBoard."""

import logging
import os
from typing import Any, Dict, List

import requests

from src.plugins.base import PluginBase, PluginResult

logger = logging.getLogger(__name__)

MAX_WIDTH = 15


class PlexNowPlayingPlugin(PluginBase):
    """Fetches current Plex playback session and exposes it as variables."""

    @property
    def plugin_id(self) -> str:
        return "plex_now_playing"

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        errors = []
        plex_url = config.get("plex_url") or os.getenv("PLEX_URL")
        plex_token = config.get("plex_token") or os.getenv("PLEX_TOKEN")

        if not plex_url:
            errors.append("Plex Server URL is required")
        elif not (plex_url.startswith("http://") or plex_url.startswith("https://")):
            errors.append("Plex Server URL must start with http:// or https://")

        if not plex_token:
            errors.append("Plex Token is required")

        return errors

    def fetch_data(self) -> PluginResult:
        plex_url = (self.config.get("plex_url") or os.getenv("PLEX_URL", "")).rstrip("/")
        plex_token = self.config.get("plex_token") or os.getenv("PLEX_TOKEN")
        target_user = (self.config.get("target_user") or "").strip()

        if not plex_url or not plex_token:
            return PluginResult(
                available=False,
                error="Plex URL or Token not configured",
            )

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
        except requests.RequestException as e:
            logger.warning("Plex connection failed: %s", e)
            return PluginResult(
                available=False,
                error=f"Plex connection failed: {e}",
            )
        except ValueError as e:
            logger.warning("Invalid JSON response from Plex: %s", e)
            return PluginResult(
                available=False,
                error="Invalid JSON response from Plex",
            )

        sessions = payload.get("MediaContainer", {}).get("Metadata", []) or []

        if not sessions:
            return PluginResult(
                available=True,
                data=self._idle_data(),
            )

        session = sessions[0]
        if target_user:
            match = next(
                (
                    s for s in sessions
                    if s.get("User", {}).get("title", "").lower() == target_user.lower()
                ),
                None,
            )
            if match:
                session = match
            else:
                return PluginResult(
                    available=True,
                    data=self._idle_data(user=target_user),
                )

        return PluginResult(
            available=True,
            data=self._build_data(session),
        )

    def _idle_data(self, user: str = "") -> Dict[str, Any]:
        return {
            "is_playing": "NO",
            "media_type": "",
            "title": "PLEX MEDIA",
            "subtitle": "",
            "year": "",
            "show_name": "",
            "season_episode": "",
            "episode_title": "",
            "user": self._truncate(user.upper(), MAX_WIDTH),
            "status": "STANDBY",
        }

    def _build_data(self, session: Dict[str, Any]) -> Dict[str, Any]:
        media_type = session.get("type", "")
        user = session.get("User", {}).get("title", "")

        base = {
            "is_playing": "YES",
            "media_type": media_type.upper()[:7],
            "user": self._truncate(user.upper(), MAX_WIDTH),
            "status": "PLAYING",
            "title": "",
            "subtitle": "",
            "year": "",
            "show_name": "",
            "season_episode": "",
            "episode_title": "",
        }

        if media_type == "movie":
            title = session.get("title", "") or ""
            year = session.get("year")
            base["title"] = self._truncate(title.upper(), MAX_WIDTH)
            base["subtitle"] = f"({year})" if year else ""
            base["year"] = str(year) if year else ""
        elif media_type == "episode":
            show = session.get("grandparentTitle", "") or "SERIE"
            season = str(session.get("parentIndex", 1)).zfill(2)
            episode = str(session.get("index", 1)).zfill(2)
            ep_title = session.get("title", "") or ""

            base["show_name"] = self._truncate(show.upper(), MAX_WIDTH)
            base["season_episode"] = f"S{season} E{episode}"
            base["episode_title"] = self._truncate(ep_title.upper(), MAX_WIDTH)
            base["title"] = base["show_name"]
            base["subtitle"] = base["season_episode"]
        else:
            title = session.get("title", "") or ""
            base["title"] = self._truncate(title.upper(), MAX_WIDTH)

        return base

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        if not text:
            return ""
        return text[:max_len]
