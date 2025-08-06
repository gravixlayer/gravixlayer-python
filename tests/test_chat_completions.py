import unittest
from unittest.mock import MagicMock
from gravixlayer.client import GravixLayer

class TestChatCompletions(unittest.TestCase):
    def setUp(self):
        self.client = GravixLayer(api_key="x")
        self.client._make_request = MagicMock()
        self.mock_response = MagicMock()
        self.mock_response.json.return_value = {
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "lorem-llama",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "Hello!"},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}
        }
        self.client._make_request.return_value = self.mock_response

    def test_completion_create(self):
        chat = self.client.chat.completions
        result = chat.create(model="lorem-llama", messages=[{"role": "user", "content": "Hi"}])
        self.assertEqual(result.choices[0].message.content, "Hello!")

    def test_optional_parameters(self):
        chat = self.client.chat.completions
        chat.create(
            model="abc", messages=[], temperature=0.5, top_p=0.7, max_tokens=10,
            frequency_penalty=0.2, presence_penalty=0.3
        )
        call = self.client._make_request.call_args
        data_sent = call.args[2]  # data is always the third positional argument
        assert data_sent["temperature"] == 0.5
        assert data_sent["top_p"] == 0.7
        assert data_sent["max_tokens"] == 10


    def test_streaming_response(self):
        # Stream mock: returns bytes like HTTP event-stream
        lines = [
            b'data: {"id":"chunk","choices":[{"message":{"role":"assistant","content":"Hey"},"index":0,"finish_reason":null}]}\n',
            b'data: [DONE]\n'
        ]
        mock_stream_response = MagicMock()
        mock_stream_response.iter_lines.return_value = lines
        self.client._make_request.return_value = mock_stream_response

        chat = self.client.chat.completions
        chunks = list(chat.create(model="x", messages=[], stream=True))
        self.assertEqual(chunks[0].choices[0].message.content, "Hey")
