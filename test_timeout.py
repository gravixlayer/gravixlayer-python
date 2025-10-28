from gravixlayer import Sandbox

sandbox = Sandbox.create(
    template="python-base-v1",
    provider="gravix",
    region="eu-west-1",
    timeout=1800,
    metadata={"project": "my-app", "env": "production", "user_id": "user123"}
)

print(f"Created: {sandbox.sandbox_id}")
print(f"Template: {sandbox.template}")
print(f"Timeout: {sandbox.timeout}s")
print(f"Status: {sandbox.status}")

# Clean up
sandbox.kill()