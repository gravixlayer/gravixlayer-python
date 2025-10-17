# Dynamic Memory Configuration

The GravixLayer Memory System now supports dynamic configuration switching, allowing you to change embedding models, cloud settings, and databases at runtime without reinitializing the memory system.

## Key Features

### 🔄 Dynamic Configuration Switching
- **Embedding Models**: Switch between different embedding models on-the-fly
- **Cloud Configuration**: Change cloud provider, region, and index type
- **Multiple Databases**: Support for multiple memory databases with easy switching
- **Runtime Flexibility**: All changes take effect immediately without restart

### 🎯 Fallback to Defaults
- System automatically uses defaults when no specific configuration is provided
- Easy reset to default configuration at any time
- Graceful handling of missing or invalid configurations

## Usage Examples

### Basic Initialization

```python
from gravixlayer import AsyncGravixLayer
from gravixlayer.resources.memory import Memory

client = AsyncGravixLayer()

# Initialize with defaults
memory = Memory(client)

# Initialize with specific configuration
memory = Memory(
    client,
    embedding_model="baai/bge-base-en-v1.5",
    index_name="my_custom_database",
    cloud_config={
        "cloud_provider": "GCP",
        "region": "us-central1",
        "index_type": "serverless"
    }
)
```

### Dynamic Configuration Switching

```python
# Switch embedding model
memory.switch_configuration(embedding_model="microsoft/multilingual-e5-large")

# Switch database
memory.switch_configuration(index_name="user_preferences_db")

# Switch cloud configuration
memory.switch_configuration(
    cloud_config={
        "cloud_provider": "AWS",
        "region": "us-west-2",
        "index_type": "serverless"
    }
)

# Switch multiple settings at once
memory.switch_configuration(
    embedding_model="baai/bge-large-en-v1.5",
    index_name="production_memories",
    cloud_config={"cloud_provider": "AWS", "region": "us-east-1"}
)
```

### Per-Operation Overrides

```python
# Add memory with specific model and database
await memory.add(
    "User loves pizza",
    user_id="user123",
    embedding_model="microsoft/multilingual-e5-large",  # Override for this operation
    database_name="food_preferences_db"        # Override for this operation
)

# Search with specific model and database
results = await memory.search(
    "food preferences",
    user_id="user123",
    embedding_model="baai/bge-large-en-v1.5",  # Override for this search
    database_name="food_preferences_db"         # Override for this search
)
```

### Database Management

```python
# List available databases
databases = await memory.list_available_databases()
print(f"Available databases: {databases}")

# Switch to specific database
success = await memory.switch_database("user_profiles_db")

# Get current configuration
config = memory.get_current_configuration()
print(f"Current database: {config['index_name']}")
```

### Configuration Management

```python
# Get current configuration
config = memory.get_current_configuration()
print(config)
# Output:
# {
#     'embedding_model': 'baai/bge-large-en-v1.5',
#     'inference_model': 'mistralai/mistral-nemo-instruct-2407',
#     'index_name': 'gravixlayer_memories',
#     'cloud_config': {'cloud_provider': 'AWS', 'region': 'us-east-1', 'index_type': 'serverless'},
#     'embedding_dimension': 1024
# }

# Reset to defaults
memory.reset_to_defaults()
```

## Configuration Options

### Embedding Models
- `baai/bge-large-en-v1.5` (1024 dim) - **Default**
- `baai/bge-base-en-v1.5` (768 dim)
- `baai/bge-small-en-v1.5` (384 dim)
- `microsoft/multilingual-e5-large` (1536 dim)
- `text-embedding-3-small` (1536 dim)
- `text-embedding-3-large` (3072 dim)
- `all-MiniLM-L6-v2` (384 dim)
- `all-mpnet-base-v2` (768 dim)

### Inference Models
- `mistralai/mistral-nemo-instruct-2407` - **Default**
- `meta-llama/llama-3.1-8b-instruct`
- `meta-llama/llama-3.1-70b-instruct`
- `anthropic/claude-3-haiku-20240307`
- `openai/gpt-4o-mini`

### Cloud Providers
- **AWS** (default): `us-east-1`, `us-west-2`, `eu-west-1`, `ap-southeast-1`
- **GCP**: `us-central1`, `europe-west1`, `asia-southeast1`
- **Azure**: `eastus`, `westus2`, `westeurope`, `southeastasia`

### Database Names
- `gravixlayer_memories` - **Default**
- Any custom name you specify

## Advanced Usage

### Using the Configuration Manager

```python
from gravixlayer.resources.memory import DynamicMemoryConfig

# Create configuration manager
config = DynamicMemoryConfig()

# Show current configuration
config.print_current_config()

# Show available options
config.print_available_options()

# Switch configurations
config.switch_embedding_model("microsoft/multilingual-e5-large")
config.switch_database("my_custom_db")
config.switch_cloud_config(provider="GCP", region="us-central1")

# Get configuration as dict
config_dict = config.get_current_config()
```

### Multiple Database Workflow

```python
# Start with default database
memory = Memory(client)
await memory.add("General information", user_id="user123")

# Switch to user preferences database
memory.switch_configuration(index_name="user_preferences")
await memory.add("User likes dark mode", user_id="user123")

# Switch to conversation history database
memory.switch_configuration(index_name="conversation_history")
await memory.add("User asked about weather", user_id="user123")

# Search across different databases
general_results = await memory.search("info", "user123", database_name="gravixlayer_memories")
prefs_results = await memory.search("preferences", "user123", database_name="user_preferences")
history_results = await memory.search("weather", "user123", database_name="conversation_history")
```

## Migration from Static Configuration

### Before (Static)
```python
# Old way - fixed configuration
memory = Memory(client, embedding_model="baai/bge-large-en-v1.5")
# Had to create new instance to change model
```

### After (Dynamic)
```python
# New way - dynamic configuration
memory = Memory(client)  # Uses defaults
memory.switch_configuration(embedding_model="baai/bge-large-en-v1.5")  # Change anytime
memory.switch_configuration(embedding_model="microsoft/multilingual-e5-large")  # Change again
```

## Best Practices

1. **Use Defaults**: Let the system use defaults unless you have specific requirements
2. **Per-Operation Overrides**: Use operation-level overrides for temporary changes
3. **Database Naming**: Use descriptive database names (e.g., `user_preferences`, `conversation_history`)
4. **Configuration Tracking**: Use `get_current_configuration()` to track active settings
5. **Dimension Matching**: Ensure embedding models match your vector dimensions
6. **Testing**: Test configuration changes in development before production

## Error Handling

The system gracefully handles configuration errors:

```python
# Invalid embedding model
memory.switch_configuration(embedding_model="invalid-model")
# Output: ❌ Unknown embedding model: invalid-model

# Invalid cloud provider
memory.switch_configuration(cloud_config={"cloud_provider": "InvalidCloud"})
# Output: ❌ Unknown cloud provider: InvalidCloud

# System continues with previous valid configuration
```

## Performance Considerations

- **Index Caching**: Database indexes are cached for performance
- **Model Switching**: Embedding model changes only affect new operations
- **Cloud Configuration**: Changes only apply to new database creation
- **Memory Overhead**: Minimal overhead for configuration management

This dynamic configuration system provides maximum flexibility while maintaining backward compatibility and ease of use.