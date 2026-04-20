"""Unit tests for gravixlayer._resource_utils."""

from gravixlayer._resource_utils import (
    normalize_runtime_api_payload,
    build_list_endpoint,
    parse_total_items,
    parse_paginated_items,
)


class TestNormalizeRuntimeApiPayload:
    def test_maps_id_to_runtime_id(self):
        data = {"id": "rid-1", "status": "running"}
        normalize_runtime_api_payload(data)
        assert data["runtime_id"] == "rid-1"

    def test_preserves_existing_runtime_id(self):
        data = {"id": "x", "runtime_id": "y", "status": "running"}
        normalize_runtime_api_payload(data)
        assert data["runtime_id"] == "y"

    def test_maps_compute_fields_and_tags(self):
        data = {
            "id": "u1",
            "status": "running",
            "compute_provider": "aws",
            "compute_region": "us-west-2",
            "tags": {"k": "v"},
        }
        normalize_runtime_api_payload(data)
        assert data["provider"] == "aws"
        assert data["region"] == "us-west-2"
        assert data["metadata"] == {"k": "v"}

    def test_no_op_when_already_sdk_shaped(self):
        data = {
            "runtime_id": "u1",
            "provider": "azure",
            "region": "eastus2",
            "metadata": {},
        }
        normalize_runtime_api_payload(data)
        assert data["runtime_id"] == "u1"


class TestBuildListEndpoint:
    def test_default_pagination(self):
        assert build_list_endpoint("runtime") == "runtime?limit=100&offset=0"

    def test_custom_limit_offset(self):
        assert build_list_endpoint("template", limit=10, offset=5) == "template?limit=10&offset=5"

    def test_extra_params_skip_none(self):
        ep = build_list_endpoint(
            "x",
            limit=2,
            offset=0,
            extra_params={"cloud": "aws", "skip": None},
        )
        assert "cloud=aws" in ep
        assert "skip" not in ep

    def test_none_limit_offset_omitted(self):
        ep = build_list_endpoint("items", limit=None, offset=None)
        assert ep == "items"


class TestParseTotalItems:
    def test_parses_items_and_total(self):
        def p(x):
            return int(x) * 2

        items, total = parse_total_items({"items": [1, 2], "total": 99}, "items", p)
        assert items == [2, 4]
        assert total == 99

    def test_default_total_is_len_when_missing(self):
        items, total = parse_total_items({"things": ["a"]}, "things", lambda x: x)
        assert items == ["a"]
        assert total == 1


class TestParsePaginatedItems:
    def test_defaults(self):
        items, limit, offset = parse_paginated_items(
            {"rows": [1, 2]},
            "rows",
            lambda x: x,
            default_limit=50,
            default_offset=0,
        )
        assert items == [1, 2]
        assert limit == 50
        assert offset == 0

    def test_explicit_limit_offset(self):
        items, limit, offset = parse_paginated_items(
            {"data": [], "limit": 5, "offset": 10},
            "data",
            lambda x: x,
            default_limit=100,
            default_offset=0,
        )
        assert items == []
        assert limit == 5
        assert offset == 10
