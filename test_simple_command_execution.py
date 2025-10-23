from gravixlayer import GravixLayer

def test_command_execution():
    """Test simple command execution in sandbox"""
    client = GravixLayer()
    sandbox_id = None
    
    try:
        # Create sandbox
        sandbox = client.sandbox.sandboxes.create(
            provider="gravix", region="eu-west-1"
        )
        sandbox_id = sandbox.sandbox_id
        
        # Run echo command
        result = client.sandbox.sandboxes.run_command(
            sandbox_id, command="echo", args=["Hello from command!"]
        )
        print(f"✅ Output: {result.stdout.strip()}")
        
        # Run ls command
        result = client.sandbox.sandboxes.run_command(
            sandbox_id, command="ls", args=["-la", "/home/user"]
        )
        print("✅ Directory listing:")
        print(result.stdout)
        
        # Run python command
        result = client.sandbox.sandboxes.run_command(
            sandbox_id, command="python", 
            args=["-c", "print('Hello from Python!')"]
        )
        print(f"✅ Python output: {result.stdout.strip()}")
        
    finally:
        if sandbox_id:
            client.sandbox.sandboxes.kill(sandbox_id)

if __name__ == "__main__":
    test_command_execution()