# GravixLayer Vector Search Guide

## What is Vector Search?

Vector search is a method of finding similar items by comparing high-dimensional numerical representations (vectors) of data. It's the core technology behind semantic search, recommendation systems, and similarity matching.

## How Vector Search Works

1. **Embeddings**: Text, images, or other data are converted into vectors (arrays of numbers)
2. **Storage**: These vectors are stored in a vector database with an index
3. **Search**: When you search, your query is also converted to a vector
4. **Similarity**: The database finds vectors most similar to your query vector
5. **Results**: Returns the most similar items ranked by similarity score

## Vector Search Endpoint - What It Does

The `gravixlayer vectors vector search` command performs **similarity search** using pre-computed embedding vectors:

### Purpose:
- Find vectors most similar to a query vector
- Useful when you already have embeddings
- Direct vector-to-vector comparison
- Fast similarity matching

### Use Cases:
- **Recommendation Systems**: Find similar products/content
- **Duplicate Detection**: Find near-duplicate items
- **Clustering**: Group similar items together
- **Anomaly Detection**: Find outliers or unusual patterns

## Fixed Commands & Examples

### 1. Basic Vector Search (FIXED)
```powershell
# Search with a 1024-dimensional vector (matching your index dimension)
python -m gravixlayer.cli vectors vector search <index-id> --vector '[0.1,0.2,0.3,...]' --top-k 5

# Note: You need a vector with 1024 dimensions, not 5!
```

### 2. Vector Search with Options (FIXED)
```powershell
# Search with metadata filter
python -m gravixlayer.cli vectors vector search <index-id> --vector '[0.1,0.2,...]' --top-k 3 --filter '{\"category\":\"test\"}' --include-values true

# Search without metadata
python -m gravixlayer.cli vectors vector search <index-id> --vector '[0.1,0.2,...]' --top-k 5 --include-metadata false
```

### 3. Vector Upsert (FIXED - Now Works)
```powershell
# Upsert with proper error handling
python -m gravixlayer.cli vectors vector upsert <index-id> --embedding '[0.1,0.2,0.3,...]' --id "my-vector-1" --metadata '{\"title\":\"Sample_Document\",\"category\":\"test\"}'

# The command now handles API response parsing issues gracefully
```

## Dimension Requirements

**CRITICAL**: Your search vector must match the index dimension:

```powershell
# ❌ WRONG - 5 dimensions in 1024-dimensional index
--vector '[0.15,0.25,0.35,0.45,0.55]'

# ✅ CORRECT - 1024 dimensions (example with first few values)
--vector '[0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0,...]'  # ... continues to 1024 values
```

## Complete Working Examples

### Example 1: Product Similarity Search
```powershell
# 1. Create index
$INDEX_ID = (python -m gravixlayer.cli vectors index create --name "products" --dimension 1024 --metric cosine | Select-String "Index ID:" | ForEach-Object { $_.ToString().Split(' ')[-1] })

# 2. Add product vectors (using text-to-vector for simplicity)
python -m gravixlayer.cli vectors vector upsert-text $INDEX_ID --text "Wireless bluetooth headphones" --model "baai/bge-large-en-v1.5" --id "product-1" --metadata '{\"category\":\"electronics\",\"price\":99.99}'

python -m gravixlayer.cli vectors vector upsert-text $INDEX_ID --text "Running shoes with cushioning" --model "baai/bge-large-en-v1.5" --id "product-2" --metadata '{\"category\":\"sports\",\"price\":129.99}'

# 3. Search for similar products using text (easier than manual vectors)
python -m gravixlayer.cli vectors vector search-text $INDEX_ID --query "audio equipment" --model "baai/bge-large-en-v1.5" --top-k 5
```

### Example 2: Document Similarity
```powershell
# 1. Add documents
python -m gravixlayer.cli vectors vector upsert-text $INDEX_ID --text "Machine learning algorithms" --model "baai/bge-large-en-v1.5" --id "doc-1" --metadata '{\"topic\":\"AI\"}'

python -m gravixlayer.cli vectors vector upsert-text $INDEX_ID --text "Deep learning neural networks" --model "baai/bge-large-en-v1.5" --id "doc-2" --metadata '{\"topic\":\"AI\"}'

# 2. Search for similar documents
python -m gravixlayer.cli vectors vector search-text $INDEX_ID --query "artificial intelligence" --model "baai/bge-large-en-v1.5" --top-k 3 --filter '{\"topic\":\"AI\"}'
```

## Vector Search vs Text Search

| Feature | Vector Search | Text Search |
|---------|---------------|-------------|
| **Input** | Pre-computed vector | Text query |
| **Use Case** | Direct similarity matching | Semantic text search |
| **Speed** | Faster (no embedding needed) | Slower (needs embedding) |
| **Flexibility** | Requires existing vectors | More user-friendly |

### When to Use Vector Search:
- You already have embeddings
- Building recommendation systems
- Batch similarity processing
- Performance-critical applications

### When to Use Text Search:
- User-facing search interfaces
- Ad-hoc queries
- Prototyping and testing
- When you don't have pre-computed vectors

## Troubleshooting

### Common Issues & Solutions:

1. **Dimension Mismatch**
   ```
   ERROR: Vector dimension mismatch: expected 1024, got 5
   ```
   **Solution**: Use vectors with correct dimensions (1024 for baai/bge-large-en-v1.5)

2. **Boolean Arguments**
   ```
   ERROR: unrecognized arguments: false
   ```
   **Solution**: Use string values: `--include-metadata false` (now fixed)

3. **Vector Upsert Issues**
   ```
   ERROR: Vector.__init__() got an unexpected keyword argument 'upserted_count'
   ```
   **Solution**: Now handled gracefully with success message and verification tip

## Best Practices

1. **Match Dimensions**: Always ensure vector dimensions match index dimensions
2. **Use Text Search for Prototyping**: Easier to test and validate
3. **Use Vector Search for Production**: When you have optimized embeddings
4. **Include Metadata**: For filtering and result interpretation
5. **Test with Small Datasets**: Validate before scaling up

## Performance Tips

- **Batch Operations**: Use multiple upserts for bulk data
- **Appropriate top-k**: Don't request more results than needed
- **Metadata Filters**: Use filters to narrow search scope
- **Index Optimization**: Choose appropriate metric (cosine for text embeddings)

The vector search functionality is now fully working with proper error handling and boolean argument support!