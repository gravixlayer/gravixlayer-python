import argparse
import os
from gravixlayer import GravixLayer

def main():
    parser = argparse.ArgumentParser(
        description="GravixLayer CLI – OpenAI-Compatible Chat Completions"
    )
    parser.add_argument("--api-key", type=str, default=None, help="API key")
    parser.add_argument("--model", required=True, help="Model name (e.g., gemma3:12b)")
    parser.add_argument("--system", default=None, help="System prompt (optional)")
    parser.add_argument("--user", required=True, help="User prompt/message")
    parser.add_argument("--temperature", type=float, default=None, help="Temperature")
    parser.add_argument("--stream", action="store_true", help="Stream output (token-by-token)")
    
    args = parser.parse_args()

    client = GravixLayer(api_key=args.api_key or os.environ.get("GRAVIXLAYER_API_KEY"))

    messages = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": args.user})

    try:
        if args.stream:
            for chunk in client.chat.completions.create(
                model=args.model,
                messages=messages,
                temperature=args.temperature,
                stream=True
            ):
                print(chunk.choices[0].message.content, end="", flush=True)
            print()
        else:
            completion = client.chat.completions.create(
                model=args.model,
                messages=messages,
                temperature=args.temperature
            )
            print(completion.choices[0].message.content)
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
