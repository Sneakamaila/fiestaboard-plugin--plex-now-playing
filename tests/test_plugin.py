"""Tests for plex_now_playing plugin."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from plugins.plex_now_playing import PlexNowPlayingPlugin


def _make_plugin(config=None):
    manifest_path = Path(__file__).parent.parent / "manifest.json"
    with open(manifest_path) as f:
        manifest = json.load(f)
    plugin = PlexNowPlayingPlugin(manifest)
    if config:
        plugin.config = config
    else:
        plugin.config = {}
    return plugin


def _mock_response(payload, status=200):
    mock = MagicMock()
    mock.status_code = status
    mock.json.return_value = payload
    mock.raise_for_status = MagicMock()
    return mock


class TestPluginIdentity:
    def test_plugin_id(self):
        plugin = _make_plugin()
        assert plugin.plugin_id == "plex_now_playing"


class TestValidateConfig:
    def test_valid_config(self, sample_config):
        plugin = _make_plugin()
        errors = plugin.validate_config(sample_config)
        assert errors == []

    def test_missing_url(self):
        plugin = _make_plugin()
        errors = plugin.validate_config({"plex_token": "abc"})
        assert any("URL" in e for e in errors)

    def test_missing_token(self):
        plugin = _make_plugin()
        errors = plugin.validate_config({"plex_url": "http://x:32400"})
        assert any("Token" in e for e in errors)

    def test_invalid_url_scheme(self):
        plugin = _make_plugin()
        errors = plugin.validate_config(
            {"plex_url": "ftp://foo", "plex_token": "abc"}
        )
        assert any("http://" in e for e in errors)


class TestFetchDataMovie:
    def test_movie_session(self, sample_config, movie_session_payload):
        plugin = _make_plugin(sample_config)
        with patch("requests.get", return_value=_mock_response(movie_session_payload)):
            result = plugin.fetch_data()

        assert result.available is True
        assert result.data["is_playing"] == "YES"
        assert result.data["media_type"] == "MOVIE"
        assert result.data["title"] == "INTERSTELLAR"
        assert result.data["subtitle"] == "(2014)"
        assert result.data["year"] == "2014"
        assert result.data["user"] == "MAX"


class TestFetchDataEpisode:
    def test_episode_session(self, sample_config, episode_session_payload):
        plugin = _make_plugin(sample_config)
        with patch("requests.get", return_value=_mock_response(episode_session_payload)):
            result = plugin.fetch_data()

        assert result.available is True
        assert result.data["is_playing"] == "YES"
        assert result.data["show_name"] == "BREAKING BAD"
        assert result.data["season_episode"] == "S05 E14"
        assert result.data["episode_title"] == "OZYMANDIAS"


class TestFetchDataIdle:
    def test_empty_sessions(self, sample_config, empty_sessions_payload):
        plugin = _make_plugin(sample_config)
        with patch("requests.get", return_value=_mock_response(empty_sessions_payload)):
            result = plugin.fetch_data()

        assert result.available is True
        assert result.data["is_playing"] == "NO"
        assert result.data["status"] == "STANDBY"


class TestFetchDataUserFilter:
    def test_matching_user(self, sample_config, movie_session_payload):
        config = {**sample_config, "target_user": "Max"}
        plugin = _make_plugin(config)
        with patch("requests.get", return_value=_mock_response(movie_session_payload)):
            result = plugin.fetch_data()

        assert result.data["is_playing"] == "YES"
        assert result.data["user"] == "MAX"

    def test_non_matching_user(self, sample_config, movie_session_payload):
        config = {**sample_config, "target_user": "Ghost"}
        plugin = _make_plugin(config)
        with patch("requests.get", return_value=_mock_response(movie_session_payload)):
            result = plugin.fetch_data()

        assert result.data["is_playing"] == "NO"
        assert result.data["status"] == "STANDBY"


class TestFetchDataErrors:
    def test_missing_config(self):
        plugin = _make_plugin({})
        result = plugin.fetch_data()
        assert result.available is False
        assert "not configured" in result.error

    def test_network_error(self, sample_config):
        plugin = _make_plugin(sample_config)
        with patch("requests.get", side_effect=requests.ConnectionError("no route")):
            result = plugin.fetch_data()
        assert result.available is False
        assert "connection failed" in result.error.lower()

    def test_invalid_json(self, sample_config):
        plugin = _make_plugin(sample_config)
        bad = MagicMock()
        bad.raise_for_status = MagicMock()
        bad.json.side_effect = ValueError("bad json")
        with patch("requests.get", return_value=bad):
            result = plugin.fetch_data()
        assert result.available is False
        assert "invalid json" in result.error.lower()


class TestVariablesMatchManifest:
    def test_data_keys_match_manifest(self, sample_config, movie_session_payload):
        plugin = _make_plugin(sample_config)
        with patch("requests.get", return_value=_mock_response(movie_session_payload)):
            result = plugin.fetch_data()

        manifest_path = Path(__file__).parent.parent / "manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)
        declared = manifest["variables"]["simple"]

        for var in declared:
            assert var in result.data, f"Missing variable: {var}"
