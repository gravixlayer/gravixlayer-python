import os
from dotenv import load_dotenv

load_dotenv()

from gravixlayer import GravixLayer

client = GravixLayer(
    api_key="kB8bkq8akxYJWazXIm9JAVfKPpzrA0gu0jCoFHB79gRHrSnhdbUZog",
)

print(f"Testing  SDK...")

try:
    completion = client.chat.completions.create(
        model="gemma3:12b",
        messages=[
            {"role": "system", "content": "You are a helpful and friendly assistant."},
            {"role": "user", "content": "What is the capital of France?"}
        ]
    )
    print("✅ Success!")
    print(f"Response: {completion.choices[0].message.content}")
except Exception as e:
    print(f"❌ Error: {e}")
