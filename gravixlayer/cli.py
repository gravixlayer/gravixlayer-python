import argparse
import os
from gravixlayer import GravixLayer

def main():
    parser = argparse.ArgumentParser(
        description="GravixLayer CLI – OpenAI-Compatible Chat Completions and Text Completions"
    )
    parser.add_argument("--api-key", type=str, default=None, help="API key")
    parser.add_argument("--model", required=True, help="Model name (e.g., gemma3:12b)")
    parser.add_argument("--system", default=None, help="System prompt (optional, chat mode only)")
    parser.add_argument("--user", help="User prompt/message (chat mode)")
    parser.add_argument("--prompt", help="Direct prompt (completions mode)")
    parser.add_argument("--temperature", type=float, default=None, help="Temperature")
    parser.add_argument("--max-tokens", type=int, default=None, help="Maximum tokens to generate")
    parser.add_argument("--stream", action="store_true", help="Stream output (token-by-token)")
    parser.add_argument("--mode", choices=["chat", "completions"], default="chat", help="API mode to use")
    
    args = parser.parse_args()

    # Validate arguments
    if args.mode == "chat" and not args.user:
        parser.error("--user is required for chat mode")
    if args.mode == "completions" and not args.prompt:
        parser.error("--prompt is required for completions mode")

    client = GravixLayer(api_key=args.api_key or os.environ.get("GRAVIXLAYER_API_KEY"))

    try:
        if args.mode == "chat":
            # Chat completions mode
            messages = []
            if args.system:
                messages.append({"role": "system", "content": args.system})
            messages.append({"role": "user", "content": args.user})

            if args.stream:
                for chunk in client.chat.completions.create(
                    model=args.model,
                    messages=messages,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                    stream=True
                ):
                    if chunk.choices[0].delta.content:
                        print(chunk.choices[0].delta.content, end="", flush=True)
                print()
            else:
                completion = client.chat.completions.create(
                    model=args.model,
                    messages=messages,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens
                )
                print(completion.choices[0].message.content)
        
        else:
            # Text completions mode
            if args.stream:
                for chunk in client.completions.create(
                    model=args.model,
                    prompt=args.prompt,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                    stream=True
                ):
                    if chunk.choices[0].text:
                        print(chunk.choices[0].text, end="", flush=True)
                print()
            else:
                completion = client.completions.create(
                    model=args.model,
                    prompt=args.prompt,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens
                )
                print(completion.choices[0].text)
                
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
