"""
Tests for Identity secret providers (sync + async) — public SDK surface.

Covers full lifecycle: create/list/get/update/delete, secret CRUD,
attach/detach, list_for_runtime. Asserts request payloads and response models.
"""

from __future__ import annotations

import json

import httpx
import pytest

from gravixlayer import AsyncGravixLayer, GravixLayer
from gravixlayer.types.secret_providers import (
    SecretInfo,
    SecretList,
    SecretProvider,
    SecretProviderList,
    SuccessResponse,
)
from tests.utils import (
    IDENTITY_BASE,
    TEST_API_KEY,
    TEST_BASE_URL,
    VALID_UUID,
    make_secret_info_response,
    make_secret_provider_response,
)


SECRET_ID = "87654321-4321-8765-4321-876543218765"
RUNTIME_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
PROVIDER_B = "11111111-2222-3333-4444-555555555555"
PROVIDERS = f"{IDENTITY_BASE}/providers"


# ===================================================================
# Sync Providers — CRUD
# ===================================================================


class TestSyncProvidersCRUD:
    def test_create(self, client, mock_api):
        mock_api.post(PROVIDERS).mock(
            return_value=httpx.Response(
                201, json={"provider": make_secret_provider_response()}
            )
        )
        provider = client.identity.providers.create(
            name="OpenAI",
            provider_type="api_key",
            secrets=[{"key": "OPENAI_API_KEY", "value": "sk-test"}],
        )
        assert isinstance(provider, SecretProvider)
        assert provider.id == VALID_UUID
        assert provider.name == "OpenAI"
        assert provider.provider_type == "api_key"
        assert len(provider.secrets) == 1
        assert provider.secrets[0].key == "OPENAI_API_KEY"
        assert provider.secrets[0].masked == "••••••••"

        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {
            "name": "OpenAI",
            "provider_type": "api_key",
            "secrets": [{"key": "OPENAI_API_KEY", "value": "sk-test"}],
        }

    def test_create_without_secrets(self, client, mock_api):
        mock_api.post(PROVIDERS).mock(
            return_value=httpx.Response(
                201,
                json={
                    "provider": make_secret_provider_response(
                        secret_count=0, secrets=[]
                    )
                },
            )
        )
        provider = client.identity.providers.create(name="Empty")
        assert provider.secret_count == 0
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"name": "Empty", "provider_type": "api_key"}
        assert "secrets" not in body

    def test_create_with_project_id(self, client, mock_api):
        mock_api.post(url__regex=rf"{PROVIDERS}\?project_id=").mock(
            return_value=httpx.Response(
                201, json={"provider": make_secret_provider_response()}
            )
        )
        client.identity.providers.create(name="OpenAI", project_id="proj-001")
        assert "project_id=proj-001" in str(mock_api.calls[-1].request.url)

    def test_list(self, client, mock_api):
        mock_api.get(url__regex=rf"{PROVIDERS}\?").mock(
            return_value=httpx.Response(
                200,
                json={
                    "providers": [
                        make_secret_provider_response(),
                        make_secret_provider_response(id=PROVIDER_B, name="Anthropic"),
                    ],
                    "total": 2,
                },
            )
        )
        result = client.identity.providers.list(limit=50, search="Open")
        assert isinstance(result, SecretProviderList)
        assert result.total == 2
        assert len(result.providers) == 2
        assert "limit=50" in str(mock_api.calls[-1].request.url)
        assert "search=Open" in str(mock_api.calls[-1].request.url)

    def test_get(self, client, mock_api):
        mock_api.get(f"{PROVIDERS}/{VALID_UUID}").mock(
            return_value=httpx.Response(
                200, json={"provider": make_secret_provider_response()}
            )
        )
        provider = client.identity.providers.get(VALID_UUID)
        assert provider.id == VALID_UUID
        assert provider.is_active is True

    def test_update(self, client, mock_api):
        mock_api.patch(f"{PROVIDERS}/{VALID_UUID}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "provider": make_secret_provider_response(
                        name="Renamed", is_active=False
                    )
                },
            )
        )
        provider = client.identity.providers.update(
            VALID_UUID, name="Renamed", is_active=False
        )
        assert provider.name == "Renamed"
        assert provider.is_active is False
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"name": "Renamed", "is_active": False}

    def test_delete(self, client, mock_api):
        mock_api.delete(f"{PROVIDERS}/{VALID_UUID}").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        result = client.identity.providers.delete(VALID_UUID)
        assert isinstance(result, SuccessResponse)
        assert result.success is True


# ===================================================================
# Sync Providers — Secrets
# ===================================================================


class TestSyncProviderSecrets:
    def test_add_secret(self, client, mock_api):
        mock_api.post(f"{PROVIDERS}/{VALID_UUID}/secrets").mock(
            return_value=httpx.Response(
                201, json={"secret": make_secret_info_response()}
            )
        )
        secret = client.identity.providers.add_secret(
            VALID_UUID, key="OPENAI_API_KEY", value="sk-live"
        )
        assert isinstance(secret, SecretInfo)
        assert secret.key == "OPENAI_API_KEY"
        assert secret.value_set is True
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"key": "OPENAI_API_KEY", "value": "sk-live"}

    def test_list_secrets(self, client, mock_api):
        mock_api.get(f"{PROVIDERS}/{VALID_UUID}/secrets").mock(
            return_value=httpx.Response(
                200, json={"secrets": [make_secret_info_response()]}
            )
        )
        result = client.identity.providers.list_secrets(VALID_UUID)
        assert isinstance(result, SecretList)
        assert len(result.secrets) == 1

    def test_list_secrets_empty(self, client, mock_api):
        mock_api.get(f"{PROVIDERS}/{VALID_UUID}/secrets").mock(
            return_value=httpx.Response(200, json={"secrets": []})
        )
        result = client.identity.providers.list_secrets(VALID_UUID)
        assert result.secrets == []

    def test_update_secret(self, client, mock_api):
        mock_api.patch(f"{PROVIDERS}/{VALID_UUID}/secrets/{SECRET_ID}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "secret": make_secret_info_response(key="ANTHROPIC_API_KEY")
                },
            )
        )
        secret = client.identity.providers.update_secret(
            VALID_UUID, SECRET_ID, key="ANTHROPIC_API_KEY", value="sk-new"
        )
        assert secret.key == "ANTHROPIC_API_KEY"
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"key": "ANTHROPIC_API_KEY", "value": "sk-new"}

    def test_delete_secret(self, client, mock_api):
        mock_api.delete(f"{PROVIDERS}/{VALID_UUID}/secrets/{SECRET_ID}").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        result = client.identity.providers.delete_secret(VALID_UUID, SECRET_ID)
        assert result.success is True


# ===================================================================
# Sync Providers — Attachments
# ===================================================================


class TestSyncProviderAttachments:
    def test_attach(self, client, mock_api):
        mock_api.post(f"{PROVIDERS}/{VALID_UUID}/attach").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        result = client.identity.providers.attach(VALID_UUID, RUNTIME_ID)
        assert result.success is True
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"runtime_id": RUNTIME_ID}

    def test_detach(self, client, mock_api):
        mock_api.delete(f"{PROVIDERS}/{VALID_UUID}/attach/{RUNTIME_ID}").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        result = client.identity.providers.detach(VALID_UUID, RUNTIME_ID)
        assert result.success is True

    def test_list_for_runtime(self, client, mock_api):
        mock_api.get(f"{IDENTITY_BASE}/runtimes/{RUNTIME_ID}/providers").mock(
            return_value=httpx.Response(
                200, json={"providers": [make_secret_provider_response()]}
            )
        )
        result = client.identity.providers.list_for_runtime(RUNTIME_ID)
        assert isinstance(result, SecretProviderList)
        assert len(result.providers) == 1
        assert result.total == 1


# ===================================================================
# Types
# ===================================================================


class TestSecretProviderTypes:
    def test_from_api_masks_secrets(self):
        provider = SecretProvider.from_api(make_secret_provider_response())
        assert provider.secrets[0].masked == "••••••••"
        assert "sk-" not in provider.secrets[0].masked

    def test_from_api_missing_secrets_defaults_empty(self):
        data = make_secret_provider_response()
        del data["secrets"]
        data["secret_count"] = 0
        provider = SecretProvider.from_api(data)
        assert provider.secrets == []
        assert provider.secret_count == 0


# ===================================================================
# Async Providers — full lifecycle parity
# ===================================================================


class TestAsyncProviders:
    @pytest.mark.asyncio
    async def test_create_list_get_update_delete(self, mock_api):
        mock_api.post(PROVIDERS).mock(
            return_value=httpx.Response(
                201, json={"provider": make_secret_provider_response()}
            )
        )
        mock_api.get(url__regex=rf"{PROVIDERS}\?").mock(
            return_value=httpx.Response(
                200,
                json={"providers": [make_secret_provider_response()], "total": 1},
            )
        )
        mock_api.get(f"{PROVIDERS}/{VALID_UUID}").mock(
            return_value=httpx.Response(
                200, json={"provider": make_secret_provider_response()}
            )
        )
        mock_api.patch(f"{PROVIDERS}/{VALID_UUID}").mock(
            return_value=httpx.Response(
                200,
                json={"provider": make_secret_provider_response(name="Updated")},
            )
        )
        mock_api.delete(f"{PROVIDERS}/{VALID_UUID}").mock(
            return_value=httpx.Response(200, json={"success": True})
        )

        async with AsyncGravixLayer(
            api_key=TEST_API_KEY, base_url=TEST_BASE_URL
        ) as client:
            created = await client.identity.providers.create(
                name="OpenAI",
                secrets=[{"key": "OPENAI_API_KEY", "value": "sk-x"}],
            )
            assert created.id == VALID_UUID

            listed = await client.identity.providers.list(limit=10)
            assert listed.total == 1

            got = await client.identity.providers.get(VALID_UUID)
            assert got.name == "OpenAI"

            updated = await client.identity.providers.update(
                VALID_UUID, name="Updated"
            )
            assert updated.name == "Updated"

            deleted = await client.identity.providers.delete(VALID_UUID)
            assert deleted.success is True

    @pytest.mark.asyncio
    async def test_secrets_and_attachments(self, mock_api):
        mock_api.post(f"{PROVIDERS}/{VALID_UUID}/secrets").mock(
            return_value=httpx.Response(
                201, json={"secret": make_secret_info_response()}
            )
        )
        mock_api.get(f"{PROVIDERS}/{VALID_UUID}/secrets").mock(
            return_value=httpx.Response(
                200, json={"secrets": [make_secret_info_response()]}
            )
        )
        mock_api.patch(f"{PROVIDERS}/{VALID_UUID}/secrets/{SECRET_ID}").mock(
            return_value=httpx.Response(
                200, json={"secret": make_secret_info_response()}
            )
        )
        mock_api.delete(f"{PROVIDERS}/{VALID_UUID}/secrets/{SECRET_ID}").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        mock_api.post(f"{PROVIDERS}/{VALID_UUID}/attach").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        mock_api.delete(f"{PROVIDERS}/{VALID_UUID}/attach/{RUNTIME_ID}").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        mock_api.get(f"{IDENTITY_BASE}/runtimes/{RUNTIME_ID}/providers").mock(
            return_value=httpx.Response(
                200, json={"providers": [make_secret_provider_response()]}
            )
        )

        async with AsyncGravixLayer(
            api_key=TEST_API_KEY, base_url=TEST_BASE_URL
        ) as client:
            secret = await client.identity.providers.add_secret(
                VALID_UUID, key="OPENAI_API_KEY", value="sk-x"
            )
            assert secret.key == "OPENAI_API_KEY"

            secrets = await client.identity.providers.list_secrets(VALID_UUID)
            assert len(secrets.secrets) == 1

            updated = await client.identity.providers.update_secret(
                VALID_UUID, SECRET_ID, value="sk-y"
            )
            assert updated.value_set is True

            deleted = await client.identity.providers.delete_secret(
                VALID_UUID, SECRET_ID
            )
            assert deleted.success is True

            attached = await client.identity.providers.attach(VALID_UUID, RUNTIME_ID)
            assert attached.success is True

            listed = await client.identity.providers.list_for_runtime(RUNTIME_ID)
            assert len(listed.providers) == 1

            detached = await client.identity.providers.detach(VALID_UUID, RUNTIME_ID)
            assert detached.success is True
