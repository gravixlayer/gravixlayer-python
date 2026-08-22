"""
Pytest configuration shared by every unit test.

Unit tests never talk to the API, so they must not read the developer's
credentials either: a key left in the shell would otherwise change what some
tests assert. Each test starts from a clean environment and opts back in with
``monkeypatch.setenv`` when it wants to exercise configuration from the
environment.
"""

import os

import pytest

_SDK_ENV_PREFIX = "GRAVIXLAYER_"


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    """Hide any GravixLayer configuration the surrounding shell exported."""
    for name in [key for key in os.environ if key.startswith(_SDK_ENV_PREFIX)]:
        monkeypatch.delenv(name, raising=False)
