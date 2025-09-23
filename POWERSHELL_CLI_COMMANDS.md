# GravixLayer CLI Commands - PowerShell Edition

## Prerequisites
```powershell
$env:GRAVIXLAYER_API_KEY="your_api_key_here"
```

## Index Management Commands

### Create Index
```powershell
# Basic index creation
python -m gravixlayer.cli vectors index create --name "my-embeddings" --dimension 1024 --metric cosine

# Index with simple metadata (PowerShell format)
python -m gravixlayer.cli vectors index create --name "product-embeddings" --dimension 1536 --metric cosine --metadata '{\"description\":\"Product_embeddings\",\"model\":\"text-embedding-ada-002\"}'

# Index with metadata from file (recommended for complex JSON)
python -m gravixlayer.cli vectors index create --name "product-embeddings-file" --dimension 1536 --metric cosine --metadata-file metadata.json

# Index with base64 metadata (for very complex JSON)
python -m gravixlayer.cli vectors index create --name "product-embeddings-b64" --dimension 768 --metric cosine --metadata-b64 eyJkZXNjcmlwdGlvbiI6ICJQcm9kdWN0IGVtYmVkZGluZ3MiLCAibW9kZWwiOiAidGV4dC1lbWJlZGRpbmctYWRhLTAwMiJ9

# Index with delete protection
python -m gravixlayer.cli vectors index create --name "protected-index" --dimension 768 --metric euclidean --delete-protection
```

### List and Get Indexes
```powershell
# List all indexes
python -m gravixlayer.cli vectors index list

# List indexes as JSON
python -m gravixlayer.cli vectors index list --json

# Get index details
python -m gravixlayer.cli vectors index get <index-id>

# Get index details as JSON
python -m gravixlayer.cli vectors index get <index-id> --json
```

### Update Index
```powershell
# Update index metadata (PowerShell format)
python -m gravixlayer.cli vectors index update <index-id> --metadata '{\"description\":\"Updated_embeddings\",\"version\":\"2.0\"}'

# Update with metadata file
python -m gravixlayer.cli vectors index update <index-id> --metadata-file updated_metadata.json

# Enable delete protection
python -m gravixlayer.cli vectors index update <index-id> --delete-protection true

# Disable delete protection
python -m gravixlayer.cli vectors index update <index-id> --delete-protection false
```

### Delete Index
```powershell
python -m gravixlayer.cli vectors index delete <index-id>
```

## Vector Operations Commands

### Upsert Vectors
```powershell
# Upsert vector with embedding (PowerShell format)
python -m gravixlayer.cli vectors vector upsert <index-id> --embedding '[0.1,0.2,0.3,0.4,0.5]' --id "my-vector-1" --metadata '{\"title\":\"Sample_Document\",\"category\":\"test\"}'

# Upsert with metadata file
python -m gravixlayer.cli vectors vector upsert <index-id> --embedding '[0.2,0.3,0.4,0.5,0.6]' --metadata-file vector_metadata.json

# Auto-generate vector ID
python -m gravixlayer.cli vectors vector upsert <index-id> --embedding '[0.2,0.3,0.4,0.5,0.6]' --metadata '{\"title\":\"Another_Document\"}'
```

### Upsert Text Vectors
```powershell
# Upsert text vector (PowerShell format)
python -m gravixlayer.cli vectors vector upsert-text <index-id> --text "This is a sample document for embedding" --model "baai/bge-large-en-v1.5" --id "text-vector-1" --metadata '{\"source\":\"cli\",\"type\":\"example\"}'

# With metadata file
python -m gravixlayer.cli vectors vector upsert-text <index-id> --text "Another sample document" --model "baai/bge-large-en-v1.5" --metadata-file metadata.json

# Auto-generate ID
python -m gravixlayer.cli vectors vector upsert-text <index-id> --text "Another sample document" --model "baai/bge-large-en-v1.5" --metadata '{\"source\":\"cli\"}'
```

### Search Operations
```powershell
# Basic vector search
python -m gravixlayer.cli vectors vector search <index-id> --vector '[0.15,0.25,0.35,0.45,0.55]' --top-k 5

# Vector search with metadata filter (PowerShell format)
python -m gravixlayer.cli vectors vector search <index-id> --vector '[0.15,0.25,0.35,0.45,0.55]' --top-k 3 --filter '{\"category\":\"test\"}' --include-values

# Vector search without metadata
python -m gravixlayer.cli vectors vector search <index-id> --vector '[0.15,0.25,0.35,0.45,0.55]' --top-k 5 --include-metadata false

# Basic text search
python -m gravixlayer.cli vectors vector search-text <index-id> --query "sample document" --model "baai/bge-large-en-v1.5" --top-k 5

# Text search with filter (PowerShell format)
python -m gravixlayer.cli vectors vector search-text <index-id> --query "document embedding" --model "baai/bge-large-en-v1.5" --top-k 3 --filter '{\"source\":\"cli\"}'
```

### Vector Management
```powershell
# List vectors
python -m gravixlayer.cli vectors vector list <index-id> --ids-only
python -m gravixlayer.cli vectors vector list <index-id>

# Get vector information
python -m gravixlayer.cli vectors vector get <index-id> <vector-id>

# Delete vector
python -m gravixlayer.cli vectors vector delete <index-id> <vector-id>
```

## Complete Workflow Examples

### Example 1: Product Embeddings (PowerShell)
```powershell
# 1. Create index for products
$INDEX_ID = (python -m gravixlayer.cli vectors index create --name "product-catalog" --dimension 1024 --metric cosine --metadata '{\"purpose\":\"product_search\"}' | Select-String "Index ID:" | ForEach-Object { $_.ToString().Split(' ')[-1] })

Write-Host "Created index: $INDEX_ID"

# 2. Add product vectors (PowerShell format)
python -m gravixlayer.cli vectors vector upsert-text $INDEX_ID --text "Wireless bluetooth headphones with noise cancellation" --model "baai/bge-large-en-v1.5" --id "product-1" --metadata '{\"name\":\"Premium_Headphones\",\"category\":\"electronics\",\"price\":299.99}'

python -m gravixlayer.cli vectors vector upsert-text $INDEX_ID --text "Running shoes with advanced cushioning technology" --model "baai/bge-large-en-v1.5" --id "product-2" --metadata '{\"name\":\"Athletic_Shoes\",\"category\":\"sports\",\"price\":129.99}'

# 3. Search for products
Write-Host "Searching for audio products:"
python -m gravixlayer.cli vectors vector search-text $INDEX_ID --query "audio headphones music" --model "baai/bge-large-en-v1.5" --top-k 3

# 4. Filter by category (PowerShell format)
Write-Host "Electronics only:"
python -m gravixlayer.cli vectors vector search-text $INDEX_ID --query "wireless technology" --model "baai/bge-large-en-v1.5" --top-k 2 --filter '{\"category\":\"electronics\"}'

# 5. List all products
python -m gravixlayer.cli vectors vector list $INDEX_ID --ids-only

# 6. Clean up (optional)
# python -m gravixlayer.cli vectors index delete $INDEX_ID
```

### Example 2: Document Search (PowerShell)
```powershell
# 1. Create document index
$DOC_INDEX = (python -m gravixlayer.cli vectors index create --name "document-search" --dimension 1024 --metric cosine | Select-String "Index ID:" | ForEach-Object { $_.ToString().Split(' ')[-1] })

# 2. Add documents (PowerShell format)
python -m gravixlayer.cli vectors vector upsert-text $DOC_INDEX --text "Machine learning algorithms for data analysis and prediction" --model "baai/bge-large-en-v1.5" --id "doc-1" --metadata '{\"title\":\"ML_Guide\",\"author\":\"Data_Scientist\",\"topic\":\"AI\"}'

python -m gravixlayer.cli vectors vector upsert-text $DOC_INDEX --text "Web development with modern JavaScript frameworks" --model "baai/bge-large-en-v1.5" --id "doc-2" --metadata '{\"title\":\"Web_Dev_Guide\",\"author\":\"Frontend_Dev\",\"topic\":\"Programming\"}'

# 3. Semantic search
python -m gravixlayer.cli vectors vector search-text $DOC_INDEX --query "artificial intelligence and data science" --model "baai/bge-large-en-v1.5" --top-k 5

# 4. Get document metadata
python -m gravixlayer.cli vectors vector get $DOC_INDEX doc-1

# 5. Delete specific document
python -m gravixlayer.cli vectors vector delete $DOC_INDEX doc-2

# 6. Verify deletion
python -m gravixlayer.cli vectors vector list $DOC_INDEX --ids-only
```

## PowerShell-Specific Tips

### 1. JSON Formatting Rules
- **Use escaped double quotes**: `'{\"key\":\"value\"}'`
- **Avoid spaces in values**: Use underscores instead: `\"Product_embeddings\"`
- **For complex JSON**: Use `--metadata-file` or `--metadata-b64`

### 2. Variable Extraction
```powershell
# Extract index ID from command output
$INDEX_ID = (python -m gravixlayer.cli vectors index create --name "test" --dimension 768 --metric cosine | Select-String "Index ID:" | ForEach-Object { $_.ToString().Split(' ')[-1] })
```

### 3. Alternative Methods for Complex JSON

#### Method 1: Metadata File
```powershell
# Create metadata.json
@"
{
  "description": "Complex metadata with spaces",
  "tags": ["test", "production"],
  "config": {
    "nested": true,
    "values": [1, 2, 3]
  }
}
"@ | Out-File -FilePath metadata.json -Encoding UTF8

# Use in command
python -m gravixlayer.cli vectors index create --name "complex-index" --dimension 768 --metric cosine --metadata-file metadata.json
```

#### Method 2: Base64 Encoding
```powershell
# Encode JSON to base64
$metadata = @{
    description = "Complex metadata with spaces"
    tags = @("test", "production")
    config = @{
        nested = $true
        values = @(1, 2, 3)
    }
}
$json = $metadata | ConvertTo-Json -Compress
$bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
$base64 = [System.Convert]::ToBase64String($bytes)

# Use in command
python -m gravixlayer.cli vectors index create --name "b64-index" --dimension 768 --metric cosine --metadata-b64 $base64
```

## Troubleshooting

### Common PowerShell Issues
1. **JSON parsing errors**: Use escaped quotes `'{\"key\":\"value\"}'`
2. **Spaces in JSON values**: Replace with underscores or use metadata file
3. **Variable extraction**: Use `Select-String` and `ForEach-Object`

### Error Messages
The CLI now provides PowerShell-specific examples in error messages to help with proper formatting.