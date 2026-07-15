"""
Network Policies resource for the asynchronous GravixLayer client.

Same endpoints as :mod:`gravixlayer.resources.network_policies`.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .._resource_utils import build_list_endpoint
from ..types.network_policies import (
    NetworkPolicy,
    NetworkPolicyList,
    NetworkPolicyRule,
    NetworkPolicyRuleList,
    SuccessResponse,
    _parse_policy,
    _parse_rule,
)


class AsyncNetworkPolicies:
    """Async network policies resource at ``client.network_policies``."""

    def __init__(self, client):
        self.client = client

    async def _make_network_policy_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        return await self.client._make_request(
            method, endpoint, data, _service="v1/network-policies", **kwargs
        )

    async def create(
        self,
        name: str,
        egress_mode: str = "allowlist",
        description: Optional[str] = None,
        is_default: bool = False,
        project_id: Optional[str] = None,
    ) -> NetworkPolicy:
        body: Dict[str, Any] = {
            "name": name,
            "egress_mode": egress_mode,
            "is_default": is_default,
        }
        if description is not None:
            body["description"] = description
        endpoint = ""
        if project_id:
            endpoint = f"?project_id={project_id}"
        response = await self._make_network_policy_request("POST", endpoint, body)
        return _parse_policy(response.json()["policy"])

    async def list(
        self,
        limit: int = 100,
        offset: int = 0,
        project_id: Optional[str] = None,
        search: Optional[str] = None,
    ) -> NetworkPolicyList:
        endpoint = build_list_endpoint(
            "",
            limit=limit,
            offset=offset,
            extra_params={"project_id": project_id, "search": search},
        )
        response = await self._make_network_policy_request("GET", endpoint)
        data = response.json()
        policies = [_parse_policy(p) for p in (data.get("policies") or [])]
        return NetworkPolicyList(policies=policies, total=int(data.get("total", 0)))

    async def get(self, policy_id: str) -> NetworkPolicy:
        response = await self._make_network_policy_request("GET", policy_id)
        return _parse_policy(response.json()["policy"])

    async def update(
        self,
        policy_id: str,
        name: Optional[str] = None,
        egress_mode: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_default: Optional[bool] = None,
        project_id: Optional[str] = None,
    ) -> NetworkPolicy:
        body: Dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if egress_mode is not None:
            body["egress_mode"] = egress_mode
        if description is not None:
            body["description"] = description
        if is_active is not None:
            body["is_active"] = is_active
        if is_default is not None:
            body["is_default"] = is_default
        endpoint = policy_id
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = await self._make_network_policy_request("PATCH", endpoint, body)
        return _parse_policy(response.json()["policy"])

    async def delete(
        self, policy_id: str, project_id: Optional[str] = None
    ) -> SuccessResponse:
        endpoint = policy_id
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = await self._make_network_policy_request("DELETE", endpoint)
        data = response.json()
        return SuccessResponse(success=bool(data.get("success", True)))

    async def add_rule(
        self,
        policy_id: str,
        destination: str,
        port: int = 0,
        protocol: str = "tcp",
        description: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> NetworkPolicyRule:
        body: Dict[str, Any] = {
            "destination": destination,
            "port": port,
            "protocol": protocol,
        }
        if description is not None:
            body["description"] = description
        endpoint = f"{policy_id}/rules"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = await self._make_network_policy_request("POST", endpoint, body)
        return _parse_rule(response.json()["rule"])

    async def list_rules(self, policy_id: str) -> NetworkPolicyRuleList:
        response = await self._make_network_policy_request(
            "GET", f"{policy_id}/rules"
        )
        data = response.json()
        return NetworkPolicyRuleList(
            rules=[_parse_rule(r) for r in (data.get("rules") or [])]
        )

    async def update_rule(
        self,
        policy_id: str,
        rule_id: str,
        destination: Optional[str] = None,
        port: Optional[int] = None,
        protocol: Optional[str] = None,
        description: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> NetworkPolicyRule:
        body: Dict[str, Any] = {}
        if destination is not None:
            body["destination"] = destination
        if port is not None:
            body["port"] = port
        if protocol is not None:
            body["protocol"] = protocol
        if description is not None:
            body["description"] = description
        endpoint = f"{policy_id}/rules/{rule_id}"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = await self._make_network_policy_request("PATCH", endpoint, body)
        return _parse_rule(response.json()["rule"])

    async def delete_rule(
        self,
        policy_id: str,
        rule_id: str,
        project_id: Optional[str] = None,
    ) -> SuccessResponse:
        endpoint = f"{policy_id}/rules/{rule_id}"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = await self._make_network_policy_request("DELETE", endpoint)
        data = response.json()
        return SuccessResponse(success=bool(data.get("success", True)))

    async def attach(
        self,
        policy_id: str,
        runtime_id: str,
        project_id: Optional[str] = None,
    ) -> SuccessResponse:
        endpoint = f"{policy_id}/attach"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = await self._make_network_policy_request(
            "POST", endpoint, {"runtime_id": runtime_id}
        )
        data = response.json()
        return SuccessResponse(success=bool(data.get("success", True)))

    async def detach(
        self,
        policy_id: str,
        runtime_id: str,
        project_id: Optional[str] = None,
    ) -> SuccessResponse:
        endpoint = f"{policy_id}/attach/{runtime_id}"
        if project_id:
            endpoint = f"{endpoint}?project_id={project_id}"
        response = await self._make_network_policy_request("DELETE", endpoint)
        data = response.json()
        return SuccessResponse(success=bool(data.get("success", True)))

    async def list_for_runtime(self, runtime_id: str) -> NetworkPolicyList:
        response = await self._make_network_policy_request(
            "GET", f"runtimes/{runtime_id}"
        )
        data = response.json()
        policies = [_parse_policy(p) for p in (data.get("policies") or [])]
        return NetworkPolicyList(policies=policies, total=len(policies))
