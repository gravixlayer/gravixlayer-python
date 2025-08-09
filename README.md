# Gravix Layer API Python SDK

A Python SDK for the Gravix Layer API with a clean, modern interface.

***

## Installation

- Using pip:
  - pip install gravixlayer

***

## Quick Start

- Basic chat completion:

  - python
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

    print(completion.choices.message.content)

***

## Features

- Native Gravix Layer SDK
- Streaming support for real-time responses
- Async support with fully asynchronous client methods
- Robust error handling with retries and structured exceptions
- Full type hints for enhanced developer experience
- Environment variable detection for API keys

***

## API Reference

### Chat Completions

- Create a chat completion:

  - python
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
    print(completion.choices.message.content)

***

### Streaming

- Stream chat responses:

  - python
    stream = client.chat.completions.create(
        model="llama3.1:8b",
        messages=[
            {"role": "user", "content": "Tell me about the Eiffel Tower"}
        ],
        stream=True
    )

    for chunk in stream:
        if chunk.choices.delta.content is not None:
            print(chunk.choices.delta.content, end="")

***

### Async Usage

- Use the asynchronous client:

  - python
    import asyncio
    from gravixlayer import AsyncGravixLayer

    async def main():
        client = AsyncGravixLayer(api_key=os.environ.get("GRAVIXLAYER_API_KEY"))
        response = await client.chat.completions.create(
            model="llama3.1:8b",
            messages=[{"role": "user", "content": "What’s the capital of France?"}]
        )
        print(response.choices.message.content)

    asyncio.run(main())

***

### Text Completions

- Non-chat text completion:

  - python
    response = client.completions.create(
        model="llama3.1:8b",
        prompt="Write a Python function to calculate factorial.",
        max_tokens=100,
    )
    print(response.choices.text)

***

### Streaming Text Completions

- Stream non-chat completions:

  - python
    stream = client.completions.create(
        model="llama3.1:8b",
        prompt="Write a Python function to calculate factorial.",
        stream=True,
    )

    for chunk in stream:
        if chunk.choices.delta.content is not None:
            print(chunk.choices.delta.content, end="")

***

### Listing Models

- List available models:

  - python
    models = client.models.list()

    for model in models.data:
        print(model.id)

***

## Environment Variables

- GRAVIXLAYER_API_KEY — Your Gravix Layer API key

***

## Contributing

- Issues and pull requests are welcome. Please ensure code is formatted, typed, and tested where applicable.

***

## License

- MIT License
