#!/usr/bin/env python3
"""
Basic GravixLayer Sandbox Test

A focused test to understand core sandbox functionality:
1. Sandbox creation and basic info
2. Simple code execution
3. Basic file operations
4. Cleanup

Run with: python test_sandbox_basics.py
"""

import os
import sys
import time

# Add the gravixlayer package to path
sys.path.insert(0, '.')

try:
    from gravixlayer import GravixLayer, Sandbox
    print("✅ GravixLayer imported successfully")
except ImportError as e:
    print(f"❌ Failed to import GravixLayer: {e}")
    sys.exit(1)


def test_basic_sandbox_functionality():
    """Test basic sandbox functionality step by step"""
    
    # Check API key
    api_key = os.environ.get("GRAVIXLAYER_API_KEY")
    if not api_key:
        print("❌ GRAVIXLAYER_API_KEY environment variable not set")
        print("Please set your API key: export GRAVIXLAYER_API_KEY='your_key_here'")
        return False
    
    print("🔧 API key found, initializing client...")
    
    try:
        # Initialize client
        client = GravixLayer(api_key=api_key)
        print("✅ Client initialized successfully")
        
        # Test 1: List available templates
        print("\n📋 Step 1: Checking available templates...")
        templates = client.sandbox.templates.list(limit=5)
        print(f"✅ Found {len(templates.templates)} templates:")
        for template in templates.templates:
            print(f"   🏷️  {template.name}: {template.description}")
        
        # Test 2: Create sandbox using class method
        print("\n🚀 Step 2: Creating sandbox...")
        sandbox = Sandbox.create(
            template="python-base-v1",
            provider="gravix", 
            region="eu-west-1",
            timeout=600
        )
        print(f"✅ Sandbox created: {sandbox.sandbox_id}")
        print(f"   Status: {sandbox.status}")
        print(f"   Template: {sandbox.template}")
        print(f"   Is alive: {sandbox.is_alive()}")
        
        # Test 3: Basic code execution
        print("\n🐍 Step 3: Testing code execution...")
        result = sandbox.run_code("""
print("Hello from GravixLayer sandbox!")
import sys
print(f"Python version: {sys.version}")
x = 2 + 2
print(f"2 + 2 = {x}")
""")
        
        print("✅ Code executed successfully:")
        for line in result.logs['stdout']:
            print(f"   📤 {line}")
        
        # Test 4: Command execution
        print("\n💻 Step 4: Testing command execution...")
        cmd_result = sandbox.run_command("echo", ["Hello from command line!"])
        print(f"✅ Command executed: {cmd_result.stdout.strip()}")
        
        # Test 5: File operations
        print("\n📁 Step 5: Testing file operations...")
        
        # Write a file
        test_content = "Hello World!\nThis is a test file from GravixLayer."
        sandbox.write_file("/home/user/test.txt", test_content)
        print("✅ File written successfully")
        
        # Read the file back
        read_content = sandbox.read_file("/home/user/test.txt")
        print(f"✅ File read successfully: {len(read_content)} characters")
        
        # List files
        files = sandbox.list_files("/home/user")
        print(f"✅ Files in /home/user: {files}")
        
        # Test 6: Get sandbox metrics
        print("\n📊 Step 6: Checking sandbox metrics...")
        metrics = client.sandbox.sandboxes.get_metrics(sandbox.sandbox_id)
        print(f"✅ Metrics retrieved:")
        print(f"   CPU Usage: {metrics.cpu_usage:.2f}%")
        print(f"   Memory: {metrics.memory_usage:.0f}/{metrics.memory_total:.0f} MB")
        
        # Test 7: Cleanup
        print("\n🧹 Step 7: Cleaning up...")
        sandbox.kill()
        print("✅ Sandbox terminated successfully")
        
        print("\n🎉 All basic tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_context_manager():
    """Test using sandbox with context manager"""
    print("\n🔄 Testing context manager usage...")
    
    try:
        with Sandbox.create(template="python-base-v1", timeout=300) as sandbox:
            print(f"✅ Context manager sandbox created: {sandbox.sandbox_id}")
            
            # Quick test
            result = sandbox.run_code("print('Context manager test successful!')")
            print(f"✅ Output: {result.logs['stdout'][0]}")
            
            # Sandbox will auto-cleanup when exiting context
        
        print("✅ Context manager test completed (auto-cleanup)")
        return True
        
    except Exception as e:
        print(f"❌ Context manager test failed: {e}")
        return False


def main():
    """Run basic sandbox tests"""
    print("🚀 GravixLayer Sandbox Basic Test Suite")
    print("="*50)
    
    # Test basic functionality
    basic_success = test_basic_sandbox_functionality()
    
    # Test context manager
    context_success = test_context_manager()
    
    if basic_success and context_success:
        print("\n🎉 All basic tests passed!")
        return True
    else:
        print("\n💥 Some tests failed!")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)