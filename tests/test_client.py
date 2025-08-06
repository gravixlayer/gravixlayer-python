import os
import unittest
from gravixlayer.client import GravixLayer

class TestGravixLayerClient(unittest.TestCase):
    def test_api_key_argument(self):
        client = GravixLayer(api_key="test-key")
        self.assertEqual(client.api_key, "test-key")
    
    def test_api_key_env(self):
        os.environ["GRAVIXLAYER_API_KEY"] = "env-key"
        client = GravixLayer()
        self.assertEqual(client.api_key, "env-key")
        del os.environ["GRAVIXLAYER_API_KEY"]

    def test_https_enforcement(self):
        with self.assertRaises(ValueError):
            GravixLayer(api_key="k", base_url="http://not-secure.com")
