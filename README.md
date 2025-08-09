# Gravix Layer API Python SDK

A Python SDK for the GravixLayer API that's fully compatible with OpenAI's interface.

## Installation

```bash
pip install gravixlayer
```

## Quick Start

```python
import os
from gravixlayer import GravixLayer

# Initialize client
client = GravixLayer(
    api_key=os.environ.get("GRAVIXLAYER_API_KEY"),
)

# Create completion
completion = client.chat.completions.create(
    model="llama3.1:8b",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What are the three most popular programming languages?"}
    ]
)

print(completion.choices[0].message.content)
```

## API Reference

### Chat Completions

```python
completion = client.chat.completions.create(
    model="llama3.1:8b",
    messages=[
        {"role": "user", "content": "Tell me a fun fact about space"}
    ],
    temperature=0.7,
    max_tokens=150,
    top_p=1.0,
    frequency_penalty=0,
    presence_penalty=0,
    stop=None,
    stream=False
)

print(completion.choices[0].message.content)
```

### Streaming

```python
stream = client.chat.completions.create(
    model="llama3.1:8b",
    messages=[
        {"role": "user", "content": "Tell me about the Eiffel Tower"}
    ],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content is not None:
        print(chunk.choices[0].delta.content, end="")
```

### Async Usage

```python
import asyncio
from gravixlayer import AsyncGravixLayer

async def main():
    client = AsyncGravixLayer(api_key="your_api_key_here")
    
    response = await client.chat.completions.create(
        model="llama3.1:8b",
        messages=[{"role": "user", "content": "What's the capital of France?"}]
    )
    
    print(response.choices[0].message.content)

asyncio.run(main())
```

### Text Completions

```python
response = client.completions.create(
    model="llama3.1:8b",
    prompt="Write a Python function to calculate factorial.",
    max_tokens=100,
)

print(response.choices[0].text)
```

### Streaming Text Completions

```python
stream = client.completions.create(
    model="llama3.1:8b",
    prompt="Write a Python function to calculate factorial.",
    stream=True,
)

for chunk in stream:
    if chunk.choices[0].delta.content is not None:
        print(chunk.choices[0].delta.content, end="")
```

### Listing Models

```python
models = client.models.list()
for model in models.data:
    print(model.id)
```

## Environment Variables

- `GRAVIXLAYER_API_KEY` – Your GravixLayer API key

## License

MIT License
