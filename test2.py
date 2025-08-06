import asyncio
from gravixlayer.async_client import AsyncGravixLayer

async def main():
    client = AsyncGravixLayer()
    result = await client.chat.completions.create(
        model="gemma3:12b",
        messages=[{"role": "user", "content": "Say something cool!"}]
    )
    print("Async response:", result.choices[0].message.content)

asyncio.run(main())
