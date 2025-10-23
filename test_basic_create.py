"""
Test basic sandbox creation to debug the issue
"""

from gravixlayer import Sandbox

def test_basic_create():
    """Test basic sandbox creation"""
    print("🧪 Testing Basic Sandbox Creation")
    
    try:
        # Create sandbox
        sbx = Sandbox.create()
        print(f"✅ Created sandbox: {sbx.sandbox_id}")
        print(f"Status: {sbx.status}")
        
        # Check if alive
        print(f"Is alive: {sbx.is_alive()}")
        
        # Try to get info
        try:
            info = sbx._get_client().sandbox.sandboxes.get(sbx.sandbox_id)
            print(f"Info status: {info.status}")
        except Exception as e:
            print(f"❌ Error getting info: {e}")
        
        # Manual cleanup
        try:
            sbx.kill()
            print("✅ Sandbox killed")
        except Exception as e:
            print(f"❌ Error killing: {e}")
            
    except Exception as e:
        print(f"❌ Error creating sandbox: {e}")

if __name__ == "__main__":
    test_basic_create()