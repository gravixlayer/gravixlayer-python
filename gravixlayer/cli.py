import argparse
import os
import json
from gravixlayer import GravixLayer


def parse_gpu_spec(gpu_type, gpu_count=1):
    """Parse GPU specification and return hardware string"""
    gpu_mapping = {
        "t4": "nvidia-t4-16gb-pcie_1",
        "t4": "nvidia-t4-16gb-pcie_2",
    }

    gpu_key = gpu_type.lower()
    if gpu_key not in gpu_mapping:
        raise ValueError(
            f"Unsupported GPU type: {gpu_type}. Supported: {list(gpu_mapping.keys())}")

    return f"{gpu_mapping[gpu_key]}_{gpu_count}"


def main():
    parser = argparse.ArgumentParser(
        description="GravixLayer CLI – Chat Completions, Text Completions, and Deployment Management"
    )

    # Create subparsers for different commands
    subparsers = parser.add_subparsers(
        dest="command", help="Available commands")

    # Chat/Completions parser (default behavior)
    chat_parser = subparsers.add_parser("chat", help="Chat completions")
    chat_parser.add_argument("--api-key", type=str,
                             default=None, help="API key")
    chat_parser.add_argument("--model", required=True, help="Model name")
    chat_parser.add_argument("--system", default=None,
                             help="System prompt (optional)")
    chat_parser.add_argument("--user", help="User prompt/message (chat mode)")
    chat_parser.add_argument(
        "--prompt", help="Direct prompt (completions mode)")
    chat_parser.add_argument("--temperature", type=float,
                             default=None, help="Temperature")
    chat_parser.add_argument("--max-tokens", type=int,
                             default=None, help="Maximum tokens to generate")
    chat_parser.add_argument(
        "--stream", action="store_true", help="Stream output")
    chat_parser.add_argument(
        "--mode", choices=["chat", "completions"], default="chat", help="API mode")

    # Deployments parser (for deployment management)
    deployments_parser = subparsers.add_parser(
        "deployments", help="Deployment management")
    deployments_subparsers = deployments_parser.add_subparsers(
        dest="deployments_action", help="Deployment actions")

    # Create deployment
    create_parser = deployments_subparsers.add_parser(
        "create", help="Create a new deployment")
    create_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    create_parser.add_argument(
        "--deployment_name", required=True, help="Deployment name")
    create_parser.add_argument(
        "--hw_type", default="dedicated", help="Hardware type (default: dedicated)")
    create_parser.add_argument("--gpu_model", required=True,
                               help="GPU model specification (e.g., NVIDIA_T4_16GB)")
    create_parser.add_argument(
        "--gpu_count", type=int, default=1, help="Number of GPUs (supported values: 1, 2, 4, 8)")
    create_parser.add_argument(
        "--min_replicas", type=int, default=1, help="Minimum replicas (default: 1)")
    create_parser.add_argument(
        "--max_replicas", type=int, default=1, help="Maximum replicas (default: 1)")
    create_parser.add_argument(
        "--model_name", required=True, help="Model name to deploy")
    create_parser.add_argument("--auto-retry", action="store_true", 
                               help="Auto-retry with unique name if deployment name exists")
    create_parser.add_argument("--wait", action="store_true",
                               help="Wait for deployment to be ready before exiting")

    # List deployments
    list_parser = deployments_subparsers.add_parser(
        "list", help="List all deployments")
    list_parser.add_argument("--api-key", type=str,
                             default=None, help="API key")
    list_parser.add_argument(
        "--json", action="store_true", help="Output as JSON")

    # Delete deployment
    delete_parser = deployments_subparsers.add_parser(
        "delete", help="Delete a deployment")
    delete_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    delete_parser.add_argument("deployment_id", help="Deployment ID to delete")

    # Hardware/GPU listing
    hardware_parser = deployments_subparsers.add_parser(
        "hardware", help="List available hardware/GPUs")
    hardware_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    hardware_parser.add_argument(
        "--list", action="store_true", help="List available hardware")
    hardware_parser.add_argument(
        "--json", action="store_true", help="Output as JSON")

    # GPU listing (alias for hardware)
    gpu_parser = deployments_subparsers.add_parser(
        "gpu", help="List available GPUs")
    gpu_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    gpu_parser.add_argument(
        "--list", action="store_true", help="List available GPUs")
    gpu_parser.add_argument(
        "--json", action="store_true", help="Output as JSON")

    # Files parser (for file management)
    files_parser = subparsers.add_parser(
        "files", help="File management")
    files_subparsers = files_parser.add_subparsers(
        dest="files_action", help="File actions")

    # Upload file
    upload_parser = files_subparsers.add_parser(
        "upload", help="Upload a file")
    upload_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    upload_parser.add_argument(
        "--file", required=True, help="Path to file to upload")
    upload_parser.add_argument(
        "--purpose", required=True, choices=["fine-tune", "assistants", "batch","vision","user_data","evals"], 
        help="Purpose of the file")
    upload_parser.add_argument(
        "--expires-after", type=int, help="File expiration time in seconds")

    # List files
    list_files_parser = files_subparsers.add_parser(
        "list", help="List all files")
    list_files_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    list_files_parser.add_argument(
        "--purpose", help="Filter by purpose")
    list_files_parser.add_argument(
        "--json", action="store_true", help="Output as JSON")

    # Get file info
    info_parser = files_subparsers.add_parser(
        "info", help="Get file information")
    info_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    info_parser.add_argument("file_id", help="File ID")
    info_parser.add_argument(
        "--json", action="store_true", help="Output as JSON")

    # Download file
    download_parser = files_subparsers.add_parser(
        "download", help="Download a file")
    download_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    download_parser.add_argument("file_id", help="File ID")
    download_parser.add_argument(
        "--output", help="Output file path (optional)")

    # Delete file
    delete_files_parser = files_subparsers.add_parser(
        "delete", help="Delete a file")
    delete_files_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    delete_files_parser.add_argument("file_id", help="File ID to delete")

    # For backward compatibility, if no subcommand is provided, treat as chat
    parser.add_argument("--api-key", type=str, default=None, help="API key")
    parser.add_argument("--model", help="Model name")
    parser.add_argument("--system", default=None,
                        help="System prompt (optional)")
    parser.add_argument("--user", help="User prompt/message")
    parser.add_argument("--prompt", help="Direct prompt")
    parser.add_argument("--temperature", type=float,
                        default=None, help="Temperature")
    parser.add_argument("--max-tokens", type=int, default=None,
                        help="Maximum tokens to generate")
    parser.add_argument("--stream", action="store_true", help="Stream output")
    parser.add_argument(
        "--mode", choices=["chat", "completions"], default="chat", help="API mode")

    args = parser.parse_args()

    # Handle different commands
    if args.command == "deployments":
        handle_deployments_commands(args)
    elif args.command == "files":
        handle_files_commands(args)
    elif args.command == "chat" or (args.command is None and args.model):
        handle_chat_commands(args, parser)
    else:
        parser.print_help()


def wait_for_deployment_ready(client, deployment_id, deployment_name):
    """Wait for deployment to be ready and show status updates"""
    import time
    
    print()
    print(f"⏳ Waiting for deployment '{deployment_name}' to be ready...")
    print("   Press Ctrl+C to stop monitoring (deployment will continue in background)")
    
    try:
        while True:
            try:
                deployments = client.deployments.list()
                current_deployment = None
                
                for dep in deployments:
                    if dep.deployment_id == deployment_id:
                        current_deployment = dep
                        break
                
                if current_deployment:
                    status = current_deployment.status.lower()
                    print(f"   Status: {current_deployment.status}")
                    
                    if status in ['running', 'ready', 'active']:
                        print()
                        print("🚀 Deployment is now ready!")
                        print(f"Deployment ID: {current_deployment.deployment_id}")
                        print(f"Deployment Name: {current_deployment.deployment_name}")
                        print(f"Status: {current_deployment.status}")
                        print(f"Model: {current_deployment.model_name}")
                        print(f"GPU Model: {current_deployment.gpu_model}")
                        print(f"GPU Count: {current_deployment.gpu_count}")
                        break
                    elif status in ['failed', 'error', 'stopped']:
                        print()
                        print(f"❌ Deployment failed with status: {current_deployment.status}")
                        break
                    else:
                        # Still creating/pending
                        time.sleep(10)  # Wait 10 seconds before checking again
                else:
                    print("   ❌ Deployment not found")
                    break
                    
            except Exception as e:
                print(f"   Error checking status: {e}")
                time.sleep(10)
                
    except KeyboardInterrupt:
        print()
        print("⏹️  Monitoring stopped. Deployment continues in background.")
        print(f"   Check status with: gravixlayer deployments list")


def handle_deployments_commands(args):
    """Handle deployment-related commands"""
    client = GravixLayer(
        api_key=args.api_key or os.environ.get("GRAVIXLAYER_API_KEY"))

    try:
        if args.deployments_action == "create":
            # Validate gpu_count
            if args.gpu_count not in [1, 2, 4, 8]:
                print(f"❌ Error: GPU count must be one of: 1, 2, 4, 8. You provided: {args.gpu_count}")
                print("Only these GPU counts are supported.")
                return
                
            print(f"Creating deployment '{args.deployment_name}' with model '{args.model_name}'...")

            # Generate unique name if auto-retry is enabled
            original_name = args.deployment_name
            if hasattr(args, 'auto_retry') and args.auto_retry:
                import random
                import string
                import time
                
                # Use timestamp + random for better uniqueness
                timestamp = str(int(time.time()))[-4:]  # Last 4 digits of timestamp
                suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
                args.deployment_name = f"{original_name}-{timestamp}{suffix}"
                print(f"Using unique name: '{args.deployment_name}'")

            try:
                response = client.deployments.create(
                    deployment_name=args.deployment_name,
                    model_name=args.model_name,
                    gpu_model=args.gpu_model,
                    gpu_count=args.gpu_count,
                    min_replicas=args.min_replicas,
                    max_replicas=args.max_replicas,
                    hw_type=args.hw_type
                )

                print("✅ Deployment created successfully!")
                print(f"Deployment ID: {response.deployment_id}")
                print(f"Deployment Name: {args.deployment_name}")
                print(f"Status: {response.status}")
                print(f"Model: {args.model_name}")
                print(f"GPU Model: {args.gpu_model}")
                print(f"GPU Count: {args.gpu_count}")
                print(f"Min Replicas: {args.min_replicas}")
                print(f"Max Replicas: {args.max_replicas}")
                
                # Wait for deployment to be ready if --wait flag is used
                if hasattr(args, 'wait') and args.wait:
                    wait_for_deployment_ready(client, response.deployment_id, args.deployment_name)
                else:
                    # Add status checking
                    if hasattr(response, 'status') and response.status:
                        if response.status.lower() in ['creating', 'pending']:
                            print()
                            print("💡 Tip: Use --wait flag to monitor deployment status automatically")
                            print("   Or check status with: gravixlayer deployments list")
                        elif response.status.lower() in ['running', 'ready']:
                            print("🚀 Deployment is ready to use!")
                        
            except Exception as create_error:
                # Parse the error message to provide better feedback
                error_str = str(create_error)
                
                # Try to parse JSON error response
                try:
                    import json
                    import time
                    if error_str.startswith('{"') and error_str.endswith('}'):
                        error_data = json.loads(error_str)
                        error_code = error_data.get('code', 'unknown')
                        error_message = error_data.get('error', error_str)
                        
                        # Check if deployment name already exists
                        if 'already exists' in error_message.lower():
                            # Check if the deployment was actually created
                            try:
                                existing_deployments = client.deployments.list()
                                deployment_created = False
                                created_deployment = None
                                
                                for dep in existing_deployments:
                                    if dep.deployment_name == args.deployment_name:
                                        deployment_created = True
                                        created_deployment = dep
                                        break

                                if deployment_created:
                                    # Deployment was actually created successfully!
                                    print(f"Deployment ID: {created_deployment.deployment_id}")
                                    print(f"Deployment Name: {created_deployment.deployment_name}")
                                    print(f"Status: {created_deployment.status}")
                                    print(f"Model: {created_deployment.model_name}")
                                    print(f"GPU Model: {created_deployment.gpu_model}")
                                    print(f"GPU Count: {created_deployment.gpu_count}")
                                    print(f"Min Replicas: {created_deployment.min_replicas}")
                                    print(f"Max Replicas: {getattr(created_deployment, 'max_replicas', 1) or 1}")
                                    print(f"Created: {created_deployment.created_at}")
                                    
                                    # Wait for deployment to be ready if --wait flag is used
                                    if hasattr(args, 'wait') and args.wait:
                                        wait_for_deployment_ready(client, created_deployment.deployment_id, created_deployment.deployment_name)
                                    else:
                                        if created_deployment.status.lower() in ['creating', 'pending']:
                                            print()
                                            print("💡 Tip: Use --wait flag to monitor deployment status automatically")
                                            print("   Or check status with: gravixlayer deployments list")
                                        elif created_deployment.status.lower() in ['running', 'ready']:
                                            print("🚀 Deployment is ready to use!")
                                    return  # Success, exit the function
                                else:
                                    # Check if it's a genuine duplicate with the original name
                                    genuine_duplicate = False
                                    for dep in existing_deployments:
                                        if dep.deployment_name == original_name:
                                            genuine_duplicate = True
                                            break
                                    
                                    if genuine_duplicate:
                                        print(f"❌ Deployment creation failed: deployment with name '{original_name}' already exists.")
                                        if hasattr(args, 'auto_retry') and args.auto_retry:
                                            print("Auto-retry was already attempted but failed.")
                                        else:
                                            print(f"Try with --auto-retry flag: gravixlayer deployments create --deployment_name \"{original_name}\" --gpu_model \"{args.gpu_model}\" --model_name \"{args.model_name}\" --auto-retry")
                                    else:
                                        print(f"⚠️  Deployment creation failed: {error_message}")
                                        print("This might be a temporary API issue. Please try again.")
                            except Exception as list_error:
                                print(f"❌ Deployment creation failed: {error_message}")
                                print(f"⚠️  Could not verify deployment status due to an error: {list_error}")
                        else:
                            print(f"❌ Deployment creation failed: {error_message}")
                    else:
                        print(f"❌ Deployment creation failed: {error_str}")
                except (json.JSONDecodeError, ValueError):
                    print(f"❌ Deployment creation failed: {error_str}")
                return

        elif args.deployments_action == "list":
            deployments = client.deployments.list()

            if args.json:
                print(json.dumps([d.model_dump()
                      for d in deployments], indent=2))
            else:
                if not deployments:
                    print("No deployments found.")
                else:
                    print(f"Found {len(deployments)} deployment(s):")
                    print()
                    for deployment in deployments:
                        print(f"Deployment ID: {deployment.deployment_id}")
                        print(f"Deployment Name: {deployment.deployment_name}")
                        print(f"Model: {deployment.model_name}")
                        print(f"Status: {deployment.status}")
                        print(f"GPU Model: {deployment.gpu_model}")
                        print(f"GPU Count: {deployment.gpu_count}")
                        print(f"Min Replicas: {deployment.min_replicas}")
                        print(f"Max Replicas: {deployment.max_replicas}")
                        print(f"Created: {deployment.created_at}")
                        print()

        elif args.deployments_action == "delete":
            print(f"Deleting deployment {args.deployment_id}...")
            response = client.deployments.delete(args.deployment_id)
            print("Deployment deleted successfully!")
            print(f"   Response: {response}")

        elif args.deployments_action in ["hardware", "gpu"]:
            if hasattr(args, 'list') and args.list:
                accelerators = client.accelerators.list()
                
                if hasattr(args, 'json') and getattr(args, 'json', False):
                    import json as json_module
                    # Filter out unwanted fields from JSON output
                    filtered_accelerators = []
                    for a in accelerators:
                        data = a.model_dump()
                        # Remove the specified fields
                        data.pop('name', None)
                        data.pop('memory', None)
                        data.pop('gpu_type', None)
                        data.pop('use_case', None)
                        filtered_accelerators.append(data)
                    print(json_module.dumps(filtered_accelerators, indent=2))
                else:
                    if not accelerators:
                        print("No accelerators/GPUs found.")
                    else:
                        print(f"Available {'Hardware' if args.deployments_action == 'hardware' else 'GPUs'} ({len(accelerators)} found):")
                        print()
                        print(f"{'Accelerator':<15} {'Hardware String':<35} {'Memory':<10}")
                        print("-" * 60)
                        
                        for accelerator in accelerators:
                            gpu_type = getattr(accelerator, 'gpu_type', accelerator.name)
                            hardware_string = accelerator.hardware_string
                            memory = getattr(accelerator, 'memory', 'N/A')
                            
                            print(f"{gpu_type:<15} {hardware_string:<35} {memory:<10}")
            else:
                print(f"Use --list flag to list available {'hardware' if args.deployments_action == 'hardware' else 'GPUs'}")
                print(f"Example: gravixlayer deployments {args.deployments_action} --list")

    except Exception as e:
        print(f"Error: {e}")


def handle_chat_commands(args, parser):
    """Handle chat and completion commands"""
    # Validate arguments
    if args.mode == "chat" and not args.user:
        parser.error("--user is required for chat mode")
    if args.mode == "completions" and not args.prompt:
        parser.error("--prompt is required for completions mode")

    client = GravixLayer(
        api_key=args.api_key or os.environ.get("GRAVIXLAYER_API_KEY"))

    try:
        if args.mode == "chat":
            # Chat completions mode
            messages = []
            if args.system:
                messages.append({"role": "system", "content": args.system})
            messages.append({"role": "user", "content": args.user})

            if args.stream:
                for chunk in client.chat.completions.create(
                    model=args.model,
                    messages=messages,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                    stream=True
                ):
                    if chunk.choices[0].delta.content:
                        print(chunk.choices[0].delta.content,
                              end="", flush=True)
                print()
            else:
                completion = client.chat.completions.create(
                    model=args.model,
                    messages=messages,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens
                )
                print(completion.choices[0].message.content)

        else:
            # Text completions mode
            if args.stream:
                for chunk in client.completions.create(
                    model=args.model,
                    prompt=args.prompt,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                    stream=True
                ):
                    if chunk.choices[0].text:
                        print(chunk.choices[0].text, end="", flush=True)
                print()
            else:
                completion = client.completions.create(
                    model=args.model,
                    prompt=args.prompt,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens
                )
                print(completion.choices[0].text)

    except Exception as e:
        print(f"❌ Error: {e}")


def handle_files_commands(args):
    """Handle file management commands"""
    api_key = args.api_key or os.getenv("GRAVIXLAYER_API_KEY")
    if not api_key:
        print("❌ Error: API key is required. Set GRAVIXLAYER_API_KEY environment variable or use --api-key")
        return

    try:
        client = GravixLayer(api_key=api_key)
        
        if args.files_action == "upload":
            # Upload file
            if not os.path.exists(args.file):
                print(f"❌ Error: File '{args.file}' not found")
                return
                
            print(f"📤 Uploading file: {args.file}")
            with open(args.file, 'rb') as f:
                upload_args = {
                    'file': f,
                    'purpose': args.purpose
                }
                if args.expires_after:
                    upload_args['expires_after'] = args.expires_after
                    
                response = client.files.upload(**upload_args)
                
            print(f"✅ File uploaded successfully!")
            print(f"   Message: {response.message}")
            print(f"   Filename: {response.file_name}")
            print(f"   Purpose: {response.purpose}")
   
                
        elif args.files_action == "list":
            # List files
            print("📋 Listing files...")
            response = client.files.list()
            
            if args.json:
                print(json.dumps([file.model_dump() for file in response.data], indent=2))
            else:
                if not response.data:
                    print("   No files found")
                else:
                    # Filter by purpose if specified
                    files_to_show = response.data
                    if args.purpose:
                        files_to_show = [file for file in response.data if file.purpose == args.purpose]
                    
                    print(f"   Found {len(files_to_show)} file(s):")
                    for file in files_to_show:
                        print(f"   • {file.id} - {file.filename} ({file.bytes} bytes, {file.purpose})")
                        
        elif args.files_action == "info":
            # Get file info
            file_identifier = args.file_id
            print(f"ℹ️  Getting file info: {file_identifier}")
            
            # Check if the identifier is a filename or file ID
            # File IDs are UUIDs (contain hyphens), filenames typically don't
            if '-' not in file_identifier or not file_identifier.replace('-', '').replace('_', '').isalnum():
                # Likely a filename, need to find the file ID
                print("   Looking up file by name...")
                files_response = client.files.list()
                matching_file = None
                
                for file in files_response.data:
                    if file.filename == file_identifier:
                        matching_file = file
                        break
                
                if not matching_file:
                    print(f"❌ Error: No file found with filename '{file_identifier}'")
                    return
                
                file_id = matching_file.id
                print(f"   Found file ID: {file_id}")
            else:
                # Assume it's a file ID
                file_id = file_identifier
            
            file_info = client.files.retrieve(file_id)
            
            if args.json:
                print(json.dumps(file_info.model_dump(), indent=2))
            else:
                print(f"   File ID: {file_info.id}")
                print(f"   Filename: {file_info.filename}")
                print(f"   Purpose: {file_info.purpose}")
                print(f"   Size: {file_info.bytes} bytes")
                print(f"   Created: {file_info.created_at}")
                if hasattr(file_info, 'expires_at') and file_info.expires_at:
                    print(f"   Expires: {file_info.expires_at}")
                    
        elif args.files_action == "download":
            # Download file
            file_identifier = args.file_id
            print(f"📥 Downloading file: {file_identifier}")
            
            # Check if the identifier is a filename or file ID
            # File IDs are UUIDs (contain hyphens), filenames typically don't
            if '-' not in file_identifier or not file_identifier.replace('-', '').replace('_', '').isalnum():
                # Likely a filename, need to find the file ID
                print("   Looking up file by name...")
                files_response = client.files.list()
                matching_file = None
                
                for file in files_response.data:
                    if file.filename == file_identifier:
                        matching_file = file
                        break
                
                if not matching_file:
                    print(f"❌ Error: No file found with filename '{file_identifier}'")
                    return
                
                file_id = matching_file.id
                print(f"   Found file ID: {file_id}")
            else:
                # Assume it's a file ID
                file_id = file_identifier
            
            content = client.files.content(file_id)
            
            # Determine output filename
            if args.output:
                output_path = args.output
            else:
                # Get file info to determine filename
                file_info = client.files.retrieve(file_id)
                output_path = file_info.filename
                
            with open(output_path, 'wb') as f:
                f.write(content)
                
            print(f"✅ File downloaded to: {output_path}")
            
        elif args.files_action == "delete":
            # Delete file
            file_identifier = args.file_id
            print(f"🗑️  Deleting file: {file_identifier}")
            
            # Check if the identifier is a filename or file ID
            # File IDs are UUIDs (contain hyphens), filenames typically don't
            if '-' not in file_identifier or not file_identifier.replace('-', '').replace('_', '').isalnum():
                # Likely a filename, need to find the file ID
                print("   Looking up file by name...")
                files_response = client.files.list()
                matching_file = None
                
                for file in files_response.data:
                    if file.filename == file_identifier:
                        matching_file = file
                        break
                
                if not matching_file:
                    print(f"❌ Error: No file found with filename '{file_identifier}'")
                    return
                
                file_id = matching_file.id
                print(f"   Found file ID: {file_id}")
            else:
                # Assume it's a file ID
                file_id = file_identifier
            
            response = client.files.delete(file_id)
            
            if response.message == "file deleted":
                print(f"✅ File deleted successfully")
            else:
                print(f"❌ Failed to delete file: {response.message}")
                
    except Exception as e:
        print(f"❌ Error: {str(e)}")


if __name__ == "__main__":
    main()
