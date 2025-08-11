import os
from gravixlayer import GravixLayer

def test_streaming_chat():
    client = GravixLayer(api_key=os.environ.get("GRAVIXLAYER_API_KEY"))

    stream = client.chat.completions.create(
        model="llama3.1:8b",
        messages=[{"role": "user", "content": "Tell me about the Eiffel Tower"}],
        stream=True
    )
    print("Streaming output:")
    for chunk in stream:
        # Use message.content instead of delta.content
        content = chunk.choices[0].message.content
        if content:
            print(content, end="", flush=True)
    print()

if __name__ == "__main__":
    test_streaming_chat()
