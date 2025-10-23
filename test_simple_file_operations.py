from gravixlayer import GravixLayer

def test_file_operations():
    """Test simple file read/write/delete operations"""
    client = GravixLayer()
    sandbox_id = None
    
    try:
        # Create sandbox
        sandbox = client.sandbox.sandboxes.create(
            provider="gravix", region="eu-west-1"
        )
        sandbox_id = sandbox.sandbox_id
        
        # Write file
        client.sandbox.sandboxes.write_file(
            sandbox_id,
            "/home/user/test.txt",
            "Hello World!\nThis is a test file."
        )
        print("✅ File written")
        
        # Read file
        content = client.sandbox.sandboxes.read_file(
            sandbox_id, "/home/user/test.txt"
        )
        print(f"✅ File read: {content.content}")
        
        # List files
        files = client.sandbox.sandboxes.list_files(sandbox_id, "/home/user")
        print(f"✅ Found {len(files.files)} items")
        
        # Delete file
        client.sandbox.sandboxes.delete_file(sandbox_id, "/home/user/test.txt")
        print("✅ File deleted")
        
    finally:
        if sandbox_id:
            client.sandbox.sandboxes.kill(sandbox_id)

if __name__ == "__main__":
    test_file_operations()