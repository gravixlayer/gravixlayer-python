text
# GravixLayer Python SDK

A Python SDK for GravixLayer API that's fully compatible with OpenAI's interface.

## Installation

pip install gravixlayer

text

## Quick Start

import os
from gravixlayer import GravixLayer
Initialize client

client = GravixLayer(
api_key=os.environ.get("GRAVIXLAYER_API_KEY"),
)
Create completion

completion = client.chat.completions.create(
model="llama3.1:8b",
messages=[
{"role": "system", "content": "You are a helpful assistant."},
{"role": "user", "content": "What are the three most popular programming languages?"}
]
)

print(completion.choices.message.content)

text

## OpenAI Compatibility

You can use this SDK as a drop-in replacement for OpenAI:

from gravixlayer import OpenAI # This is an alias for GravixLayer

client = OpenAI(
base_url="https://api.gravixlayer.com/v1/inference",
api_key=os.environ.get("GRAVIXLAYER_API_KEY"),
)

text

## Features

- **OpenAI Compatible**: Drop-in replacement for OpenAI Python SDK
- **Streaming Support**: Real-time response streaming
- **Error Handling**: Automatic retries and proper error handling
- **Type Hints**: Full type support for better development experience
- **Environment Variables**: Automatic API key detection

## API Reference

### Chat Completions

completion = client.chat.completions.create(
model="llama3.1:8b",
messages=[...],
temperature=0.7,
max_tokens=150,
top_p=1.0,
frequency_penalty=0,
presence_penalty=0,
stop=None,
stream=False
)

text

### Streaming

stream = client.chat.completions.create(
model="llama3.1:8b",
messages=[...],
stream=True
)

for chunk in stream:
if chunk.choices.delta.content is not None:
print(chunk.choices.delta.content, end="")

text

## Environment Variables

- `GRAVIXLAYER_API_KEY`: Your GravixLayer API key

## License

MIT License