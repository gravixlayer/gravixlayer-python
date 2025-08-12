import os
import asyncio
from gravixlayer import AsyncGravixLayer

async def test_async_streaming_chat():
    client = AsyncGravixLayer(api_key=os.environ.get("GRAVIXLAYER_API_KEY"))

    try:

        stream = client.chat.completions.create(
            model="llama3.1:8b",
            messages=[{"role": "user", "content": "Tell me about Python"}],
            stream=True
        )
        
        print("Async streaming output:")
        async for chunk in stream:
            if not chunk.choices:
                continue
                
            choice = chunk.choices[0]
            content = None
            
            if choice.delta and choice.delta.content:
                content = choice.delta.content
            elif choice.message and choice.message.content:
                content = choice.message.content
            
            if content:
                print(content, end="", flush=True)
        print()
        
    except Exception as e:
        print(f"Error during async streaming: {e}")
        import traceback
        traceback.print_exc()

async def test_async_non_streaming():
    """Test non-streaming async completion"""
    client = AsyncGravixLayer(api_key=os.environ.get("GRAVIXLAYER_API_KEY"))

    try:
        # For non-streaming, we need to await the coroutine
        response = await client.chat.completions.create(
            model="llama3.1:8b",
            messages=[{"role": "user", "content": "What's 2+2?"}],
            stream=False
        )
        
        print("Async non-streaming response:")
        print(response.choices[0].message.content)
        
    except Exception as e:
        print(f"Error during async non-streaming: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=== Testing Async Streaming ===")
    asyncio.run(test_async_streaming_chat())
    
    print("\n=== Testing Async Non-Streaming ===")
    asyncio.run(test_async_non_streaming())