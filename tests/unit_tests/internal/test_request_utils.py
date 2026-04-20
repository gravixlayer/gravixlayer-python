"""Unit tests for gravixlayer._request_utils."""

from gravixlayer._request_utils import (
    RETRYABLE_STATUS,
    SUCCESS_STATUS,
    JSON_HEADERS,
    build_url,
    prepare_request_kwargs,
    next_retry_delay,
    can_retry,
)


class TestConstants:
    def test_retryable_status(self):
        assert 502 in RETRYABLE_STATUS
        assert 200 not in RETRYABLE_STATUS

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


class TestPrepareRequestKwargs:
    def test_json_body_sets_headers(self):
        kwargs: dict = {}
        prepare_request_kwargs({"a": 1}, kwargs)
        assert kwargs["json"] == {"a": 1}
        assert kwargs["headers"] == JSON_HEADERS

    def test_none_data_only_headers(self):
        kwargs: dict = {}
        prepare_request_kwargs(None, kwargs)
        assert "json" not in kwargs
        assert kwargs["headers"] == JSON_HEADERS

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
