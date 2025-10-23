"""
Simple Sandbox Usage Example - Clean API
"""

from gravixlayer import Sandbox

# Simple usage - just like you requested
sbx = Sandbox.create()  # By default the sandbox is alive for 5 minutes
execution = sbx.run_code("print('hello world')")  # Execute Python inside the sandbox
print(execution.logs)

# Clean up
sbx.kill()

print("\n" + "="*50)
print("More examples:")

# Context manager (recommended)
with Sandbox.create() as sandbox:
    # Execute code
    result = sandbox.run_code("""
import math
x = math.sqrt(16)
print(f"Square root of 16 = {x}")
    """)
    
    print("Output:", result.stdout.strip())
    
    # File operations
    sandbox.write_file("/home/user/test.py", "print('Hello from file!')")
    content = sandbox.read_file("/home/user/test.py")
    print("File content:", content)
    
    # Run commands
    cmd_result = sandbox.run_command("python", ["/home/user/test.py"])
    print("Command output:", cmd_result.stdout.strip())

print("✅ All done!")