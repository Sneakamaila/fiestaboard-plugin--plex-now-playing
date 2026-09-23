"""Shared test fixtures for the Plex Now Playing plugin."""

import pytest


@pytest.fixture
def sample_config():
    return {
        "plex_url": "http://192.168.1.50:32400",
        "plex_token": "test_token_xyz",
        "refresh_seconds": 30,
    }


@pytest.fixture
def movie_session_payload():
    return {
        "MediaContainer": {
            "Metadata": [
                {
                    "type": "movie",
                    "title": "Interstellar",
                    "year": 2014,
                    "User": {"title": "Max"},
                }
            ]
        }
    }


@pytest.fixture
def episode_session_payload():
    return {
        "MediaContainer": {
            "Metadata": [
                {
                    "type": "episode",
                    "grandparentTitle": "Breaking Bad",
                    "parentIndex": 5,
                    "index": 14,
                    "title": "Ozymandias",
                    "User": {"title": "Max"},
                }
            ]
        }
    }


@pytest.fixture
def empty_sessions_payload():
    return {"MediaContainer": {}}
