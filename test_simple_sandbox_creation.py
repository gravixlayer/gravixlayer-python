import os
from gravixlayer import GravixLayer

def test_sandbox_creation():
    """Test simple sandbox creation and deletion"""
    print("🧪 Simple Sandbox Creation Test")
    
    client = GravixLayer()
    
    try:
        # Create sandbox
        print("Creating sandbox...")
        sandbox = client.sandbox.sandboxes.create(
            provider="gravix",
            region="eu-west-1",
            template="python-base-v1"
        )
        
        print(f"✅ Created: {sandbox.sandbox_id}")
        print(f"Status: {sandbox.status}")
        
        
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_sandbox_creation()