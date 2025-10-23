"""
Test the simplified Sandbox API
"""

from gravixlayer import Sandbox

def test_simple_sandbox():
    """Test the simplified sandbox interface"""
    print("🧪 Testing Simple Sandbox API")
    
    # Method 1: Manual management (safer for testing)
    sbx = Sandbox.create()
    
    try:
        print(f"✅ Created sandbox: {sbx.sandbox_id}")
        
        # Execute Python code
        execution = sbx.run_code("print('Hello World!')")
        print(f"✅ Code executed successfully: {execution.success}")
        print(f"📝 Output: {execution.stdout.strip()}")
        print(f"📋 Logs: {execution.logs}")
        
        # Execute more complex code
        execution = sbx.run_code("""
x = 2 + 2
print(f"2 + 2 = {x}")

numbers = [1, 2, 3, 4, 5]
total = sum(numbers)
print(f"Sum of {numbers} = {total}")
""")
        
        print("✅ Complex code executed:")
        for line in execution.logs.get('stdout', []):
            if line.strip():
                print(f"   {line}")
        
    finally:
        sbx.kill()
        print("✅ Sandbox cleaned up")

def test_context_manager():
    """Test context manager interface"""
    print("\n🧪 Testing Context Manager")
    
    # Method 2: Using context manager
    with Sandbox.create() as sbx:
        print(f"✅ Created sandbox: {sbx.sandbox_id}")
        
        execution = sbx.run_code("print('Context manager test')")
        print(f"✅ Output: {execution.stdout.strip()}")
        
    print("✅ Sandbox automatically cleaned up")

if __name__ == "__main__":
    test_simple_sandbox()
    test_context_manager()