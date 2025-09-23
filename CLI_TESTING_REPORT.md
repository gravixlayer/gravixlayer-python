# GravixLayer CLI Testing Report & Fixes

## Test Results Summary

| Test Case | Status | Issue | Solution |
|-----------|--------|-------|----------|
| Basic index creation | ✅ PASS | None | Works correctly |
| Metadata from file | ✅ PASS | None | Works correctly |
| Base64 metadata | ✅ PASS | None | Works correctly |
| Simple JSON metadata | ❌ FAIL → ✅ FIXED | PowerShell quote handling | Use escaped quotes |
| Delete protection | ✅ PASS | None | Works correctly |
| Vector upsert | ✅ PASS | None | Works correctly |
| Search with filter | ✅ PASS | None | Works correctly |

## Issues Found & Fixed

### Issue 1: PowerShell JSON Quote Handling
**Problem**: Commands with single quotes around JSON fail in PowerShell
```powershell
# FAILS in PowerShell
--metadata '{"type":"test"}'
```

**Root Cause**: PowerShell strips quotes differently than bash/cmd

**Solution**: Use escaped double quotes in PowerShell
```powershell
# WORKS in PowerShell
--metadata '{\"type\":\"test\"}'
```

## Working Commands for PowerShell

### Prerequisites
```powershell
$env:GRAVIXLAYER_API_KEY="your_api_key_here"
```

### Index Management (FIXED)
```powershell
# Basic index creation (works)
python -m gravixlayer.cli vectors index create --name "my-embeddings" --dimension 1024 --metric cosine

# Index with metadata (FIXED - use escaped quotes)
python -m gravixlayer.cli vectors index create --name "product-embeddings" --dimension 1536 --metric cosine --metadata '{\"description\":\"Product embeddings\",\"model\":\"text-embedding-ada-002\"}'

# Index with metadata from file (works)
python -m gravixlayer.cli vectors index create --name "product-embeddings-file" --dimension 1536 --metric cosine --metadata-file metadata.json

# Index with base64 metadata (works)
python -m gravixlayer.cli vectors index create --name "product-embeddings-b64" --dimension 768 --metric cosine --metadata-b64 eyJkZXNjcmlwdGlvbiI6ICJQcm9kdWN0IGVtYmVkZGluZ3MiLCAibW9kZWwiOiAidGV4dC1lbWJlZGRpbmctYWRhLTAwMiJ9

# Delete protection (works)
python -m gravixlayer.cli vectors index update <index-id> --delete-protection true
python -m gravixlayer.cli vectors index update <index-id> --delete-protection false
```

### Vector Operations (FIXED)
```powershell
# Vector upsert with metadata (FIXED)
python -m gravixlayer.cli vectors vector upsert-text <index-id> --text "Sample text" --model "baai/bge-large-en-v1.5" --id "vec-1" --metadata '{\"source\":\"cli\",\"type\":\"test\"}'

# Search with filter (FIXED)
python -m gravixlayer.cli vectors vector search-text <index-id> --query "search term" --model "baai/bge-large-en-v1.5" --top-k 5 --filter '{\"category\":\"test\"}'
```

## Code Fixes Required

The CLI code is working correctly, but the documentation needs updates for PowerShell compatibility.

### Fix 1: Update Documentation
The examples in **CLI_COMMANDS_REFERENCE.md** and **vector_cli_examples.md** need PowerShell-specific versions.

### Fix 2: Enhanced Error Messages
The error messages in **cli.py** should include PowerShell-specific examples.