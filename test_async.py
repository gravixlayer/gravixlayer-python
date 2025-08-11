import os
import asyncio
from gravixlayer import AsyncGravixLayer

async def test_async_chat():
    client = AsyncGravixLayer(api_key=os.environ.get("GRAVIXLAYER_API_KEY"))
    response = await client.chat.completions.create(
        model="llama3.1:8b",
        messages=[{"role": "user", "content": "What's the capital of France?"}]
    )
    print("Async completion:")
    print(response.choices[0].message.content)

if __name__ == "__main__":
    asyncio.run(test_async_chat())
