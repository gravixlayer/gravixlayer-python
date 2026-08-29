"""Error envelope formatting and exception mapping."""

from datetime import datetime, timedelta, timezone

from email.utils import format_datetime

from gravixlayer.types.exceptions import (
    GravixLayerAuthenticationError,
    GravixLayerBadRequestError,
    GravixLayerError,
    GravixLayerRateLimitError,
    GravixLayerServerError,
    error_code,
    error_from_response,
    format_error_message,
)


class TestFormatErrorMessage:
    def test_prefers_message_over_error(self):
        body = {
            "error": "Runtime quota exceeded",
            "code": "quota_exceeded",
            "message": "CPU quota exceeded. Reduce running runtimes or upgrade your tier.",
            "exceeded": ["vcpu"],
        }
        assert (
            format_error_message("{}", body)
            == "CPU quota exceeded. Reduce running runtimes or upgrade your tier."
        )

    def test_falls_back_to_error_string(self):
        assert format_error_message("", {"error": "Runtime not found", "code": "not_found"}) == (
            "Runtime not found"
        )

    def test_reads_nested_error_message(self):
        assert format_error_message("", {"error": {"message": "invalid template"}}) == (
            "invalid template"
        )

    def test_skips_blank_fields(self):
        assert format_error_message("plain text", {"error": "  ", "message": ""}) == "plain text"

    def test_empty_body_is_request_failed(self):
        assert format_error_message("", None) == "Request failed."
        assert format_error_message("   ", {}) == "Request failed."


class TestErrorCode:
    def test_reads_string_code(self):
        assert error_code({"code": "quota_exceeded"}) == "quota_exceeded"

    def test_ignores_non_string_code(self):
        assert error_code({"code": 7}) is None
        assert error_code(["quota_exceeded"]) is None
        assert error_code(None) is None


class TestErrorFromResponse:
    def test_quota_is_clean_bad_request(self):
        text = (
            '{"error":"Runtime quota exceeded","code":"quota_exceeded",'
            '"message":"CPU quota exceeded. Reduce running runtimes or upgrade your tier.",'
            '"exceeded":["vcpu"]}'
        )
        err = error_from_response(403, text)
        assert isinstance(err, GravixLayerBadRequestError)
        assert str(err) == "CPU quota exceeded. Reduce running runtimes or upgrade your tier."
        assert err.status == 403
        assert err.code == "quota_exceeded"
        assert err.body["exceeded"] == ["vcpu"]

    def test_wallet_is_bad_request(self):
        err = error_from_response(
            402,
            '{"error":"Insufficient wallet balance. Please top up your wallet.",'
            '"code":"resource_exhausted"}',
        )
        assert isinstance(err, GravixLayerBadRequestError)
        assert err.status == 402
        assert err.code == "resource_exhausted"
        assert "wallet" in str(err).lower()

    def test_not_found_uses_error_field(self):
        err = error_from_response(404, '{"error":"Runtime not found","code":"not_found"}')
        assert str(err) == "Runtime not found"
        assert err.code == "not_found"

    def test_rate_limit_class_and_retry_after(self):
        err = error_from_response(
            429,
            '{"error":"Rate limit exceeded. Retry after the window resets.","code":"rate_limited"}',
            {"Retry-After": "1"},
        )
        assert isinstance(err, GravixLayerRateLimitError)
        assert err.status == 429
        assert err.code == "rate_limited"
        assert err.retry_after_seconds == 1.0

    def test_retry_after_http_date(self):
        when = datetime.now(timezone.utc) + timedelta(seconds=8)
        err = error_from_response(429, "slow", {"Retry-After": format_datetime(when, usegmt=True)})
        assert err.retry_after_seconds is not None
        assert 6 <= err.retry_after_seconds <= 8

    def test_auth_never_echoes_body(self):
        err = error_from_response(401, '{"error":"key sk-secret-value is invalid"}')
        assert isinstance(err, GravixLayerAuthenticationError)
        assert str(err) == "Authentication failed."
        assert "sk-secret" not in str(err)

    def test_server_error(self):
        err = error_from_response(500, '{"error":"An internal error occurred.","code":"internal_error"}')
        assert isinstance(err, GravixLayerServerError)
        assert err.code == "internal_error"

    def test_plain_text_body(self):
        err = error_from_response(502, "upstream exploded")
        assert isinstance(err, GravixLayerServerError)
        assert str(err) == "upstream exploded"
        assert err.body == "upstream exploded"
        assert err.code is None

    def test_request_id_from_headers(self):
        err = error_from_response(500, "boom", {"X-Request-Id": "req-42"})
        assert err.request_id == "req-42"

    def test_plain_constructor_still_works(self):
        err = GravixLayerBadRequestError("permission denied")
        assert str(err) == "permission denied"
        assert err.status is None
        assert err.code is None

    def test_code_from_body_on_constructor(self):
        err = GravixLayerError("x", body={"code": "conflict"})
        assert err.code == "conflict"

    def test_unknown_status_is_base_class(self):
        err = error_from_response(399, "weird")
        assert type(err) is GravixLayerError
        assert str(err) == "weird"
