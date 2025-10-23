from gravixlayer import GravixLayer

def test_code_execution():
    """Test simple code execution in sandbox"""
    client = GravixLayer()
    sandbox_id = None
    
    try:
        # Create sandbox
        sandbox = client.sandbox.sandboxes.create(
            provider="gravix", region="eu-west-1", template="python-base-v1"
        )
        sandbox_id = sandbox.sandbox_id
        
        # Run Python code
        result = client.sandbox.sandboxes.run_code(
            sandbox_id,
            code="""
print("Hello from sandbox!")
x = 2 + 2
print(f"2 + 2 = {x}")

numbers = [1, 2, 3, 4, 5]
total = sum(numbers)
print(f"Sum of {numbers} = {total}")
"""
        )
        
        print("✅ Code executed!")
        if result.logs and result.logs.get("stdout"):
            for line in result.logs["stdout"]:
                print(f"   {line}")
        
    finally:
        if sandbox_id:
            client.sandbox.sandboxes.kill(sandbox_id)

if __name__ == "__main__":
    test_code_execution()