import unittest
from gravixlayer.client import GravixLayer
from gravixlayer.types.exceptions import (
    GravixLayerAuthenticationError, GravixLayerRateLimitError, GravixLayerServerError,
    GravixLayerBadRequestError, GravixLayerConnectionError
)

class TestExceptionHandling(unittest.TestCase):
    def setUp(self):
        self.client = GravixLayer(api_key="x")

    def test_auth_error(self):
        def fail_auth(*a, **k):
            raise GravixLayerAuthenticationError("bad key")
        self.client._make_request = fail_auth
        with self.assertRaises(GravixLayerAuthenticationError):
            self.client.chat.completions.create(model="x", messages=[])

    def test_rate_limit_error(self):
        def fail_limit(*a, **k):
            raise GravixLayerRateLimitError("Too many requests")
        self.client._make_request = fail_limit
        with self.assertRaises(GravixLayerRateLimitError):
            self.client.chat.completions.create(model="x", messages=[])
