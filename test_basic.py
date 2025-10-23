from gravixlayer import GravixLayer

client = GravixLayer()

# Create and use sandbox
sandbox = client.sandbox.sandboxes.create(
    provider="gravix",
    region="eu-west-1",
    template="python-base-v1"
)

# Run code
result = client.sandbox.sandboxes.run_code(
    sandbox.sandbox_id,
    "print('Hello from GravixLayer!')"
)

# Clean up
client.sandbox.sandboxes.kill(sandbox.sandbox_id)