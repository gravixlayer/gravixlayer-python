from gravixlayer import Sandbox

# Create sandbox - will automatically display creation info
sandbox = Sandbox.create(
    template="python-base-v1",
    timeout=600,
    metadata={"project": "my-app"}
)

# Run code
result = sandbox.run_code("import sys; print(sys.version)")
print(result.logs['stdout'][0])