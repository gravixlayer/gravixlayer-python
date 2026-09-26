"""Unit tests for gravixlayer._request_utils."""

import pytest

import httpx

from gravixlayer._request_utils import (
    RETRYABLE_STATUS,
    SUCCESS_STATUS,
    JSON_HEADERS,
    MAX_RETRY_AFTER_SECS,
    ApiKeyAuth,
    aresponse_text,
    build_url,
    prepare_request_kwargs,
    next_retry_delay,
    can_retry,
    response_text,
    split_authorization,
    url_origin,
)


class TestConstants:
    def test_retryable_status(self):
        assert 502 in RETRYABLE_STATUS
        assert 503 in RETRYABLE_STATUS
        assert 504 in RETRYABLE_STATUS
        assert 200 not in RETRYABLE_STATUS
        assert 403 not in RETRYABLE_STATUS
        assert 429 not in RETRYABLE_STATUS

    def test_success_status(self):
        assert {200, 201, 202, 204, 207}.issubset(SUCCESS_STATUS)


class TestBuildUrl:
    def test_absolute_https_passthrough(self):
        url = build_url(
            "https://example.com/path",
            "v1/agents",
            {"v1/agents": "https://api/x/v1/agents"},
            "https://api/x",
        )
        assert url == "https://example.com/path"

    def test_absolute_http_passthrough(self):
        url = build_url(
            "http://localhost:8080/invoke",
            "",
            {},
            "https://api/x",
        )
        assert url == "http://localhost:8080/invoke"

    def test_relative_with_service(self):
        service_urls = {"v1/agents": "https://api.example.com/v1/agents"}
        url = build_url("runtime/abc", "v1/agents", service_urls, "https://api.example.com")
        assert url == "https://api.example.com/v1/agents/runtime/abc"

    def test_relative_strips_leading_slash(self):
        service_urls = {"v1/inference": "https://api.example.com/v1/inference"}
        url = build_url("/template/build", "v1/inference", service_urls, "https://api.example.com")
        assert url == "https://api.example.com/v1/inference/template/build"

    def test_unknown_service_uses_base(self):
        url = build_url("foo", "v1/unknown", {}, "https://api.example.com")
        assert url == "https://api.example.com/v1/unknown/foo"

    def test_empty_service_uses_base_url_only(self):
        url = build_url("extra", "", {}, "https://api.example.com")
        assert url == "https://api.example.com/extra"

    def test_empty_endpoint_returns_service_base(self):
        service_urls = {"v1/agents": "https://api.example.com/v1/agents"}
        url = build_url("", "v1/agents", service_urls, "https://api.example.com")
        assert url == "https://api.example.com/v1/agents"

    def test_query_only_endpoint_does_not_insert_path_slash(self):
        service_urls = {
            "v1/network-policies": "https://api.example.com/v1/network-policies"
        }
        url = build_url(
            "?limit=50&offset=0",
            "v1/network-policies",
            service_urls,
            "https://api.example.com",
        )
        assert url == "https://api.example.com/v1/network-policies?limit=50&offset=0"


class TestPrepareRequestKwargs:
    def test_json_body_sets_headers(self):
        kwargs: dict = {}
        prepare_request_kwargs({"a": 1}, kwargs)
        assert kwargs["json"] == {"a": 1}
        assert kwargs["headers"] == JSON_HEADERS

    def test_json_headers_mapping_is_immutable(self):
        with pytest.raises((TypeError, AttributeError)):
            JSON_HEADERS["Content-Type"] = "text/plain"  # type: ignore[index]

    def test_json_body_preserves_caller_headers(self):
        kwargs = {"headers": {"X-Request-Id": "abc"}}
        prepare_request_kwargs({"a": 1}, kwargs)
        assert kwargs["headers"]["X-Request-Id"] == "abc"
        assert kwargs["headers"]["Content-Type"] == "application/json"
        assert "X-Request-Id" not in JSON_HEADERS

    def test_none_data_omits_json_headers(self):
        kwargs: dict = {}
        prepare_request_kwargs(None, kwargs)
        assert "json" not in kwargs
        assert "headers" not in kwargs

    def test_files_with_data_puts_form_data(self):
        kwargs = {"files": [("f", ("a.txt", b"x", "text/plain"))]}
        prepare_request_kwargs({"metadata": "{}"}, kwargs)
        assert kwargs["data"] == {"metadata": "{}"}
        assert "json" not in kwargs
        assert "headers" not in kwargs


class TestNextRetryDelay:
    def test_retry_after_numeric_string(self):
        d = next_retry_delay(0, lambda: 0.0, retry_after="2.5")
        assert d == 2.5

    def test_retry_after_is_capped(self):
        d = next_retry_delay(0, lambda: 0.0, retry_after="99999")
        assert d == MAX_RETRY_AFTER_SECS

    def test_retry_after_negative_falls_back_to_exponential(self):
        d = next_retry_delay(1, lambda: 0.1, retry_after="-1")
        assert d == 2.1

    def test_retry_after_invalid_falls_back_to_exponential(self):
        d = next_retry_delay(2, lambda: 0.25, retry_after="not-a-number")
        assert d == (1 << 2) + 0.25

    def test_no_retry_after_uses_exponential_and_rand(self):
        d = next_retry_delay(1, lambda: 0.1, retry_after=None)
        assert d == 2.1


class TestCanRetry:
    def test_can_retry_when_under_cap(self):
        assert can_retry(0, 3) is True
        assert can_retry(2, 3) is True

    def test_cannot_retry_at_max(self):
        assert can_retry(3, 3) is False


class TestResponseText:
    def test_streaming_error_body_is_readable(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"code": "rate_limited", "error": "full"})

        with httpx.Client(transport=httpx.MockTransport(handler)) as http:
            response = http.send(http.build_request("GET", "https://api.test/stream"), stream=True)
            assert response.status_code == 429
            assert "rate_limited" in response_text(response)

    async def test_async_streaming_error_body_is_readable(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"code": "rate_limited", "error": "full"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            response = await http.send(http.build_request("GET", "https://api.test/stream"), stream=True)
            assert response.status_code == 429
            assert "rate_limited" in await aresponse_text(response)


class TestUrlOrigin:
    def test_case_and_default_port_normalize(self):
        assert url_origin(httpx.URL("HTTPS://API.Example.com:443/v1")) == url_origin(
            httpx.URL("https://api.example.com")
        )

    def test_scheme_and_port_distinguish_origins(self):
        api = url_origin(httpx.URL("https://api.example.com"))
        assert url_origin(httpx.URL("http://api.example.com")) != api
        assert url_origin(httpx.URL("https://api.example.com:8443")) != api


class TestSplitAuthorization:
    def test_api_key_becomes_a_bearer_credential(self):
        assert split_authorization("key", None) == ("Bearer key", {})

    def test_caller_authorization_replaces_the_api_key(self):
        authorization, rest = split_authorization("key", {"authorization": "Token t", "X-Tenant": "acme"})
        assert authorization == "Token t"
        assert rest == {"X-Tenant": "acme"}


API = "https://api.example.com"


def _sent_authorization(url, headers=None):
    """The ``Authorization`` header a client using ``ApiKeyAuth`` sends to ``url``."""
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("Authorization"))
        return httpx.Response(204)

    with httpx.Client(transport=httpx.MockTransport(handler), auth=ApiKeyAuth("Bearer key", API)) as http:
        http.get(url, headers=headers)
    return seen[0]


class TestApiKeyAuth:
    @pytest.mark.parametrize("url", [f"{API}/v1/agents/runtime", "https://API.example.com:443/v1"])
    def test_sends_the_credential_to_the_api(self, url):
        assert _sent_authorization(url) == "Bearer key"

    @pytest.mark.parametrize(
        "url",
        [
            "https://agent.example.com/invoke",
            "http://api.example.com/v1",
            "https://api.example.com:8443/v1",
            "https://api.example.com.attacker.test/v1",
        ],
    )
    def test_keeps_the_credential_off_other_origins(self, url):
        assert _sent_authorization(url) is None

    def test_a_request_header_wins_on_any_origin(self):
        assert _sent_authorization(f"{API}/v1", {"Authorization": "Bearer mine"}) == "Bearer mine"
        assert _sent_authorization("https://agent.example.com/invoke", {"Authorization": "Bearer agent"}) == (
            "Bearer agent"
        )

    async def test_async_client_scopes_the_credential(self):
        seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.headers.get("Authorization"))
            return httpx.Response(204)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), auth=ApiKeyAuth("Bearer key", API)
        ) as http:
            await http.get(f"{API}/v1")
            await http.get("https://agent.example.com/invoke")
        assert seen == ["Bearer key", None]
