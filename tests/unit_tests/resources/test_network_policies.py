"""
Tests for sync and async network policies resources.

Covers: create (with/without rules + rollback), list, get (+include_rules),
update, delete, rule CRUD, attach/detach, list_for_runtime (system default filter),
and runtime.create(network_policy_ids=...).
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from gravixlayer import AsyncGravixLayer, GravixLayer
from gravixlayer.types.network_policies import (
    EGRESS_MODE_ALLOWLIST,
    NetworkPolicy,
    NetworkPolicyList,
    NetworkPolicyRule,
    SuccessResponse,
)
from tests.utils import (
    NP_BASE,
    TEST_API_KEY,
    TEST_BASE_URL,
    VALID_UUID,
    make_network_policy_response,
    make_network_policy_rule_response,
)


RULE_ID = "87654321-4321-8765-4321-876543218765"
RUNTIME_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
POLICY_B = "11111111-2222-3333-4444-555555555555"


# ===================================================================
# Sync Network Policies
# ===================================================================


class TestSyncNetworkPoliciesCRUD:
    def test_create(self, client, mock_api):
        mock_api.post(NP_BASE).mock(
            return_value=httpx.Response(
                201, json={"policy": make_network_policy_response(rule_count=0)}
            )
        )
        policy = client.network_policies.create(
            name="openai-only",
            egress_mode="allowlist",
            description="Allow OpenAI HTTPS",
        )
        assert isinstance(policy, NetworkPolicy)
        assert policy.id == VALID_UUID
        assert policy.egress_mode == EGRESS_MODE_ALLOWLIST
        assert policy.rules is None

        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {
            "name": "openai-only",
            "egress_mode": "allowlist",
            "is_default": False,
            "description": "Allow OpenAI HTTPS",
        }

    def test_create_rejects_invalid_egress_mode(self, client, mock_api):
        with pytest.raises(ValueError, match="egress_mode"):
            client.network_policies.create(name="bad", egress_mode="open")

    def test_create_with_rules(self, client, mock_api):
        mock_api.post(NP_BASE).mock(
            return_value=httpx.Response(
                201, json={"policy": make_network_policy_response(rule_count=0)}
            )
        )
        mock_api.post(f"{NP_BASE}/{VALID_UUID}/rules").mock(
            return_value=httpx.Response(
                201, json={"rule": make_network_policy_rule_response()}
            )
        )
        policy = client.network_policies.create(
            name="openai-only",
            rules=[
                {"destination": "api.openai.com", "port": 443, "protocol": "tcp"},
            ],
        )
        assert policy.rules is not None
        assert len(policy.rules) == 1
        assert policy.rules[0].destination == "api.openai.com"
        assert policy.rule_count == 1

        # create + add_rule
        assert len(mock_api.calls) == 2
        rule_body = json.loads(mock_api.calls[1].request.content)
        assert rule_body == {
            "destination": "api.openai.com",
            "port": 443,
            "protocol": "tcp",
        }

    def test_create_with_rules_rolls_back_on_rule_failure(self, client, mock_api):
        mock_api.post(NP_BASE).mock(
            return_value=httpx.Response(
                201, json={"policy": make_network_policy_response(rule_count=0)}
            )
        )
        mock_api.post(f"{NP_BASE}/{VALID_UUID}/rules").mock(
            return_value=httpx.Response(400, json={"error": "invalid destination"})
        )
        mock_api.delete(f"{NP_BASE}/{VALID_UUID}").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        with pytest.raises(RuntimeError, match="rolled back"):
            client.network_policies.create(
                name="openai-only",
                rules=[{"destination": "bad*host", "port": 443}],
            )
        methods = [c.request.method for c in mock_api.calls]
        assert methods == ["POST", "POST", "DELETE"]

    def test_list(self, client, mock_api):
        mock_api.get(url__regex=rf"{NP_BASE}\?").mock(
            return_value=httpx.Response(
                200,
                json={
                    "policies": [
                        make_network_policy_response(),
                        make_network_policy_response(id=POLICY_B, name="deny-all"),
                    ],
                    "total": 2,
                },
            )
        )
        result = client.network_policies.list(limit=50, search="open")
        assert isinstance(result, NetworkPolicyList)
        assert result.total == 2
        assert len(result.policies) == 2
        assert "limit=50" in str(mock_api.calls[-1].request.url)
        assert "search=open" in str(mock_api.calls[-1].request.url)

    def test_list_rejects_bad_limit(self, client, mock_api):
        with pytest.raises(ValueError, match="limit"):
            client.network_policies.list(limit=0)

    def test_get(self, client, mock_api):
        mock_api.get(f"{NP_BASE}/{VALID_UUID}").mock(
            return_value=httpx.Response(
                200, json={"policy": make_network_policy_response()}
            )
        )
        policy = client.network_policies.get(VALID_UUID)
        assert policy.id == VALID_UUID
        assert policy.rules is None

    def test_get_include_rules(self, client, mock_api):
        mock_api.get(f"{NP_BASE}/{VALID_UUID}").mock(
            return_value=httpx.Response(
                200, json={"policy": make_network_policy_response(rule_count=0)}
            )
        )
        mock_api.get(f"{NP_BASE}/{VALID_UUID}/rules").mock(
            return_value=httpx.Response(
                200, json={"rules": [make_network_policy_rule_response()]}
            )
        )
        policy = client.network_policies.get(VALID_UUID, include_rules=True)
        assert policy.rules is not None
        assert len(policy.rules) == 1
        assert policy.rule_count == 1

    def test_update(self, client, mock_api):
        mock_api.patch(f"{NP_BASE}/{VALID_UUID}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "policy": make_network_policy_response(
                        name="renamed", is_active=False
                    )
                },
            )
        )
        policy = client.network_policies.update(
            VALID_UUID, name="renamed", is_active=False
        )
        assert policy.name == "renamed"
        assert policy.is_active is False
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"name": "renamed", "is_active": False}

    def test_delete(self, client, mock_api):
        mock_api.delete(f"{NP_BASE}/{VALID_UUID}").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        result = client.network_policies.delete(VALID_UUID)
        assert isinstance(result, SuccessResponse)
        assert result.success is True

    def test_update_all_optional_fields_and_project_id(self, client, mock_api):
        mock_api.patch(url__regex=rf"{NP_BASE}/{VALID_UUID}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "policy": make_network_policy_response(
                        name="n2", egress_mode="denylist", description="d"
                    )
                },
            )
        )
        mock_api.delete(url__regex=rf"{NP_BASE}/{VALID_UUID}").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        policy = client.network_policies.update(
            VALID_UUID,
            name="n2",
            egress_mode="denylist",
            description="d",
            is_active=True,
            is_default=False,
            project_id="proj-1",
        )
        assert policy.name == "n2"
        assert "project_id=proj-1" in str(mock_api.calls[-1].request.url)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["egress_mode"] == "denylist"
        assert body["description"] == "d"
        with pytest.raises(ValueError, match="egress_mode"):
            client.network_policies.update(VALID_UUID, egress_mode="nope")
        assert client.network_policies.delete(
            VALID_UUID, project_id="proj-1"
        ).success is True
        assert "project_id=proj-1" in str(mock_api.calls[-1].request.url)

    def test_create_with_description_and_project_id(self, client, mock_api):
        mock_api.post(url__regex=rf"{NP_BASE}").mock(
            return_value=httpx.Response(
                201, json={"policy": make_network_policy_response(rule_count=0)}
            )
        )
        policy = client.network_policies.create(
            name="openai-only",
            egress_mode="allowlist",
            description="Allow OpenAI",
            project_id="proj-1",
        )
        assert isinstance(policy, NetworkPolicy)
        assert "project_id=proj-1" in str(mock_api.calls[-1].request.url)
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["description"] == "Allow OpenAI"


class TestSyncNetworkPolicyRules:
    def test_add_rule(self, client, mock_api):
        mock_api.post(f"{NP_BASE}/{VALID_UUID}/rules").mock(
            return_value=httpx.Response(
                201, json={"rule": make_network_policy_rule_response()}
            )
        )
        rule = client.network_policies.add_rule(
            VALID_UUID, destination="api.openai.com", port=443, protocol="TCP"
        )
        assert isinstance(rule, NetworkPolicyRule)
        assert rule.port == 443
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["protocol"] == "tcp"

    def test_add_rule_rejects_bad_protocol(self, client, mock_api):
        with pytest.raises(ValueError, match="protocol"):
            client.network_policies.add_rule(
                VALID_UUID, destination="x.com", protocol="sctp"
            )

    def test_list_rules(self, client, mock_api):
        mock_api.get(f"{NP_BASE}/{VALID_UUID}/rules").mock(
            return_value=httpx.Response(
                200, json={"rules": [make_network_policy_rule_response()]}
            )
        )
        result = client.network_policies.list_rules(VALID_UUID)
        assert len(result.rules) == 1

    def test_update_rule(self, client, mock_api):
        mock_api.patch(url__regex=rf"{NP_BASE}/{VALID_UUID}/rules/{RULE_ID}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "rule": make_network_policy_rule_response(
                        destination="api.anthropic.com", port=443
                    )
                },
            )
        )
        rule = client.network_policies.update_rule(
            VALID_UUID,
            RULE_ID,
            destination="api.anthropic.com",
            port=443,
            protocol="TCP",
            description="anthropic",
            project_id="proj-1",
        )
        assert rule.destination == "api.anthropic.com"
        body = json.loads(mock_api.calls[-1].request.content)
        assert body["protocol"] == "tcp"
        assert body["description"] == "anthropic"
        assert "project_id=proj-1" in str(mock_api.calls[-1].request.url)

    def test_update_rule_rejects_bad_inputs(self, client, mock_api):
        with pytest.raises(ValueError, match="protocol"):
            client.network_policies.update_rule(VALID_UUID, RULE_ID, protocol="sctp")
        with pytest.raises(ValueError, match="port"):
            client.network_policies.update_rule(VALID_UUID, RULE_ID, port=-1)

    def test_add_rule_with_description_and_project_id(self, client, mock_api):
        mock_api.post(url__regex=rf"{NP_BASE}/{VALID_UUID}/rules").mock(
            return_value=httpx.Response(
                201,
                json={
                    "rule": make_network_policy_rule_response(description="openai")
                },
            )
        )
        rule = client.network_policies.add_rule(
            VALID_UUID,
            destination="api.openai.com",
            port=443,
            description="openai",
            project_id="proj-1",
        )
        assert rule.description == "openai"
        assert "project_id=proj-1" in str(mock_api.calls[-1].request.url)

    def test_add_rule_rejects_bad_port(self, client, mock_api):
        with pytest.raises(ValueError, match="port"):
            client.network_policies.add_rule(VALID_UUID, "x.com", port=70000)

    def test_delete_rule(self, client, mock_api):
        mock_api.delete(f"{NP_BASE}/{VALID_UUID}/rules/{RULE_ID}").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        result = client.network_policies.delete_rule(VALID_UUID, RULE_ID)
        assert result.success is True

    def test_delete_rule_with_project_id(self, client, mock_api):
        mock_api.delete(
            url__regex=rf"{NP_BASE}/{VALID_UUID}/rules/{RULE_ID}"
        ).mock(return_value=httpx.Response(200, json={"success": True}))
        result = client.network_policies.delete_rule(
            VALID_UUID, RULE_ID, project_id="proj-1"
        )
        assert result.success is True
        assert "project_id=proj-1" in str(mock_api.calls[-1].request.url)


class TestSyncNetworkPolicyAttachments:
    def test_attach(self, client, mock_api):
        mock_api.post(url__regex=rf"{NP_BASE}/{VALID_UUID}/attach").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        result = client.network_policies.attach(
            VALID_UUID, RUNTIME_ID, project_id="proj-1"
        )
        assert result.success is True
        body = json.loads(mock_api.calls[-1].request.content)
        assert body == {"runtime_id": RUNTIME_ID}
        assert "project_id=proj-1" in str(mock_api.calls[-1].request.url)

    def test_detach(self, client, mock_api):
        mock_api.delete(
            url__regex=rf"{NP_BASE}/{VALID_UUID}/attach/{RUNTIME_ID}"
        ).mock(return_value=httpx.Response(200, json={"success": True}))
        result = client.network_policies.detach(
            VALID_UUID, RUNTIME_ID, project_id="proj-1"
        )
        assert result.success is True
        assert "project_id=proj-1" in str(mock_api.calls[-1].request.url)

    def test_list_for_runtime_hides_system_default(self, client, mock_api):
        mock_api.get(f"{NP_BASE}/runtimes/{RUNTIME_ID}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "policies": [
                        make_network_policy_response(
                            id="sys-default",
                            name="System Default",
                            is_system=True,
                            is_default=True,
                            rule_count=0,
                        ),
                        make_network_policy_response(),
                    ]
                },
            )
        )
        result = client.network_policies.list_for_runtime(RUNTIME_ID)
        assert len(result.policies) == 1
        assert result.policies[0].name == "openai-only"
        assert result.total == 1

    def test_list_for_runtime_include_system(self, client, mock_api):
        mock_api.get(f"{NP_BASE}/runtimes/{RUNTIME_ID}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "policies": [
                        make_network_policy_response(
                            id="sys-default",
                            name="System Default",
                            is_system=True,
                            is_default=True,
                        ),
                        make_network_policy_response(),
                    ]
                },
            )
        )
        result = client.network_policies.list_for_runtime(
            RUNTIME_ID, include_system=True
        )
        assert len(result.policies) == 2
        assert result.policies[0].is_system_default is True


# ===================================================================
# Async Network Policies (smoke coverage of key paths)
# ===================================================================


class TestAsyncNetworkPolicies:
    @pytest.mark.asyncio
    async def test_create_attach_list_for_runtime(self, mock_api):
        mock_api.post(NP_BASE).mock(
            return_value=httpx.Response(
                201, json={"policy": make_network_policy_response(rule_count=0)}
            )
        )
        mock_api.post(f"{NP_BASE}/{VALID_UUID}/attach").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        mock_api.get(f"{NP_BASE}/runtimes/{RUNTIME_ID}").mock(
            return_value=httpx.Response(
                200, json={"policies": [make_network_policy_response()]}
            )
        )

        async with AsyncGravixLayer(
            api_key=TEST_API_KEY, base_url=TEST_BASE_URL
        ) as client:
            policy = await client.network_policies.create(name="openai-only")
            assert policy.id == VALID_UUID
            ok = await client.network_policies.attach(policy.id, RUNTIME_ID)
            assert ok.success is True
            attached = await client.network_policies.list_for_runtime(RUNTIME_ID)
            assert len(attached.policies) == 1

    @pytest.mark.asyncio
    async def test_create_with_rules(self, mock_api):
        mock_api.post(NP_BASE).mock(
            return_value=httpx.Response(
                201, json={"policy": make_network_policy_response(rule_count=0)}
            )
        )
        mock_api.post(f"{NP_BASE}/{VALID_UUID}/rules").mock(
            return_value=httpx.Response(
                201, json={"rule": make_network_policy_rule_response()}
            )
        )
        async with AsyncGravixLayer(
            api_key=TEST_API_KEY, base_url=TEST_BASE_URL
        ) as client:
            policy = await client.network_policies.create(
                name="openai-only",
                rules=[{"destination": "api.openai.com", "port": 443}],
            )
            assert policy.rules is not None
            assert len(policy.rules) == 1

    @pytest.mark.asyncio
    async def test_full_lifecycle_parity(self, mock_api):
        mock_api.post(NP_BASE).mock(
            return_value=httpx.Response(
                201, json={"policy": make_network_policy_response(rule_count=0)}
            )
        )
        mock_api.get(url__regex=rf"{NP_BASE}\?").mock(
            return_value=httpx.Response(
                200,
                json={"policies": [make_network_policy_response()], "total": 1},
            )
        )
        mock_api.get(f"{NP_BASE}/{VALID_UUID}").mock(
            return_value=httpx.Response(
                200, json={"policy": make_network_policy_response(rule_count=0)}
            )
        )
        mock_api.get(f"{NP_BASE}/{VALID_UUID}/rules").mock(
            return_value=httpx.Response(
                200, json={"rules": [make_network_policy_rule_response()]}
            )
        )
        mock_api.patch(f"{NP_BASE}/{VALID_UUID}").mock(
            return_value=httpx.Response(
                200, json={"policy": make_network_policy_response(name="renamed")}
            )
        )
        mock_api.post(f"{NP_BASE}/{VALID_UUID}/rules").mock(
            return_value=httpx.Response(
                201, json={"rule": make_network_policy_rule_response()}
            )
        )
        mock_api.patch(f"{NP_BASE}/{VALID_UUID}/rules/{RULE_ID}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "rule": make_network_policy_rule_response(
                        destination="api.anthropic.com"
                    )
                },
            )
        )
        mock_api.delete(f"{NP_BASE}/{VALID_UUID}/rules/{RULE_ID}").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        mock_api.post(f"{NP_BASE}/{VALID_UUID}/attach").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        mock_api.delete(f"{NP_BASE}/{VALID_UUID}/attach/{RUNTIME_ID}").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        mock_api.delete(f"{NP_BASE}/{VALID_UUID}").mock(
            return_value=httpx.Response(200, json={"success": True})
        )

        async with AsyncGravixLayer(
            api_key=TEST_API_KEY, base_url=TEST_BASE_URL
        ) as client:
            np = client.network_policies
            policy = await np.create(name="openai-only", egress_mode="allowlist")
            listed = await np.list(limit=10)
            assert listed.total == 1

            detail = await np.get(policy.id, include_rules=True)
            assert detail.rules is not None
            assert len(detail.rules) == 1

            updated = await np.update(policy.id, name="renamed")
            assert updated.name == "renamed"

            rule = await np.add_rule(
                policy.id, destination="api.openai.com", port=443
            )
            assert rule.port == 443

            rules = await np.list_rules(policy.id)
            assert len(rules.rules) == 1

            patched = await np.update_rule(
                policy.id, RULE_ID, destination="api.anthropic.com"
            )
            assert patched.destination == "api.anthropic.com"

            assert (await np.delete_rule(policy.id, RULE_ID)).success is True
            assert (await np.attach(policy.id, RUNTIME_ID)).success is True
            assert (await np.detach(policy.id, RUNTIME_ID)).success is True
            assert (await np.delete(policy.id)).success is True

    @pytest.mark.asyncio
    async def test_list_for_runtime_hides_system_default(self, mock_api):
        mock_api.get(f"{NP_BASE}/runtimes/{RUNTIME_ID}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "policies": [
                        make_network_policy_response(
                            id="sys-default",
                            name="System Default",
                            is_system=True,
                            is_default=True,
                        ),
                        make_network_policy_response(),
                    ]
                },
            )
        )
        async with AsyncGravixLayer(
            api_key=TEST_API_KEY, base_url=TEST_BASE_URL
        ) as client:
            result = await client.network_policies.list_for_runtime(RUNTIME_ID)
            assert len(result.policies) == 1
            assert result.policies[0].name == "openai-only"

    @pytest.mark.asyncio
    async def test_create_with_rules_rolls_back_on_rule_failure(self, mock_api):
        mock_api.post(NP_BASE).mock(
            return_value=httpx.Response(
                201, json={"policy": make_network_policy_response(rule_count=0)}
            )
        )
        mock_api.post(f"{NP_BASE}/{VALID_UUID}/rules").mock(
            return_value=httpx.Response(400, text="bad rule")
        )
        mock_api.delete(f"{NP_BASE}/{VALID_UUID}").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        async with AsyncGravixLayer(
            api_key=TEST_API_KEY, base_url=TEST_BASE_URL
        ) as client:
            with pytest.raises(RuntimeError, match="rolled back"):
                await client.network_policies.create(
                    name="openai-only",
                    egress_mode="allowlist",
                    rules=[{"destination": "api.openai.com", "port": 443}],
                )

    @pytest.mark.asyncio
    async def test_validation_and_optional_fields(self, mock_api):
        mock_api.patch(f"{NP_BASE}/{VALID_UUID}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "policy": make_network_policy_response(
                        name="n2", egress_mode="denylist"
                    )
                },
            )
        )
        mock_api.post(f"{NP_BASE}/{VALID_UUID}/rules").mock(
            return_value=httpx.Response(
                201,
                json={
                    "rule": make_network_policy_rule_response(description="d")
                },
            )
        )
        mock_api.patch(f"{NP_BASE}/{VALID_UUID}/rules/{RULE_ID}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "rule": make_network_policy_rule_response(
                        protocol="udp", port=53
                    )
                },
            )
        )
        mock_api.get(f"{NP_BASE}/runtimes/{RUNTIME_ID}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "policies": [
                        make_network_policy_response(
                            id="sys-default",
                            name="System Default",
                            is_system=True,
                            is_default=True,
                        ),
                        make_network_policy_response(),
                    ]
                },
            )
        )

        async with AsyncGravixLayer(
            api_key=TEST_API_KEY, base_url=TEST_BASE_URL
        ) as client:
            np = client.network_policies
            with pytest.raises(ValueError, match="limit"):
                await np.list(limit=0)
            with pytest.raises(ValueError, match="offset"):
                await np.list(offset=-1)
            with pytest.raises(ValueError, match="egress_mode"):
                await np.create(name="x", egress_mode="nope")
            with pytest.raises(ValueError, match="protocol"):
                await np.add_rule(VALID_UUID, "x.com", protocol="sctp")
            with pytest.raises(ValueError, match="port"):
                await np.add_rule(VALID_UUID, "x.com", port=70000)

            updated = await np.update(
                VALID_UUID,
                name="n2",
                egress_mode="denylist",
                description="d",
                is_active=True,
                is_default=False,
                project_id="proj-1",
            )
            assert updated.name == "n2"
            assert "project_id=proj-1" in str(mock_api.calls[-1].request.url)

            rule = await np.add_rule(
                VALID_UUID,
                "dns.google",
                port=53,
                protocol="UDP",
                description="d",
                project_id="proj-1",
            )
            assert rule.description == "d"

            patched = await np.update_rule(
                VALID_UUID,
                RULE_ID,
                destination="1.1.1.1",
                port=53,
                protocol="udp",
                description="dns",
                project_id="proj-1",
            )
            assert patched.protocol == "udp"

            with pytest.raises(ValueError, match="protocol"):
                await np.update_rule(VALID_UUID, RULE_ID, protocol="sctp")
            with pytest.raises(ValueError, match="port"):
                await np.update_rule(VALID_UUID, RULE_ID, port=-1)

            all_policies = await np.list_for_runtime(
                RUNTIME_ID, include_system=True
            )
            assert len(all_policies.policies) == 2
