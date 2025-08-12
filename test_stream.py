import os
from gravixlayer import GravixLayer

def test_streaming_chat():
    client = GravixLayer(api_key=os.environ.get("GRAVIXLAYER_API_KEY"))

    try:
        stream = client.chat.completions.create(
            model="gpt-oss:20b",
            messages=[{"role": "user", "content": "Tell me about Taj Mahal"}],
            stream=True
        )
        print("Streaming output:")
        for chunk in stream:
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
        print(f"Error during streaming: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_streaming_chat()
