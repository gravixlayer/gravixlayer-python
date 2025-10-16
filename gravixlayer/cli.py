

import argparse
import os
import json
import sys
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


def safe_json_parse(json_str, field_name="JSON"):
    """Safely parse JSON string with helpful error messages"""
    if not json_str:
        return {}
    
    # First, try parsing as-is
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        # If parsing fails, show helpful error message
        print(f"ERROR: Invalid JSON in {field_name}")
        print(f"   JSON string: {json_str}")
        print(f"   Error: {e}")
        print()
        print("Tips for fixing JSON:")
        print("1. Use double quotes for strings: {\"key\": \"value\"}")
        print("2. PowerShell IMPORTANT: Use single quotes around JSON and escape inner quotes:")
        print("   CORRECT:   --metadata '{\\\"key\\\":\\\"value\\\"}'")
        print("   INCORRECT: --metadata '{\"key\": \"value\"}'  (PowerShell strips quotes)")
        print("3. For complex JSON, save to file and use --metadata-file")
        print("4. For very complex JSON, use --metadata-b64 <base64-encoded-json>")
        print("5. Example working formats:")
        print("   PowerShell: --metadata '{\\\"type\\\":\\\"test\\\"}'")
        print("   PowerShell: --metadata '{\\\"title\\\": \\\"Updated Document\\\"}'")
        print("   Bash/Linux: --metadata '{\"type\":\"test\"}'")
        print("   CMD: --metadata \"{\\\"type\\\":\\\"test\\\"}\"")
        print("6. PowerShell common mistake: Using unescaped quotes causes quote stripping")
        print("7. Alternative: Use --metadata-file for complex JSON with spaces")
        return None


def parse_metadata(args, field_name="metadata"):
    """Parse metadata from --metadata string, --metadata-file, or --metadata-b64"""
    import base64
    
    if hasattr(args, 'metadata_file') and args.metadata_file:
        try:
            with open(args.metadata_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"ERROR: Metadata file not found: {args.metadata_file}")
            return None
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON in metadata file: {args.metadata_file}")
            print(f"   Error: {e}")
            return None
    elif hasattr(args, 'metadata_b64') and args.metadata_b64:
        try:
            decoded_json = base64.b64decode(args.metadata_b64).decode('utf-8')
            return json.loads(decoded_json)
        except Exception as e:
            print(f"ERROR: Invalid base64-encoded JSON in {field_name}")
            print(f"   Error: {e}")
            print("   Tip: Encode your JSON with: echo '{\"key\":\"value\"}' | base64")
            return None
    elif hasattr(args, 'metadata') and args.metadata:
        # Handle case where metadata is a list (from nargs='*')
        if isinstance(args.metadata, list):
            metadata_str = ' '.join(args.metadata)
        else:
            metadata_str = args.metadata
        return safe_json_parse(metadata_str, field_name)
    else:
        return {}


def main():
    parser = argparse.ArgumentParser(
        description="GravixLayer CLI – Chat Completions, Text Completions, Deployment Management, File Management, and Vector Database"
    )

    # Create subparsers for different commands
    subparsers = parser.add_subparsers(
        dest="command", help="Available commands", required=True)

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
        dest="deployments_action", help="Deployment actions", required=True)

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
        dest="files_action", help="File actions", required=True)

    # Upload file
    upload_parser = files_subparsers.add_parser(
        "upload", help="Upload a file")
    upload_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    upload_parser.add_argument(
        "--file", required=True, help="Path to file to upload")
    upload_parser.add_argument(
        "--file_name", help="Custom name for the uploaded file (optional)")
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

    # Vectors parser (for vector database management)
    vectors_parser = subparsers.add_parser(
        "vectors", help="Vector database management")
    vectors_subparsers = vectors_parser.add_subparsers(
        dest="vectors_action", help="Vector actions", required=True)

    # Index management
    index_parser = vectors_subparsers.add_parser(
        "index", help="Index management")
    index_subparsers = index_parser.add_subparsers(
        dest="index_action", help="Index actions", required=True)

    # Create index
    create_index_parser = index_subparsers.add_parser(
        "create", help="Create a vector index")
    create_index_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    create_index_parser.add_argument(
        "--name", required=True, help="Index name")
    create_index_parser.add_argument(
        "--dimension", type=int, required=True, help="Vector dimension (1-2000)")
    create_index_parser.add_argument(
        "--metric", required=True, choices=["cosine", "euclidean", "dotproduct"],
        help="Similarity metric")
    create_index_parser.add_argument(
        "--cloud-provider", required=True, choices=["AWS", "GCP", "Azure", "Gravix"],
        help="Cloud provider")
    create_index_parser.add_argument(
        "--region", required=True, help="Region ID (e.g., us-east-1, us-central1, eastus)")
    create_index_parser.add_argument(
        "--index-type", required=True, choices=["serverless", "dedicated"],
        help="Index type")
    create_index_parser.add_argument(
        "--vector-type", default="dense", help="Vector type (default: dense)")
    create_index_parser.add_argument(
        "--metadata", nargs='*', help="JSON metadata for the index")
    create_index_parser.add_argument(
        "--metadata-file", help="Path to JSON file containing metadata")
    create_index_parser.add_argument(
        "--metadata-b64", help="Base64-encoded JSON metadata (for complex JSON with spaces)")
    create_index_parser.add_argument(
        "--delete-protection", action="store_true", help="Enable delete protection")

    # List indexes
    list_indexes_parser = index_subparsers.add_parser(
        "list", help="List all indexes")
    list_indexes_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    list_indexes_parser.add_argument(
        "--json", action="store_true", help="Output as JSON")

    # Get index
    get_index_parser = index_subparsers.add_parser(
        "get", help="Get index information")
    get_index_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    get_index_parser.add_argument("index_id", help="Index ID")
    get_index_parser.add_argument(
        "--json", action="store_true", help="Output as JSON")

    # Update index
    update_index_parser = index_subparsers.add_parser(
        "update", help="Update index")
    update_index_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    update_index_parser.add_argument("index_id", help="Index ID")
    update_index_parser.add_argument(
        "--metadata", nargs='*', help="JSON metadata to update")
    update_index_parser.add_argument(
        "--metadata-file", help="Path to JSON file containing metadata")
    update_index_parser.add_argument(
        "--metadata-b64", help="Base64-encoded JSON metadata (for complex JSON with spaces)")
    update_index_parser.add_argument(
        "--delete-protection", type=str, choices=["true", "false"], help="Enable/disable delete protection (true/false)")

    # Delete index
    delete_index_parser = index_subparsers.add_parser(
        "delete", help="Delete index")
    delete_index_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    delete_index_parser.add_argument("index_id", help="Index ID to delete")

    # Vector operations
    vector_parser = vectors_subparsers.add_parser(
        "vector", help="Vector operations")
    vector_subparsers = vector_parser.add_subparsers(
        dest="vector_action", help="Vector actions", required=True)

    # Upsert vector
    upsert_parser = vector_subparsers.add_parser(
        "upsert", help="Upsert a vector")
    upsert_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    upsert_parser.add_argument("index_id", help="Index ID")
    upsert_parser.add_argument(
        "--embedding", nargs='*', required=True, help="Vector embedding as JSON array")
    upsert_parser.add_argument(
        "--id", help="Vector ID (auto-generated if not provided)")
    upsert_parser.add_argument(
        "--metadata", nargs='*', help="JSON metadata for the vector")
    upsert_parser.add_argument(
        "--metadata-file", help="Path to JSON file containing metadata")
    upsert_parser.add_argument(
        "--metadata-b64", help="Base64-encoded JSON metadata")
    upsert_parser.add_argument(
        "--delete-protection", action="store_true", help="Enable delete protection for this vector")

    # Upsert text vector
    upsert_text_parser = vector_subparsers.add_parser(
        "upsert-text", help="Upsert a text vector")
    upsert_text_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    upsert_text_parser.add_argument("index_id", help="Index ID")
    upsert_text_parser.add_argument(
        "--text", required=True, help="Text to convert to vector")
    upsert_text_parser.add_argument(
        "--model", required=True, help="Embedding model name")
    upsert_text_parser.add_argument(
        "--id", help="Vector ID (auto-generated if not provided)")
    upsert_text_parser.add_argument(
        "--metadata", nargs='*', help="JSON metadata for the vector")
    upsert_text_parser.add_argument(
        "--metadata-file", help="Path to JSON file containing metadata")
    upsert_text_parser.add_argument(
        "--metadata-b64", help="Base64-encoded JSON metadata")
    upsert_text_parser.add_argument(
        "--delete-protection", action="store_true", help="Enable delete protection for this vector")

    # Search vectors
    search_parser = vector_subparsers.add_parser(
        "search", help="Search vectors")
    search_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    search_parser.add_argument("index_id", help="Index ID")
    search_parser.add_argument(
        "--vector", nargs='*', required=True, help="Query vector as JSON array")
    search_parser.add_argument(
        "--top-k", type=int, default=10, help="Number of results (default: 10)")
    search_parser.add_argument(
        "--filter", nargs='*', help="JSON filter for metadata")
    search_parser.add_argument(
        "--include-metadata", type=str, choices=["true", "false"], default="true", help="Include metadata (true/false)")
    search_parser.add_argument(
        "--include-values", type=str, choices=["true", "false"], default="false", help="Include vector values (true/false)")

    # Search text
    search_text_parser = vector_subparsers.add_parser(
        "search-text", help="Search using text")
    search_text_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    search_text_parser.add_argument("index_id", help="Index ID")
    search_text_parser.add_argument(
        "--query", required=True, help="Search query text")
    search_text_parser.add_argument(
        "--model", required=True, help="Embedding model name")
    search_text_parser.add_argument(
        "--top-k", type=int, default=10, help="Number of results (default: 10)")
    search_text_parser.add_argument(
        "--filter", nargs='*', help="JSON filter for metadata")

    # List vectors
    list_vectors_parser = vector_subparsers.add_parser(
        "list", help="List vectors in index")
    list_vectors_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    list_vectors_parser.add_argument("index_id", help="Index ID")
    list_vectors_parser.add_argument(
        "--ids-only", action="store_true", help="List only vector IDs")

    # Get vector
    get_vector_parser = vector_subparsers.add_parser(
        "get", help="Get vector information")
    get_vector_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    get_vector_parser.add_argument("index_id", help="Index ID")
    get_vector_parser.add_argument("vector_id", help="Vector ID")

    # Update vector
    update_vector_parser = vector_subparsers.add_parser(
        "update", help="Update vector metadata and delete protection")
    update_vector_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    update_vector_parser.add_argument("index_id", help="Index ID")
    update_vector_parser.add_argument("vector_id", help="Vector ID")
    update_vector_parser.add_argument(
        "--metadata", nargs='*', help="JSON metadata to update")
    update_vector_parser.add_argument(
        "--metadata-file", help="Path to JSON file containing metadata")
    update_vector_parser.add_argument(
        "--metadata-b64", help="Base64-encoded JSON metadata")
    update_vector_parser.add_argument(
        "--delete-protection", type=str, choices=["true", "false"], help="Enable/disable delete protection (true/false)")

    # Delete vector
    delete_vector_parser = vector_subparsers.add_parser(
        "delete", help="Delete vector")
    delete_vector_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    delete_vector_parser.add_argument("index_id", help="Index ID")
    delete_vector_parser.add_argument("vector_id", help="Vector ID to delete")

    # Batch delete vectors
    batch_delete_parser = vector_subparsers.add_parser(
        "batch-delete", help="Delete multiple vectors")
    batch_delete_parser.add_argument(
        "--api-key", type=str, default=None, help="API key")
    batch_delete_parser.add_argument("index_id", help="Index ID")
    batch_delete_parser.add_argument(
        "--vector-ids", required=True, help="Comma-separated list of vector IDs to delete")

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
    elif args.command == "vectors":
        handle_vectors_commands(args)
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
                        print(f"ERROR: Deployment failed with status: {current_deployment.status}")
                        break
                    else:
                        # Still creating/pending
                        time.sleep(10)  # Wait 10 seconds before checking again
                else:
                    print("   ERROR: Deployment not found")
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
                print(f"ERROR: Error: GPU count must be one of: 1, 2, 4, 8. You provided: {args.gpu_count}")
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

                print("SUCCESS: Deployment created successfully!")
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
                                        print(f"ERROR: Deployment creation failed: deployment with name '{original_name}' already exists.")
                                        if hasattr(args, 'auto_retry') and args.auto_retry:
                                            print("Auto-retry was already attempted but failed.")
                                        else:
                                            print(f"Try with --auto-retry flag: gravixlayer deployments create --deployment_name \"{original_name}\" --gpu_model \"{args.gpu_model}\" --model_name \"{args.model_name}\" --auto-retry")
                                    else:
                                        print(f"WARNING:  Deployment creation failed: {error_message}")
                                        print("This might be a temporary API issue. Please try again.")
                            except Exception as list_error:
                                print(f"ERROR: Deployment creation failed: {error_message}")
                                print(f"WARNING:  Could not verify deployment status due to an error: {list_error}")
                        else:
                            print(f"ERROR: Deployment creation failed: {error_message}")
                    else:
                        print(f"ERROR: Deployment creation failed: {error_str}")
                except (json.JSONDecodeError, ValueError):
                    print(f"ERROR: Deployment creation failed: {error_str}")
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
                        
                        for accelerator in accelerators:
                            print(f"GPU ID: {accelerator.gpu_id or 'N/A'}")
                            print(f"Model: {accelerator.name}")  # This will show "NVIDIA T4 16GB" format
                            print(f"GPU Model Code: {accelerator.gpu_model or 'N/A'}")
                            print(f"Memory: {accelerator.memory}")
                            print(f"Link: {accelerator.gpu_link or 'N/A'}")
                            print(f"Status: {accelerator.status or 'N/A'}")
                            print(f"Pricing: ${accelerator.pricing or 0}/hour")
                            if accelerator.updated_at:
                                print(f"Updated: {accelerator.updated_at}")
                            print()
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
                    max_tokens=args.max_tokens or 150,
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
                    max_tokens=args.max_tokens or 150
                )
                print(completion.choices[0].message.content)

        else:
            # Text completions mode
            if args.stream:
                for chunk in client.completions.create(
                    model=args.model,
                    prompt=args.prompt,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens or 150,
                    stream=True
                ):
                    if chunk.choices[0].text is not None:
                        print(chunk.choices[0].text, end="", flush=True)
                print()
            else:
                completion = client.completions.create(
                    model=args.model,
                    prompt=args.prompt,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens or 150
                )
                print(completion.choices[0].text)

    except Exception as e:
        print(f"ERROR: Error: {e}")


def handle_files_commands(args):
    """Handle file management commands"""
    api_key = args.api_key or os.getenv("GRAVIXLAYER_API_KEY")
    if not api_key:
        print("ERROR: Error: API key is required. Set GRAVIXLAYER_API_KEY environment variable or use --api-key")
        return

    try:
        client = GravixLayer(api_key=api_key)
        
        if args.files_action == "upload":
            # Upload file
            if not os.path.exists(args.file):
                print(f"ERROR: Error: File '{args.file}' not found")
                return
                
            print(f"Uploading file: {args.file}")
            with open(args.file, 'rb') as f:
                upload_args = {
                    'file': f,
                    'purpose': args.purpose
                }
                if args.expires_after:
                    upload_args['expires_after'] = args.expires_after
                if args.file_name:
                    upload_args['filename'] = args.file_name
                    
                response = client.files.upload(**upload_args)
                
            print(f"SUCCESS: File uploaded successfully!")
            print(f"   Message: {response.message}")
            print(f"   Filename: {response.file_name}")
            print(f"   Purpose: {response.purpose}")
   
                
        elif args.files_action == "list":
            # List files
            print("Listing files...")
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
                    print()
                    for file in files_to_show:
                        print(f"File ID: {file.id}")
                        print(f"Filename: {file.filename}")
                        print(f"Size: {file.bytes} bytes")
                        print(f"Purpose: {file.purpose}")
                        if hasattr(file, 'created_at') and file.created_at:
                            # Convert Unix timestamp to ISO format
                            from datetime import datetime
                            created_date = datetime.fromtimestamp(file.created_at).isoformat() + 'Z'
                            print(f"Created: {created_date}")
                        print()
                        
        elif args.files_action == "info":
            # Get file info
            file_identifier = args.file_id
            print(f"Getting file info: {file_identifier}")
            
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
                    print(f"ERROR: Error: No file found with filename '{file_identifier}'")
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
                    print(f"ERROR: Error: No file found with filename '{file_identifier}'")
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
                
            print(f"SUCCESS: File downloaded to: {output_path}")
            
        elif args.files_action == "delete":
            # Delete file
            file_identifier = args.file_id
            print(f"Deleting file: {file_identifier}")
            
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
                    print(f"ERROR: Error: No file found with filename '{file_identifier}'")
                    return
                
                file_id = matching_file.id
                print(f"   Found file ID: {file_id}")
            else:
                # Assume it's a file ID
                file_id = file_identifier
            
            response = client.files.delete(file_id)
            
            if response.message == "file deleted":
                print(f"SUCCESS: File deleted successfully")
            else:
                print(f"ERROR: Failed to delete file: {response.message}")
                
    except Exception as e:
        print(f"ERROR: Error: {str(e)}")


def handle_vectors_commands(args):
    """Handle vector database commands"""
    api_key = args.api_key or os.getenv("GRAVIXLAYER_API_KEY")
    if not api_key:
        print("ERROR: Error: API key is required. Set GRAVIXLAYER_API_KEY environment variable or use --api-key")
        return

    try:
        client = GravixLayer(api_key=api_key)
        
        if args.vectors_action == "index":
            # Index management commands
            if args.index_action == "create":
                print(f"Creating vector index: {args.name}")
                
                # Parse metadata if provided
                metadata = parse_metadata(args, "metadata")
                if metadata is None:
                    return
                
                index = client.vectors.indexes.create(
                    name=args.name,
                    dimension=args.dimension,
                    metric=args.metric,
                    cloud_provider=getattr(args, 'cloud_provider'),
                    region=getattr(args, 'region'),
                    index_type=getattr(args, 'index_type'),
                    vector_type=getattr(args, 'vector_type', 'dense'),
                    metadata=metadata,
                    delete_protection=getattr(args, 'delete_protection', False)
                )
                
                print("Index created successfully!")
                print(f"   Index ID: {index.id}")
                print(f"   Name: {index.name}")
                print(f"   Dimension: {index.dimension}")
                print(f"   Metric: {index.metric}")
                print(f"   Cloud Provider: {index.cloud_provider}")
                print(f"   Region: {index.region}")
                print(f"   Index Type: {index.index_type}")
                print(f"   Vector Type: {index.vector_type}")
                if index.metadata:
                    print(f"   Metadata: {json.dumps(index.metadata, indent=2)}")
                
            elif args.index_action == "list":
                print("Listing vector indexes...")
                indexes_list = client.vectors.indexes.list()
                
                if args.json:
                    indexes_data = []
                    for idx in indexes_list.indexes:
                        indexes_data.append({
                            "id": idx.id,
                            "name": idx.name,
                            "dimension": idx.dimension,
                            "metric": idx.metric,
                            "vector_type": idx.vector_type,
                            "metadata": idx.metadata,
                            "delete_protection": idx.delete_protection,
                            "created_at": idx.created_at,
                            "updated_at": idx.updated_at
                        })
                    print(json.dumps(indexes_data, indent=2))
                else:
                    if not indexes_list.indexes:
                        print("   No indexes found")
                    else:
                        print(f"   Found {len(indexes_list.indexes)} index(es):")
                        print()
                        for idx in indexes_list.indexes:
                            print(f"Index ID: {idx.id}")
                            print(f"Name: {idx.name}")
                            print(f"Dimension: {idx.dimension}")
                            print(f"Metric: {idx.metric}")
                            print(f"Vector Type: {idx.vector_type}")
                            print(f"Delete Protection: {idx.delete_protection}")
                            print(f"Created: {idx.created_at}")
                            if idx.metadata:
                                print(f"Metadata: {json.dumps(idx.metadata)}")
                            print()
                
            elif args.index_action == "get":
                print(f"Getting index info: {args.index_id}")
                index = client.vectors.indexes.get(args.index_id)
                
                if args.json:
                    index_data = {
                        "id": index.id,
                        "name": index.name,
                        "dimension": index.dimension,
                        "metric": index.metric,
                        "vector_type": index.vector_type,
                        "metadata": index.metadata,
                        "delete_protection": index.delete_protection,
                        "created_at": index.created_at,
                        "updated_at": index.updated_at
                    }
                    print(json.dumps(index_data, indent=2))
                else:
                    print(f"Index ID: {index.id}")
                    print(f"Name: {index.name}")
                    print(f"Dimension: {index.dimension}")
                    print(f"Metric: {index.metric}")
                    print(f"Vector Type: {index.vector_type}")
                    print(f"Delete Protection: {index.delete_protection}")
                    print(f"Created: {index.created_at}")
                    print(f"Updated: {index.updated_at}")
                    if index.metadata:
                        print(f"Metadata: {json.dumps(index.metadata, indent=2)}")
                
            elif args.index_action == "update":
                print(f"Updating index: {args.index_id}")
                
                update_data = {}
                parsed_metadata = parse_metadata(args, "metadata")
                if parsed_metadata is None:
                    return
                if parsed_metadata:  # Only add if not empty
                    update_data["metadata"] = parsed_metadata
                
                if hasattr(args, 'delete_protection') and args.delete_protection is not None:
                    update_data["delete_protection"] = args.delete_protection.lower() == "true"
                
                if not update_data:
                    print("ERROR: Error: No update data provided")
                    return
                
                updated_index = client.vectors.indexes.update(args.index_id, **update_data)
                print("SUCCESS: Index updated successfully!")
                print(f"   Name: {updated_index.name}")
                print(f"   Metadata: {json.dumps(updated_index.metadata, indent=2)}")
                
            elif args.index_action == "delete":
                print(f"Deleting index: {args.index_id}")
                client.vectors.indexes.delete(args.index_id)
                print("SUCCESS: Index deleted successfully!")
        
        elif args.vectors_action == "vector":
            # Vector operations
            vectors = client.vectors.index(args.index_id)
            
            if args.vector_action == "upsert":
                print(f"Upserting vector to index: {args.index_id}")
                
                # Parse embedding
                # Handle case where embedding is a list (from nargs='*')
                if isinstance(args.embedding, list):
                    embedding_str = ' '.join(args.embedding)
                else:
                    embedding_str = args.embedding
                embedding = safe_json_parse(embedding_str, "embedding")
                if embedding is None:
                    return
                if not isinstance(embedding, list):
                    print("ERROR: Error: Embedding must be a JSON array")
                    return
                
                # Get index info to validate dimensions
                try:
                    index_info = client.vectors.indexes.get(args.index_id)
                    expected_dim = index_info.dimension
                    actual_dim = len(embedding)
                    
                    if actual_dim != expected_dim:
                        print(f"ERROR: Dimension mismatch!")
                        print(f"   Index expects: {expected_dim} dimensions")
                        print(f"   Your vector has: {actual_dim} dimensions")
                        print(f"   Tip: Use 'gravixlayer vectors vector upsert-text' for automatic embedding generation")
                        print(f"   Tip: Or provide a vector with {expected_dim} dimensions")
                        return
                        
                except Exception as e:
                    print(f"ERROR: Could not validate index: {e}")
                    return
                
                # Parse metadata if provided
                metadata = parse_metadata(args, "metadata")
                if metadata is None:
                    return
                
                try:
                    vector = vectors.upsert(
                        embedding=embedding,
                        id=getattr(args, 'id', None),
                        metadata=metadata,
                        delete_protection=getattr(args, 'delete_protection', False)
                    )
                    
                    print("SUCCESS: Vector upserted successfully!")
                    print(f"   Vector ID: {vector.id}")
                    print(f"   Dimension: {len(vector.embedding)}")
                    if vector.metadata:
                        print(f"   Metadata: {json.dumps(vector.metadata)}")
                        
                except Exception as e:
                    error_str = str(e)
                    if "upserted_count" in error_str:
                        print("SUCCESS: Vector upserted successfully!")
                        print(f"   Vector ID: {getattr(args, 'id', 'auto-generated')}")
                        print(f"   Note: Vector upsert completed but response parsing had issues")
                        print(f"   Tip: Use 'gravixlayer vectors vector get <index-id> <vector-id>' to verify")
                    elif "dimension" in error_str.lower() or "mismatch" in error_str.lower():
                        print(f"ERROR: Dimension mismatch - {error_str}")
                        print(f"   Your vector has {len(embedding)} dimensions")
                        print(f"   Tip: Check your index dimension with 'gravixlayer vectors index get <index-id>'")
                        print(f"   Tip: Use 'gravixlayer vectors vector upsert-text' for automatic embedding generation")
                        return
                    else:
                        print(f"ERROR: Error: {error_str}")
                        return
                
            elif args.vector_action == "upsert-text":
                print(f"Upserting text vector to index: {args.index_id}")
                
                # Parse metadata if provided
                metadata = parse_metadata(args, "metadata")
                if metadata is None:
                    return
                
                try:
                    text_vector = vectors.upsert_text(
                        text=args.text,
                        model=args.model,
                        id=getattr(args, 'id', None),
                        metadata=metadata,
                        delete_protection=getattr(args, 'delete_protection', False)
                    )
                    
                    print("SUCCESS: Text vector upserted successfully!")
                    print(f"   Vector ID: {text_vector.id}")
                    print(f"   Model: {text_vector.model}")
                    print(f"   Dimension: {len(text_vector.embedding)}")
                    print(f"   Usage: {text_vector.usage}")
                    if text_vector.metadata:
                        print(f"   Metadata: {json.dumps(text_vector.metadata)}")
                        
                except Exception as e:
                    error_str = str(e)
                    if "upserted_count" in error_str:
                        print("SUCCESS: Text vector upserted successfully!")
                        print(f"   Vector ID: {getattr(args, 'id', 'auto-generated')}")
                        print(f"   Note: Vector upsert completed but response parsing had issues")
                        print(f"   Tip: Use 'gravixlayer vectors vector get <index-id> <vector-id>' to verify")
                    else:
                        print(f"ERROR: Error: {error_str}")
                        return
                
            elif args.vector_action == "search":
                print(f"Searching vectors in index: {args.index_id}")
                
                # Parse query vector
                # Handle case where vector is a list (from nargs='*')
                if isinstance(args.vector, list):
                    vector_str = ' '.join(args.vector)
                else:
                    vector_str = args.vector
                query_vector = safe_json_parse(vector_str, "query vector")
                if query_vector is None:
                    return
                if not isinstance(query_vector, list):
                    print("ERROR: Error: Query vector must be a JSON array")
                    return
                
                # Parse filter if provided
                filter_dict = None
                if args.filter:
                    # Handle case where filter is a list (from nargs='*')
                    if isinstance(args.filter, list):
                        filter_str = ' '.join(args.filter)
                    else:
                        filter_str = args.filter
                    filter_dict = safe_json_parse(filter_str, "filter")
                    if filter_dict is None:
                        return
                
                # Parse boolean arguments
                include_metadata = getattr(args, 'include_metadata', 'true').lower() == 'true'
                include_values = getattr(args, 'include_values', 'false').lower() == 'true'
                
                results = vectors.search(
                    vector=query_vector,
                    top_k=getattr(args, 'top_k', 10),
                    filter=filter_dict,
                    include_metadata=include_metadata,
                    include_values=include_values
                )
                
                print(f"SUCCESS: Search completed in {results.query_time_ms}ms")
                print(f"   Found {len(results.hits)} result(s):")
                print()
                
                for i, hit in enumerate(results.hits, 1):
                    print(f"{i}. Vector ID: {hit.id}")
                    print(f"   Score: {hit.score:.6f}")
                    if hit.metadata:
                        print(f"   Metadata: {json.dumps(hit.metadata)}")
                    if hit.values:
                        print(f"   Values: {hit.values[:5]}... (showing first 5)")
                    print()
                
            elif args.vector_action == "search-text":
                print(f"Text search in index: {args.index_id}")
                
                # Parse filter if provided
                filter_dict = None
                if args.filter:
                    # Handle case where filter is a list (from nargs='*')
                    if isinstance(args.filter, list):
                        filter_str = ' '.join(args.filter)
                    else:
                        filter_str = args.filter
                    filter_dict = safe_json_parse(filter_str, "filter")
                    if filter_dict is None:
                        return
                
                results = vectors.search_text(
                    query=args.query,
                    model=args.model,
                    top_k=getattr(args, 'top_k', 10),
                    filter=filter_dict
                )
                
                print(f"SUCCESS: Text search completed in {results.query_time_ms}ms")
                print(f"   Usage: {results.usage}")
                print(f"   Found {len(results.hits)} result(s):")
                print()
                
                for i, hit in enumerate(results.hits, 1):
                    print(f"{i}. Vector ID: {hit.id}")
                    print(f"   Score: {hit.score:.6f}")
                    if hit.metadata:
                        print(f"   Metadata: {json.dumps(hit.metadata)}")
                    print()
                
            elif args.vector_action == "list":
                print(f"Listing vectors in index: {args.index_id}")
                
                if getattr(args, 'ids_only', False):
                    vector_ids = vectors.list_ids()
                    print(f"   Found {len(vector_ids.vectors)} vector(s):")
                    for v in vector_ids.vectors:
                        print(f"   - {v['id']}")
                else:
                    vectors_data = vectors.list()
                    print(f"   Found {len(vectors_data.vectors)} vector(s):")
                    print()
                    for vector_id, vector_data in vectors_data.vectors.items():
                        print(f"Vector ID: {vector_id}")
                        print(f"Dimension: {len(vector_data.embedding)}")
                        print(f"Delete Protection: {vector_data.delete_protection}")
                        print(f"Created: {vector_data.created_at}")
                        if vector_data.metadata:
                            print(f"Metadata: {json.dumps(vector_data.metadata)}")
                        print()
                
            elif args.vector_action == "get":
                print(f"Getting vector: {args.vector_id}")
                vector = vectors.get(args.vector_id)
                
                print(f"Vector ID: {vector.id}")
                print(f"Dimension: {len(vector.embedding)}")
                print(f"Delete Protection: {vector.delete_protection}")
                print(f"Created: {vector.created_at}")
                print(f"Updated: {vector.updated_at}")
                if vector.metadata:
                    print(f"Metadata: {json.dumps(vector.metadata, indent=2)}")
                print(f"Embedding: {vector.embedding[:5]}... (showing first 5 values)")
                
            elif args.vector_action == "update":
                print(f"Updating vector: {args.vector_id}")
                
                # Parse metadata if provided
                metadata = None
                if hasattr(args, 'metadata') or hasattr(args, 'metadata_file') or hasattr(args, 'metadata_b64'):
                    metadata = parse_metadata(args, "metadata")
                    if metadata is None and (args.metadata or args.metadata_file or args.metadata_b64):
                        return
                
                # Parse delete protection if provided
                delete_protection = None
                if hasattr(args, 'delete_protection') and args.delete_protection:
                    delete_protection = args.delete_protection.lower() == "true"
                
                # Check if at least one field is provided
                if metadata is None and delete_protection is None:
                    print("ERROR: At least one field must be provided for update (--metadata, --metadata-file, --metadata-b64, or --delete-protection)")
                    return
                
                try:
                    updated_vector = vectors.update(
                        vector_id=args.vector_id,
                        metadata=metadata,
                        delete_protection=delete_protection
                    )
                    
                    print("SUCCESS: Vector updated successfully!")
                    print(f"   Vector ID: {updated_vector.id}")
                    print(f"   Delete Protection: {updated_vector.delete_protection}")
                    if updated_vector.metadata:
                        print(f"   Metadata: {json.dumps(updated_vector.metadata)}")
                        
                except Exception as e:
                    print(f"ERROR: Error updating vector: {e}")
                    return
                
            elif args.vector_action == "delete":
                print(f"Deleting vector: {args.vector_id}")
                vectors.delete(args.vector_id)
                print("SUCCESS: Vector deleted successfully!")
                
            elif args.vector_action == "batch-delete":
                # Parse comma-separated vector IDs
                vector_ids = [vid.strip() for vid in args.vector_ids.split(",")]
                print(f"Deleting {len(vector_ids)} vectors: {vector_ids}")
                
                try:
                    result = vectors.batch_delete(vector_ids)
                    print("SUCCESS: Batch delete completed!")
                    print(f"   Deleted IDs: {result.get('deleted_ids', [])}")
                    print(f"   Count: {result.get('count', 0)}")
                except Exception as e:
                    print(f"ERROR: Batch delete failed: {e}")
                    return
        
    except Exception as e:
        print(f"ERROR: Error: {e}")


if __name__ == "__main__":
    main()