import os
import tempfile
from gravixlayer import GravixLayer

def test_file_upload():
    """Test simple file upload to sandbox"""
    client = GravixLayer()
    
    # Create sandbox
    sandbox = client.sandbox.sandboxes.create(
        provider="gravix", region="eu-west-1"
    )
    sandbox_id = sandbox.sandbox_id
    
    # Create local file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("Hello from local file!")
        local_file = f.name
    
    # Upload file
    with open(local_file, 'rb') as f:
        result = client.sandbox.sandboxes.upload_file(
            sandbox_id, file=f, path="/home/user/uploaded.txt"
        )
    
    print(f"✅ Uploaded: {result.size} bytes")
    
    # Verify upload
    content = client.sandbox.sandboxes.read_file(
        sandbox_id, "/home/user/uploaded.txt"
    )
    print(f"✅ Content: {content.content}")

if __name__ == "__main__":
    test_file_upload()
