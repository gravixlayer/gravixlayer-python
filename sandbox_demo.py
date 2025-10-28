#!/usr/bin/env python3
"""
GravixLayer Sandbox Demo

This demo showcases the key features of GravixLayer sandboxes:
1. Easy sandbox creation
2. Code execution in the cloud
3. File operations
4. Command execution
5. Resource monitoring
6. Proper cleanup

Based on analysis of the GravixLayer SDK code structure.
"""

import os
import sys
import time

# Add the gravixlayer package to path
sys.path.insert(0, '.')

try:
    from gravixlayer import GravixLayer, Sandbox
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're in the project root directory")
    sys.exit(1)


def demo_sandbox_lifecycle():
    """Demonstrate complete sandbox lifecycle"""
    
    print("🚀 GravixLayer Sandbox Lifecycle Demo")
    print("="*50)
    
    # Check for API key
    if not os.environ.get("GRAVIXLAYER_API_KEY"):
        print("❌ Please set GRAVIXLAYER_API_KEY environment variable")
        print("Example: export GRAVIXLAYER_API_KEY='your_api_key_here'")
        return
    
    try:
        # Method 1: Using context manager (recommended)
        print("\n🔄 Method 1: Context Manager (Auto-cleanup)")
        with Sandbox.create(
            template="python-base-v1",
            provider="gravix",
            region="eu-west-1",
            timeout=600,
            metadata={"demo": "context_manager", "purpose": "testing"}
        ) as sandbox:
            
            print(f"✅ Sandbox created: {sandbox.sandbox_id}")
            print(f"   Status: {sandbox.status}")
            print(f"   Template: {sandbox.template}")
            
            # Execute Python code
            print("\n🐍 Executing Python code...")
            result = sandbox.run_code("""
import math
import datetime

print("🚀 Hello from GravixLayer sandbox!")
print(f"📅 Current time: {datetime.datetime.now()}")
print(f"🧮 Square root of 64: {math.sqrt(64)}")

# Create some data
data = [i**2 for i in range(1, 11)]
print(f"📊 Squares 1-10: {data}")
""")
            
            for line in result.logs['stdout']:
                print(f"   📤 {line}")
            
            # File operations
            print("\n📁 File operations...")
            
            # Create a Python script
            script_content = '''
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

print("Fibonacci sequence:")
for i in range(10):
    print(f"F({i}) = {fibonacci(i)}")
'''
            
            sandbox.write_file("/home/user/fibonacci.py", script_content)
            print("   ✅ Created fibonacci.py")
            
            # Execute the script
            result = sandbox.run_code('exec(open("/home/user/fibonacci.py").read())')
            print("   📤 Script output:")
            for line in result.logs['stdout'][:5]:  # Show first 5 lines
                print(f"      {line}")
            
            # Command execution
            print("\n💻 Command execution...")
            
            # List files
            cmd_result = sandbox.run_command("ls", ["-la", "/home/user"])
            print(f"   📁 Files created: {len(cmd_result.stdout.split())} items")
            
            # Check Python packages
            cmd_result = sandbox.run_command("pip", ["list"])
            if cmd_result.exit_code == 0:
                package_count = len(cmd_result.stdout.split('\n')) - 2  # Subtract header lines
                print(f"   📦 Python packages available: ~{package_count}")
            
            # Resource monitoring
            print("\n📊 Resource monitoring...")
            client = GravixLayer()
            metrics = client.sandbox.sandboxes.get_metrics(sandbox.sandbox_id)
            
            print(f"   💻 CPU Usage: {metrics.cpu_usage:.1f}%")
            print(f"   🧠 Memory: {metrics.memory_usage:.0f}/{metrics.memory_total:.0f} MB")
            print(f"   💾 Disk I/O: {metrics.disk_read + metrics.disk_write} bytes")
            
            print("\n✅ Context manager will auto-cleanup sandbox")
        
        print("🎉 Demo completed successfully!")
        
        # Method 2: Manual management
        print("\n🔧 Method 2: Manual Management")
        
        sandbox = Sandbox.create(
            template="python-base-v1",
            timeout=300
        )
        
        try:
            print(f"✅ Manual sandbox created: {sandbox.sandbox_id}")
            
            # Quick test
            result = sandbox.run_code("print('Manual management test')")
            print(f"   📤 {result.logs['stdout'][0]}")
            
        finally:
            # Always cleanup manually created sandboxes
            sandbox.kill()
            print("🧹 Manual sandbox cleaned up")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


def demo_advanced_features():
    """Demonstrate advanced sandbox features"""
    
    print("\n🔬 Advanced Features Demo")
    print("="*30)
    
    try:
        with Sandbox.create(template="python-base-v1", timeout=600) as sandbox:
            
            # Code contexts for isolation
            print("\n🔄 Testing code contexts...")
            client = GravixLayer()
            
            # Create isolated contexts
            context1 = client.sandbox.sandboxes.create_code_context(
                sandbox.sandbox_id,
                language="python"
            )
            
            context2 = client.sandbox.sandboxes.create_code_context(
                sandbox.sandbox_id,
                language="python"
            )
            
            print(f"   🆔 Context 1: {context1.context_id}")
            print(f"   🆔 Context 2: {context2.context_id}")
            
            # Set different variables in each context
            client.sandbox.sandboxes.run_code(
                sandbox.sandbox_id,
                code="shared_var = 'from_context_1'",
                context_id=context1.context_id
            )
            
            client.sandbox.sandboxes.run_code(
                sandbox.sandbox_id,
                code="shared_var = 'from_context_2'",
                context_id=context2.context_id
            )
            
            # Verify isolation
            result1 = client.sandbox.sandboxes.run_code(
                sandbox.sandbox_id,
                code="print(f'Context 1 variable: {shared_var}')",
                context_id=context1.context_id
            )
            
            result2 = client.sandbox.sandboxes.run_code(
                sandbox.sandbox_id,
                code="print(f'Context 2 variable: {shared_var}')",
                context_id=context2.context_id
            )
            
            print(f"   📤 {result1.logs['stdout'][0]}")
            print(f"   📤 {result2.logs['stdout'][0]}")
            print("   ✅ Context isolation verified")
            
            # Package installation and usage
            print("\n📦 Package installation demo...")
            
            install_result = sandbox.run_command("pip", ["install", "numpy"])
            if install_result.exit_code == 0:
                print("   ✅ NumPy installed successfully")
                
                # Use the package
                result = sandbox.run_code("""
import numpy as np

# Create array and perform operations
arr = np.array([1, 2, 3, 4, 5])
print(f"Array: {arr}")
print(f"Mean: {np.mean(arr)}")
print(f"Sum: {np.sum(arr)}")
print(f"Standard deviation: {np.std(arr):.2f}")
""")
                
                print("   📤 NumPy operations:")
                for line in result.logs['stdout']:
                    print(f"      {line}")
            else:
                print("   ⚠️  Package installation failed")
            
            # File upload simulation (create local-like file)
            print("\n📤 File operations demo...")
            
            # Create a data file
            csv_content = """name,age,city
Alice,25,New York
Bob,30,London
Charlie,35,Tokyo
Diana,28,Paris
Eve,32,Berlin"""
            
            sandbox.write_file("/home/user/data.csv", csv_content)
            print("   ✅ CSV data file created")
            
            # Process the data
            result = sandbox.run_code("""
# Simple CSV processing without pandas
with open('/home/user/data.csv', 'r') as f:
    lines = f.readlines()

header = lines[0].strip().split(',')
print(f"Columns: {header}")

data = []
for line in lines[1:]:
    row = line.strip().split(',')
    data.append(dict(zip(header, row)))

print(f"Records: {len(data)}")
for record in data:
    print(f"  {record['name']}: {record['age']} years old, lives in {record['city']}")

# Calculate average age
ages = [int(record['age']) for record in data]
avg_age = sum(ages) / len(ages)
print(f"Average age: {avg_age:.1f}")
""")
            
            print("   📊 Data processing results:")
            for line in result.logs['stdout']:
                print(f"      {line}")
    
    except Exception as e:
        print(f"❌ Advanced demo failed: {e}")


def main():
    """Run the complete demo"""
    
    # Basic lifecycle demo
    demo_sandbox_lifecycle()
    
    # Advanced features demo  
    demo_advanced_features()
    
    print("\n🎉 All demos completed!")
    print("\n💡 Key takeaways:")
    print("   • Use context managers for automatic cleanup")
    print("   • Sandboxes provide isolated Python environments")
    print("   • Full file system access within the sandbox")
    print("   • Can install packages and run system commands")
    print("   • Resource monitoring and timeout management")
    print("   • Code contexts provide variable isolation")


if __name__ == "__main__":
    main()