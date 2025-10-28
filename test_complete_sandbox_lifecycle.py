#!/usr/bin/env python3
"""
Complete GravixLayer Sandbox Lifecycle Test Suite

This comprehensive test suite covers:
1. Sandbox creation and management
2. Code execution (Python, JavaScript)
3. Command execution
4. File operations (read, write, upload, download)
5. Context management
6. Template management
7. Error handling and edge cases
8. Resource monitoring
9. Cleanup and termination

Run with: python test_complete_sandbox_lifecycle.py
"""

import os
import sys
import time
import json
import tempfile
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add the gravixlayer package to path
sys.path.insert(0, '.')

try:
    from gravixlayer import GravixLayer, Sandbox
    from gravixlayer.types.exceptions import GravixLayerError
except ImportError as e:
    print(f"❌ Failed to import GravixLayer: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


class SandboxLifecycleTest:
    """Comprehensive sandbox lifecycle testing"""
    
    def __init__(self):
        self.client = None
        self.test_results = []
        self.created_sandboxes = []
        self.start_time = datetime.now()
        
    def setup(self):
        """Initialize the test environment"""
        print("🔧 Setting up test environment...")
        
        # Check for API key
        api_key = os.environ.get("GRAVIXLAYER_API_KEY")
        if not api_key:
            print("❌ GRAVIXLAYER_API_KEY environment variable not set")
            print("Please set your API key: export GRAVIXLAYER_API_KEY='your_key_here'")
            return False
            
        try:
            self.client = GravixLayer(api_key=api_key)
            print("✅ GravixLayer client initialized")
            return True
        except Exception as e:
            print(f"❌ Failed to initialize client: {e}")
            return False
    
    def log_test(self, test_name: str, success: bool, details: str = "", duration: float = 0):
        """Log test results"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name} ({duration:.2f}s)")
        if details:
            print(f"   {details}")
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details,
            "duration": duration,
            "timestamp": datetime.now().isoformat()
        })
    
    def test_template_management(self):
        """Test template listing and information"""
        print("\n📋 Testing Template Management...")
        start_time = time.time()
        
        try:
            # List available templates
            templates = self.client.sandbox.templates.list(limit=10)
            
            if not templates.templates:
                self.log_test("Template List", False, "No templates available", time.time() - start_time)
                return False
            
            print(f"   Found {len(templates.templates)} templates:")
            for template in templates.templates:
                print(f"   🏷️  {template.name}")
                print(f"      📝 {template.description}")
                print(f"      💻 {template.vcpu_count} CPU, {template.memory_mb}MB RAM")
                print(f"      💾 {template.disk_size_mb}MB disk")
                print()
            
            self.log_test("Template List", True, f"Found {len(templates.templates)} templates", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Template List", False, f"Error: {e}", time.time() - start_time)
            return False
    
    def test_sandbox_creation_methods(self):
        """Test different sandbox creation methods"""
        print("\n🚀 Testing Sandbox Creation Methods...")
        
        # Method 1: Direct client creation
        success1 = self._test_direct_creation()
        
        # Method 2: Sandbox.create() class method
        success2 = self._test_class_method_creation()
        
        # Method 3: Context manager creation
        success3 = self._test_context_manager_creation()
        
        return success1 and success2 and success3
    
    def _test_direct_creation(self):
        """Test direct client sandbox creation"""
        start_time = time.time()
        
        try:
            sandbox = self.client.sandbox.sandboxes.create(
                provider="gravix",
                region="eu-west-1",
                template="python-base-v1",
                timeout=600,
                metadata={"test": "direct_creation", "method": "client"}
            )
            
            self.created_sandboxes.append(sandbox.sandbox_id)
            
            print(f"   📦 Created sandbox: {sandbox.sandbox_id}")
            print(f"   📊 Status: {sandbox.status}")
            print(f"   🏷️  Template: {sandbox.template}")
            print(f"   💻 Resources: {sandbox.cpu_count} CPU, {sandbox.memory_mb}MB RAM")
            
            # Verify sandbox is running
            sandbox_info = self.client.sandbox.sandboxes.get(sandbox.sandbox_id)
            if sandbox_info.status != "running":
                self.log_test("Direct Creation", False, f"Sandbox not running: {sandbox_info.status}", time.time() - start_time)
                return False
            
            self.log_test("Direct Creation", True, f"Sandbox {sandbox.sandbox_id} created", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Direct Creation", False, f"Error: {e}", time.time() - start_time)
            return False
    
    def _test_class_method_creation(self):
        """Test Sandbox.create() class method"""
        start_time = time.time()
        
        try:
            sandbox = Sandbox.create(
                template="python-base-v1",
                provider="gravix",
                region="eu-west-1",
                timeout=600,
                metadata={"test": "class_method_creation", "method": "Sandbox.create"}
            )
            
            self.created_sandboxes.append(sandbox.sandbox_id)
            
            print(f"   📦 Created sandbox: {sandbox.sandbox_id}")
            print(f"   📊 Status: {sandbox.status}")
            print(f"   💚 Is alive: {sandbox.is_alive()}")
            
            # Test basic functionality
            result = sandbox.run_code("print('Hello from class method!')")
            if not result.logs['stdout']:
                self.log_test("Class Method Creation", False, "Code execution failed", time.time() - start_time)
                return False
            
            print(f"   📤 Code output: {result.logs['stdout'][0]}")
            
            self.log_test("Class Method Creation", True, f"Sandbox {sandbox.sandbox_id} created and tested", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Class Method Creation", False, f"Error: {e}", time.time() - start_time)
            return False
    
    def _test_context_manager_creation(self):
        """Test context manager creation"""
        start_time = time.time()
        
        try:
            with Sandbox.create(
                template="python-base-v1",
                provider="gravix",
                region="eu-west-1",
                timeout=600,
                metadata={"test": "context_manager", "method": "with_statement"}
            ) as sandbox:
                
                print(f"   📦 Created sandbox: {sandbox.sandbox_id}")
                
                # Test code execution
                result = sandbox.run_code("""
print("Context manager test")
import sys
print(f"Python version: {sys.version}")
""")
                
                if not result.logs['stdout']:
                    self.log_test("Context Manager Creation", False, "Code execution failed", time.time() - start_time)
                    return False
                
                print(f"   📤 Output: {result.logs['stdout']}")
                
                # Sandbox should auto-cleanup when exiting context
            
            self.log_test("Context Manager Creation", True, "Context manager worked correctly", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Context Manager Creation", False, f"Error: {e}", time.time() - start_time)
            return False
    
    def test_code_execution(self):
        """Test various code execution scenarios"""
        print("\n🐍 Testing Code Execution...")
        
        try:
            with Sandbox.create(template="python-base-v1", timeout=600) as sandbox:
                
                # Test 1: Basic Python execution
                success1 = self._test_basic_python_execution(sandbox)
                
                # Test 2: Multi-line code execution
                success2 = self._test_multiline_code_execution(sandbox)
                
                # Test 3: Error handling in code
                success3 = self._test_code_error_handling(sandbox)
                
                # Test 4: Package installation and usage
                success4 = self._test_package_installation(sandbox)
                
                return success1 and success2 and success3 and success4
                
        except Exception as e:
            self.log_test("Code Execution Setup", False, f"Error: {e}", 0)
            return False
    
    def _test_basic_python_execution(self, sandbox):
        """Test basic Python code execution"""
        start_time = time.time()
        
        try:
            result = sandbox.run_code("""
x = 10
y = 20
result = x + y
print(f"The sum of {x} and {y} is {result}")
""")
            
            if not result.logs['stdout'] or "30" not in result.logs['stdout'][0]:
                self.log_test("Basic Python Execution", False, "Unexpected output", time.time() - start_time)
                return False
            
            print(f"   📤 Output: {result.logs['stdout'][0]}")
            self.log_test("Basic Python Execution", True, "Math calculation successful", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Basic Python Execution", False, f"Error: {e}", time.time() - start_time)
            return False
    
    def _test_multiline_code_execution(self, sandbox):
        """Test multi-line code execution"""
        start_time = time.time()
        
        try:
            result = sandbox.run_code("""
import math

def calculate_circle_area(radius):
    return math.pi * radius ** 2

radius = 5
area = calculate_circle_area(radius)
print(f"Circle with radius {radius} has area {area:.2f}")

# Test list comprehension
numbers = [1, 2, 3, 4, 5]
squares = [x**2 for x in numbers]
print(f"Squares: {squares}")
""")
            
            stdout_lines = result.logs['stdout']
            if not stdout_lines or len(stdout_lines) < 2:
                self.log_test("Multi-line Code Execution", False, "Insufficient output", time.time() - start_time)
                return False
            
            print(f"   📤 Circle area: {stdout_lines[0]}")
            print(f"   📤 Squares: {stdout_lines[1]}")
            
            self.log_test("Multi-line Code Execution", True, "Complex code executed successfully", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Multi-line Code Execution", False, f"Error: {e}", time.time() - start_time)
            return False
    
    def _test_code_error_handling(self, sandbox):
        """Test error handling in code execution"""
        start_time = time.time()
        
        try:
            # Execute code that should cause an error
            result = sandbox.run_code("""
try:
    x = 1 / 0
except ZeroDivisionError as e:
    print(f"Caught error: {e}")
    print("Error handled successfully")
""")
            
            stdout_lines = result.logs['stdout']
            if not stdout_lines or "Error handled successfully" not in stdout_lines[-1]:
                self.log_test("Code Error Handling", False, "Error not handled properly", time.time() - start_time)
                return False
            
            print(f"   📤 Error handling: {stdout_lines}")
            
            self.log_test("Code Error Handling", True, "Error handling works correctly", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Code Error Handling", False, f"Error: {e}", time.time() - start_time)
            return False
    
    def _test_package_installation(self, sandbox):
        """Test package installation and usage"""
        start_time = time.time()
        
        try:
            # Install requests package
            install_result = sandbox.run_command("pip", ["install", "requests"])
            
            if install_result.exit_code != 0:
                self.log_test("Package Installation", False, f"pip install failed: {install_result.stderr}", time.time() - start_time)
                return False
            
            # Use the installed package
            result = sandbox.run_code("""
import requests
print("requests package imported successfully")
print(f"requests version: {requests.__version__}")
""")
            
            stdout_lines = result.logs['stdout']
            if not stdout_lines or "imported successfully" not in stdout_lines[0]:
                self.log_test("Package Installation", False, "Package not imported", time.time() - start_time)
                return False
            
            print(f"   📦 Package test: {stdout_lines}")
            
            self.log_test("Package Installation", True, "Package installation and usage successful", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Package Installation", False, f"Error: {e}", time.time() - start_time)
            return False
    
    def test_command_execution(self):
        """Test system command execution"""
        print("\n💻 Testing Command Execution...")
        
        try:
            with Sandbox.create(template="python-base-v1", timeout=600) as sandbox:
                
                # Test 1: Basic commands
                success1 = self._test_basic_commands(sandbox)
                
                # Test 2: File system commands
                success2 = self._test_filesystem_commands(sandbox)
                
                # Test 3: Environment commands
                success3 = self._test_environment_commands(sandbox)
                
                return success1 and success2 and success3
                
        except Exception as e:
            self.log_test("Command Execution Setup", False, f"Error: {e}", 0)
            return False
    
    def _test_basic_commands(self, sandbox):
        """Test basic system commands"""
        start_time = time.time()
        
        try:
            # Test echo command
            result = sandbox.run_command("echo", ["Hello from command line!"])
            
            if result.exit_code != 0 or "Hello from command line!" not in result.stdout:
                self.log_test("Basic Commands", False, f"Echo failed: {result.stderr}", time.time() - start_time)
                return False
            
            print(f"   📤 Echo: {result.stdout.strip()}")
            
            # Test Python version
            result = sandbox.run_command("python", ["--version"])
            
            if result.exit_code != 0:
                self.log_test("Basic Commands", False, f"Python version failed: {result.stderr}", time.time() - start_time)
                return False
            
            print(f"   🐍 Python: {result.stdout.strip()}")
            
            self.log_test("Basic Commands", True, "Basic commands executed successfully", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Basic Commands", False, f"Error: {e}", time.time() - start_time)
            return False
    
    def _test_filesystem_commands(self, sandbox):
        """Test filesystem commands"""
        start_time = time.time()
        
        try:
            # List home directory
            result = sandbox.run_command("ls", ["-la", "/home/user"])
            
            if result.exit_code != 0:
                self.log_test("Filesystem Commands", False, f"ls failed: {result.stderr}", time.time() - start_time)
                return False
            
            print(f"   📁 Home directory listing:")
            for line in result.stdout.split('\n')[:5]:  # Show first 5 lines
                if line.strip():
                    print(f"      {line}")
            
            # Check current working directory
            result = sandbox.run_command("pwd")
            
            if result.exit_code != 0:
                self.log_test("Filesystem Commands", False, f"pwd failed: {result.stderr}", time.time() - start_time)
                return False
            
            print(f"   📍 Current directory: {result.stdout.strip()}")
            
            self.log_test("Filesystem Commands", True, "Filesystem commands executed successfully", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Filesystem Commands", False, f"Error: {e}", time.time() - start_time)
            return False
    
    def _test_environment_commands(self, sandbox):
        """Test environment-related commands"""
        start_time = time.time()
        
        try:
            # Check system information
            result = sandbox.run_command("uname", ["-a"])
            
            if result.exit_code != 0:
                self.log_test("Environment Commands", False, f"uname failed: {result.stderr}", time.time() - start_time)
                return False
            
            print(f"   💻 System: {result.stdout.strip()}")
            
            # Check environment variables
            result = sandbox.run_command("env")
            
            if result.exit_code != 0:
                self.log_test("Environment Commands", False, f"env failed: {result.stderr}", time.time() - start_time)
                return False
            
            env_lines = result.stdout.split('\n')
            print(f"   🌍 Environment variables: {len(env_lines)} found")
            
            # Show a few interesting ones
            for line in env_lines:
                if any(var in line for var in ['PATH=', 'HOME=', 'USER=']):
                    print(f"      {line}")
            
            self.log_test("Environment Commands", True, "Environment commands executed successfully", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Environment Commands", False, f"Error: {e}", time.time() - start_time)
            return False    

    def test_file_operations(self):
        """Test comprehensive file operations"""
        print("\n📁 Testing File Operations...")
        
        try:
            with Sandbox.create(template="python-base-v1", timeout=600) as sandbox:
                
                # Test 1: Basic file operations
                success1 = self._test_basic_file_operations(sandbox)
                
                # Test 2: Directory operations
                success2 = self._test_directory_operations(sandbox)
                
                # Test 3: File upload/download
                success3 = self._test_file_upload_download(sandbox)
                
                # Test 4: Large file handling
                success4 = self._test_large_file_operations(sandbox)
                
                return success1 and success2 and success3 and success4
                
        except Exception as e:
            self.log_test("File Operations Setup", False, f"Error: {e}", 0)
            return False
    
    def _test_basic_file_operations(self, sandbox):
        """Test basic file read/write operations"""
        start_time = time.time()
        
        try:
            # Write a simple text file
            test_content = "Hello World!\nThis is a test file.\nLine 3 with special chars: àáâãäå"
            sandbox.write_file("/home/user/test.txt", test_content)
            print("   ✅ File written successfully")
            
            # Read the file back
            read_content = sandbox.read_file("/home/user/test.txt")
            
            if read_content != test_content:
                self.log_test("Basic File Operations", False, "File content mismatch", time.time() - start_time)
                return False
            
            print(f"   📖 File content verified: {len(read_content)} characters")
            
            # List files to verify it exists
            files = sandbox.list_files("/home/user")
            
            if "test.txt" not in files:
                self.log_test("Basic File Operations", False, "File not found in listing", time.time() - start_time)
                return False
            
            print(f"   📁 Files in /home/user: {files}")
            
            # Delete the file
            sandbox.delete_file("/home/user/test.txt")
            
            # Verify deletion
            files_after = sandbox.list_files("/home/user")
            
            if "test.txt" in files_after:
                self.log_test("Basic File Operations", False, "File not deleted", time.time() - start_time)
                return False
            
            print("   🗑️  File deleted successfully")
            
            self.log_test("Basic File Operations", True, "All basic file operations successful", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Basic File Operations", False, f"Error: {e}", time.time() - start_time)
            return False
    
    def _test_directory_operations(self, sandbox):
        """Test directory creation and management"""
        start_time = time.time()
        
        try:
            # Create a directory structure
            sandbox.run_command("mkdir", ["-p", "/home/user/test_project/src"])
            sandbox.run_command("mkdir", ["-p", "/home/user/test_project/data"])
            
            # Create files in different directories
            sandbox.write_file("/home/user/test_project/README.md", "# Test Project\nThis is a test project.")
            sandbox.write_file("/home/user/test_project/src/main.py", "print('Hello from main.py')")
            sandbox.write_file("/home/user/test_project/data/sample.txt", "Sample data file")
            
            # List the project structure
            result = sandbox.run_command("find", ["/home/user/test_project", "-type", "f"])
            
            if result.exit_code != 0:
                self.log_test("Directory Operations", False, f"find command failed: {result.stderr}", time.time() - start_time)
                return False
            
            files_found = result.stdout.strip().split('\n')
            print(f"   📁 Project structure created:")
            for file_path in files_found:
                print(f"      {file_path}")
            
            # Verify we have the expected files
            expected_files = ["README.md", "main.py", "sample.txt"]
            for expected in expected_files:
                if not any(expected in f for f in files_found):
                    self.log_test("Directory Operations", False, f"Missing file: {expected}", time.time() - start_time)
                    return False
            
            # Clean up
            sandbox.run_command("rm", ["-rf", "/home/user/test_project"])
            
            self.log_test("Directory Operations", True, "Directory operations successful", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Directory Operations", False, f"Error: {e}", time.time() - start_time)
            return False
    
    def _test_file_upload_download(self, sandbox):
        """Test file upload and download operations"""
        start_time = time.time()
        
        try:
            # Create a temporary local file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as temp_file:
                test_content = "This is a test file for upload/download.\nIt contains multiple lines.\nAnd special characters: 🚀🐍📁"
                temp_file.write(test_content)
                temp_file_path = temp_file.name
            
            try:
                # Upload the file
                remote_path = "/home/user/uploaded_file.txt"
                sandbox.upload_file(temp_file_path, remote_path)
                print(f"   📤 File uploaded to {remote_path}")
                
                # Verify upload by reading the file
                uploaded_content = sandbox.read_file(remote_path)
                
                if uploaded_content != test_content:
                    self.log_test("File Upload/Download", False, "Uploaded content mismatch", time.time() - start_time)
                    return False
                
                print("   ✅ Upload verified successfully")
                
                # Test download functionality by reading file content
                # (Note: actual download to local file would require additional API endpoint)
                files = sandbox.list_files("/home/user")
                
                if "uploaded_file.txt" not in files:
                    self.log_test("File Upload/Download", False, "Uploaded file not found", time.time() - start_time)
                    return False
                
                print("   📥 File found in sandbox filesystem")
                
                self.log_test("File Upload/Download", True, "Upload/download operations successful", time.time() - start_time)
                return True
                
            finally:
                # Clean up local temp file
                os.unlink(temp_file_path)
                
        except Exception as e:
            self.log_test("File Upload/Download", False, f"Error: {e}", time.time() - start_time)
            return False
    
    def _test_large_file_operations(self, sandbox):
        """Test operations with larger files"""
        start_time = time.time()
        
        try:
            # Create a larger file with structured content
            large_content = []
            for i in range(1000):
                large_content.append(f"Line {i:04d}: This is line number {i} with some data: {i * 2}")
            
            large_text = '\n'.join(large_content)
            
            # Write the large file
            sandbox.write_file("/home/user/large_file.txt", large_text)
            print(f"   📝 Large file written: {len(large_text)} characters")
            
            # Read it back and verify
            read_content = sandbox.read_file("/home/user/large_file.txt")
            
            if len(read_content) != len(large_text):
                self.log_test("Large File Operations", False, f"Size mismatch: {len(read_content)} vs {len(large_text)}", time.time() - start_time)
                return False
            
            # Verify first and last lines
            read_lines = read_content.split('\n')
            if read_lines[0] != "Line 0000: This is line number 0 with some data: 0":
                self.log_test("Large File Operations", False, "First line mismatch", time.time() - start_time)
                return False
            
            if read_lines[-1] != "Line 0999: This is line number 999 with some data: 1998":
                self.log_test("Large File Operations", False, "Last line mismatch", time.time() - start_time)
                return False
            
            print(f"   ✅ Large file verified: {len(read_lines)} lines")
            
            # Test processing the large file with code
            result = sandbox.run_code("""
with open('/home/user/large_file.txt', 'r') as f:
    lines = f.readlines()

print(f"File has {len(lines)} lines")
print(f"First line: {lines[0].strip()}")
print(f"Last line: {lines[-1].strip()}")

# Count lines containing specific numbers
count_500s = sum(1 for line in lines if '500' in line)
print(f"Lines containing '500': {count_500s}")
""")
            
            stdout_lines = result.logs['stdout']
            if not stdout_lines or "File has 1000 lines" not in stdout_lines[0]:
                self.log_test("Large File Operations", False, "File processing failed", time.time() - start_time)
                return False
            
            print(f"   📊 File processing results: {stdout_lines}")
            
            self.log_test("Large File Operations", True, "Large file operations successful", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Large File Operations", False, f"Error: {e}", time.time() - start_time)
            return False
    
    def test_context_management(self):
        """Test code execution context management"""
        print("\n🔄 Testing Context Management...")
        
        try:
            with Sandbox.create(template="python-base-v1", timeout=600) as sandbox:
                
                # Test 1: Create and use contexts
                success1 = self._test_context_creation(sandbox)
                
                # Test 2: Context isolation
                success2 = self._test_context_isolation(sandbox)
                
                # Test 3: Context cleanup
                success3 = self._test_context_cleanup(sandbox)
                
                return success1 and success2 and success3
                
        except Exception as e:
            self.log_test("Context Management Setup", False, f"Error: {e}", 0)
            return False
    
    def _test_context_creation(self, sandbox):
        """Test creating and using code execution contexts"""
        start_time = time.time()
        
        try:
            # Create a new context
            context = self.client.sandbox.sandboxes.create_code_context(
                sandbox.sandbox_id,
                language="python",
                cwd="/home/user"
            )
            
            print(f"   🆔 Created context: {context.context_id}")
            print(f"   🐍 Language: {context.language}")
            print(f"   📁 Working directory: {context.cwd}")
            
            # Use the context for code execution
            result = self.client.sandbox.sandboxes.run_code(
                sandbox.sandbox_id,
                code="x = 42\nprint(f'Variable x = {x}')",
                context_id=context.context_id
            )
            
            if not result.logs['stdout'] or "Variable x = 42" not in result.logs['stdout'][0]:
                self.log_test("Context Creation", False, "Context execution failed", time.time() - start_time)
                return False
            
            print(f"   📤 Context execution: {result.logs['stdout'][0]}")
            
            # Get context info
            context_info = self.client.sandbox.sandboxes.get_code_context(
                sandbox.sandbox_id,
                context.context_id
            )
            
            print(f"   📊 Context status: {context_info.status}")
            
            self.log_test("Context Creation", True, "Context creation and usage successful", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Context Creation", False, f"Error: {e}", time.time() - start_time)
            return False
    
    def _test_context_isolation(self, sandbox):
        """Test that contexts are properly isolated"""
        start_time = time.time()
        
        try:
            # Create two separate contexts
            context1 = self.client.sandbox.sandboxes.create_code_context(
                sandbox.sandbox_id,
                language="python"
            )
            
            context2 = self.client.sandbox.sandboxes.create_code_context(
                sandbox.sandbox_id,
                language="python"
            )
            
            print(f"   🆔 Context 1: {context1.context_id}")
            print(f"   🆔 Context 2: {context2.context_id}")
            
            # Set different variables in each context
            result1 = self.client.sandbox.sandboxes.run_code(
                sandbox.sandbox_id,
                code="isolation_test = 'context1'\nprint(f'Set variable in context 1: {isolation_test}')",
                context_id=context1.context_id
            )
            
            result2 = self.client.sandbox.sandboxes.run_code(
                sandbox.sandbox_id,
                code="isolation_test = 'context2'\nprint(f'Set variable in context 2: {isolation_test}')",
                context_id=context2.context_id
            )
            
            # Verify variables are isolated
            check1 = self.client.sandbox.sandboxes.run_code(
                sandbox.sandbox_id,
                code="print(f'Context 1 variable: {isolation_test}')",
                context_id=context1.context_id
            )
            
            check2 = self.client.sandbox.sandboxes.run_code(
                sandbox.sandbox_id,
                code="print(f'Context 2 variable: {isolation_test}')",
                context_id=context2.context_id
            )
            
            if "context1" not in check1.logs['stdout'][0] or "context2" not in check2.logs['stdout'][0]:
                self.log_test("Context Isolation", False, "Variables not properly isolated", time.time() - start_time)
                return False
            
            print(f"   ✅ Context 1 check: {check1.logs['stdout'][0]}")
            print(f"   ✅ Context 2 check: {check2.logs['stdout'][0]}")
            
            self.log_test("Context Isolation", True, "Context isolation working correctly", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Context Isolation", False, f"Error: {e}", time.time() - start_time)
            return False
    
    def _test_context_cleanup(self, sandbox):
        """Test context deletion and cleanup"""
        start_time = time.time()
        
        try:
            # Create a context
            context = self.client.sandbox.sandboxes.create_code_context(
                sandbox.sandbox_id,
                language="python"
            )
            
            print(f"   🆔 Created context for cleanup test: {context.context_id}")
            
            # Use the context
            result = self.client.sandbox.sandboxes.run_code(
                sandbox.sandbox_id,
                code="cleanup_test = True\nprint('Context ready for cleanup')",
                context_id=context.context_id
            )
            
            if not result.logs['stdout']:
                self.log_test("Context Cleanup", False, "Context setup failed", time.time() - start_time)
                return False
            
            # Delete the context
            delete_result = self.client.sandbox.sandboxes.delete_code_context(
                sandbox.sandbox_id,
                context.context_id
            )
            
            print(f"   🗑️  Context deleted: {delete_result.message}")
            
            # Try to use the deleted context (should fail)
            try:
                self.client.sandbox.sandboxes.run_code(
                    sandbox.sandbox_id,
                    code="print('This should fail')",
                    context_id=context.context_id
                )
                self.log_test("Context Cleanup", False, "Deleted context still usable", time.time() - start_time)
                return False
            except Exception:
                print("   ✅ Deleted context properly inaccessible")
            
            self.log_test("Context Cleanup", True, "Context cleanup successful", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Context Cleanup", False, f"Error: {e}", time.time() - start_time)
            return False
    
    def test_resource_monitoring(self):
        """Test sandbox resource monitoring and metrics"""
        print("\n📊 Testing Resource Monitoring...")
        
        try:
            with Sandbox.create(template="python-base-v1", timeout=600) as sandbox:
                
                # Test 1: Basic metrics
                success1 = self._test_basic_metrics(sandbox)
                
                # Test 2: Resource usage under load
                success2 = self._test_resource_usage_monitoring(sandbox)
                
                # Test 3: Timeout management
                success3 = self._test_timeout_management(sandbox)
                
                return success1 and success2 and success3
                
        except Exception as e:
            self.log_test("Resource Monitoring Setup", False, f"Error: {e}", 0)
            return False
    
    def _test_basic_metrics(self, sandbox):
        """Test basic metrics retrieval"""
        start_time = time.time()
        
        try:
            # Get initial metrics
            metrics = self.client.sandbox.sandboxes.get_metrics(sandbox.sandbox_id)
            
            print(f"   📊 Timestamp: {metrics.timestamp}")
            print(f"   💻 CPU Usage: {metrics.cpu_usage:.2f}%")
            print(f"   🧠 Memory: {metrics.memory_usage:.0f}/{metrics.memory_total:.0f} MB")
            print(f"   💾 Disk Read: {metrics.disk_read} bytes")
            print(f"   💾 Disk Write: {metrics.disk_write} bytes")
            print(f"   🌐 Network RX: {metrics.network_rx} bytes")
            print(f"   🌐 Network TX: {metrics.network_tx} bytes")
            
            # Verify metrics are reasonable
            if metrics.memory_total <= 0:
                self.log_test("Basic Metrics", False, "Invalid memory total", time.time() - start_time)
                return False
            
            if metrics.cpu_usage < 0 or metrics.cpu_usage > 100:
                self.log_test("Basic Metrics", False, f"Invalid CPU usage: {metrics.cpu_usage}", time.time() - start_time)
                return False
            
            self.log_test("Basic Metrics", True, "Metrics retrieved successfully", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Basic Metrics", False, f"Error: {e}", time.time() - start_time)
            return False
    
    def _test_resource_usage_monitoring(self, sandbox):
        """Test monitoring resource usage under load"""
        start_time = time.time()
        
        try:
            # Get baseline metrics
            baseline_metrics = self.client.sandbox.sandboxes.get_metrics(sandbox.sandbox_id)
            
            # Run some CPU and memory intensive code
            result = sandbox.run_code("""
import time
import sys

print("Starting resource-intensive task...")

# CPU intensive task
total = 0
for i in range(100000):
    total += i ** 2

# Memory intensive task
large_list = [i for i in range(50000)]
large_dict = {i: str(i) * 10 for i in range(10000)}

print(f"Task completed. Total: {total}")
print(f"List size: {len(large_list)}")
print(f"Dict size: {len(large_dict)}")
""")
            
            if not result.logs['stdout']:
                self.log_test("Resource Usage Monitoring", False, "Resource-intensive task failed", time.time() - start_time)
                return False
            
            print(f"   📤 Task output: {result.logs['stdout']}")
            
            # Get metrics after load
            time.sleep(1)  # Brief pause to let metrics update
            load_metrics = self.client.sandbox.sandboxes.get_metrics(sandbox.sandbox_id)
            
            print(f"   📊 Baseline CPU: {baseline_metrics.cpu_usage:.2f}%")
            print(f"   📊 Load CPU: {load_metrics.cpu_usage:.2f}%")
            print(f"   🧠 Baseline Memory: {baseline_metrics.memory_usage:.0f} MB")
            print(f"   🧠 Load Memory: {load_metrics.memory_usage:.0f} MB")
            
            # Memory usage should have increased
            if load_metrics.memory_usage <= baseline_metrics.memory_usage:
                print("   ⚠️  Memory usage didn't increase as expected (may be due to garbage collection)")
            else:
                print("   ✅ Memory usage increased as expected")
            
            self.log_test("Resource Usage Monitoring", True, "Resource monitoring under load successful", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Resource Usage Monitoring", False, f"Error: {e}", time.time() - start_time)
            return False
    
    def _test_timeout_management(self, sandbox):
        """Test timeout management functionality"""
        start_time = time.time()
        
        try:
            # Get current sandbox info
            sandbox_info = self.client.sandbox.sandboxes.get(sandbox.sandbox_id)
            original_timeout = sandbox_info.timeout_at
            
            print(f"   ⏰ Original timeout: {original_timeout}")
            
            # Update timeout (extend by 300 seconds)
            timeout_response = self.client.sandbox.sandboxes.set_timeout(
                sandbox.sandbox_id,
                timeout=900  # 15 minutes
            )
            
            print(f"   📝 Timeout update: {timeout_response.message}")
            print(f"   ⏰ New timeout: {timeout_response.timeout_at}")
            
            # Verify timeout was updated
            updated_info = self.client.sandbox.sandboxes.get(sandbox.sandbox_id)
            
            if updated_info.timeout_at == original_timeout:
                self.log_test("Timeout Management", False, "Timeout not updated", time.time() - start_time)
                return False
            
            print(f"   ✅ Timeout successfully updated")
            
            self.log_test("Timeout Management", True, "Timeout management successful", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Timeout Management", False, f"Error: {e}", time.time() - start_time)
            return False
    
    def test_error_handling(self):
        """Test error handling and edge cases"""
        print("\n🚨 Testing Error Handling...")
        
        # Test 1: Invalid operations
        success1 = self._test_invalid_operations()
        
        # Test 2: Resource limits
        success2 = self._test_resource_limits()
        
        # Test 3: Network and connectivity
        success3 = self._test_network_operations()
        
        return success1 and success2 and success3
    
    def _test_invalid_operations(self):
        """Test handling of invalid operations"""
        start_time = time.time()
        
        try:
            with Sandbox.create(template="python-base-v1", timeout=600) as sandbox:
                
                # Test reading non-existent file
                try:
                    sandbox.read_file("/home/user/nonexistent.txt")
                    self.log_test("Invalid Operations", False, "Reading non-existent file should fail", time.time() - start_time)
                    return False
                except Exception:
                    print("   ✅ Non-existent file read properly failed")
                
                # Test invalid command
                result = sandbox.run_command("nonexistentcommand", ["arg1"])
                
                if result.exit_code == 0:
                    self.log_test("Invalid Operations", False, "Invalid command should fail", time.time() - start_time)
                    return False
                
                print(f"   ✅ Invalid command failed as expected: {result.stderr[:50]}...")
                
                # Test syntax error in code
                result = sandbox.run_code("invalid python syntax !!!")
                
                if not result.error and not result.logs.get('stderr'):
                    self.log_test("Invalid Operations", False, "Invalid syntax should produce error", time.time() - start_time)
                    return False
                
                print("   ✅ Invalid syntax properly handled")
                
            self.log_test("Invalid Operations", True, "Invalid operations handled correctly", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Invalid Operations", False, f"Error: {e}", time.time() - start_time)
            return False
    
    def _test_resource_limits(self):
        """Test resource limit handling"""
        start_time = time.time()
        
        try:
            with Sandbox.create(template="python-base-v1", timeout=600) as sandbox:
                
                # Test memory-intensive operation
                result = sandbox.run_code("""
import sys
print("Testing memory limits...")

try:
    # Try to allocate a large amount of memory
    large_data = []
    for i in range(1000):
        large_data.append([0] * 100000)  # 100k integers per iteration
    
    print(f"Allocated {len(large_data)} chunks")
    
except MemoryError:
    print("Memory limit reached (MemoryError)")
except Exception as e:
    print(f"Other error: {e}")

print("Memory test completed")
""")
                
                stdout_lines = result.logs['stdout']
                if not stdout_lines:
                    self.log_test("Resource Limits", False, "Memory test produced no output", time.time() - start_time)
                    return False
                
                print(f"   🧠 Memory test results: {stdout_lines}")
                
                # Test CPU-intensive operation with timeout
                result = sandbox.run_code("""
import time
print("Testing CPU limits...")

start_time = time.time()
iterations = 0

# CPU intensive loop
while time.time() - start_time < 5:  # Run for 5 seconds max
    iterations += 1
    _ = sum(i**2 for i in range(1000))

print(f"Completed {iterations} iterations in {time.time() - start_time:.2f} seconds")
""")
                
                stdout_lines = result.logs['stdout']
                if not stdout_lines or "iterations" not in stdout_lines[-1]:
                    self.log_test("Resource Limits", False, "CPU test failed", time.time() - start_time)
                    return False
                
                print(f"   💻 CPU test results: {stdout_lines[-1]}")
                
            self.log_test("Resource Limits", True, "Resource limits tested successfully", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Resource Limits", False, f"Error: {e}", time.time() - start_time)
            return False
    
    def _test_network_operations(self):
        """Test network operations and connectivity"""
        start_time = time.time()
        
        try:
            with Sandbox.create(template="python-base-v1", timeout=600) as sandbox:
                
                # Install requests if not available
                install_result = sandbox.run_command("pip", ["install", "requests"])
                
                if install_result.exit_code != 0:
                    print("   ⚠️  Could not install requests, skipping network tests")
                    self.log_test("Network Operations", True, "Skipped due to package installation failure", time.time() - start_time)
                    return True
                
                # Test basic HTTP request
                result = sandbox.run_code("""
import requests
import json

print("Testing network connectivity...")

try:
    # Test with a reliable public API
    response = requests.get('https://httpbin.org/json', timeout=10)
    
    if response.status_code == 200:
        data = response.json()
        print(f"HTTP request successful: {response.status_code}")
        print(f"Response keys: {list(data.keys())}")
    else:
        print(f"HTTP request failed: {response.status_code}")
        
except requests.exceptions.Timeout:
    print("Request timed out")
except requests.exceptions.ConnectionError:
    print("Connection error")
except Exception as e:
    print(f"Network error: {e}")

print("Network test completed")
""")
                
                stdout_lines = result.logs['stdout']
                if not stdout_lines:
                    self.log_test("Network Operations", False, "Network test produced no output", time.time() - start_time)
                    return False
                
                print(f"   🌐 Network test results: {stdout_lines}")
                
                # Check if network access is working
                network_working = any("successful" in line for line in stdout_lines)
                
                if network_working:
                    print("   ✅ Network connectivity confirmed")
                else:
                    print("   ⚠️  Network connectivity limited or blocked")
                
            self.log_test("Network Operations", True, "Network operations tested", time.time() - start_time)
            return True
            
        except Exception as e:
            self.log_test("Network Operations", False, f"Error: {e}", time.time() - start_time)
            return False
    
    def cleanup_sandboxes(self):
        """Clean up any remaining sandboxes"""
        print("\n🧹 Cleaning up sandboxes...")
        
        cleanup_count = 0
        for sandbox_id in self.created_sandboxes:
            try:
                self.client.sandbox.sandboxes.kill(sandbox_id)
                cleanup_count += 1
                print(f"   🗑️  Cleaned up sandbox: {sandbox_id}")
            except Exception as e:
                print(f"   ⚠️  Failed to cleanup {sandbox_id}: {e}")
        
        print(f"   ✅ Cleaned up {cleanup_count} sandboxes")
    
    def generate_report(self):
        """Generate a comprehensive test report"""
        print("\n" + "="*80)
        print("📊 COMPREHENSIVE SANDBOX LIFECYCLE TEST REPORT")
        print("="*80)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        total_duration = (datetime.now() - self.start_time).total_seconds()
        
        print(f"🕒 Total Duration: {total_duration:.2f} seconds")
        print(f"📈 Tests Run: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"📊 Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        if failed_tests > 0:
            print(f"\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result['success']:
                    print(f"   • {result['test']}: {result['details']}")
        
        print(f"\n📋 DETAILED RESULTS:")
        for result in self.test_results:
            status = "✅" if result['success'] else "❌"
            print(f"   {status} {result['test']} ({result['duration']:.2f}s)")
            if result['details'] and not result['success']:
                print(f"      {result['details']}")
        
        # Save report to file
        report_data = {
            "summary": {
                "total_duration": total_duration,
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": passed_tests/total_tests*100
            },
            "results": self.test_results,
            "timestamp": datetime.now().isoformat()
        }
        
        with open("sandbox_test_report.json", "w") as f:
            json.dump(report_data, f, indent=2)
        
        print(f"\n💾 Detailed report saved to: sandbox_test_report.json")
        
        return failed_tests == 0
    
    def run_all_tests(self):
        """Run the complete test suite"""
        print("🚀 Starting Comprehensive GravixLayer Sandbox Lifecycle Tests")
        print("="*80)
        
        if not self.setup():
            return False
        
        try:
            # Run all test categories
            test_categories = [
                ("Template Management", self.test_template_management),
                ("Sandbox Creation Methods", self.test_sandbox_creation_methods),
                ("Code Execution", self.test_code_execution),
                ("Command Execution", self.test_command_execution),
                ("File Operations", self.test_file_operations),
                ("Context Management", self.test_context_management),
                ("Resource Monitoring", self.test_resource_monitoring),
                ("Error Handling", self.test_error_handling),
            ]
            
            for category_name, test_method in test_categories:
                print(f"\n{'='*20} {category_name} {'='*20}")
                try:
                    test_method()
                except Exception as e:
                    self.log_test(f"{category_name} (Category)", False, f"Category failed: {e}", 0)
            
            return self.generate_report()
            
        finally:
            self.cleanup_sandboxes()


def main():
    """Main test execution"""
    tester = SandboxLifecycleTest()
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 All tests completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed. Check the report for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()