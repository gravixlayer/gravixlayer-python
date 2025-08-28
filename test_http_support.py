#!/usr/bin/env python3
"""
Test script to demonstrate HTTP support across all GravixLayer features.
"""

import os
import asyncio
from gravixlayer import GravixLayer
from gravixlayer.types.async_client import AsyncGravixLayer

def test_sync_http_support():
    """Test synchronous client with HTTP support"""
    print("=== Testing Sync Client HTTP Support ===")
    
    try:
        client = GravixLayer(
            api_key="test-key",
            base_url="http://localhost:8080/v1/inference"
        )
        print(f"✓ Sync client created with HTTP URL: {client.base_url}")
        print(f"✓ User agent: {client.user_agent}")
        
    except Exception as e:
        print(f"✗ Error creating sync client: {e}")

async def test_async_http_support():
    """Test asynchronous client with HTTP support"""
    print("\n=== Testing Async Client HTTP Support ===")
    
    try:
        client = AsyncGravixLayer(
            api_key="test-key",
            base_url="http://localhost:8080/v1/inference"
        )
        print(f"✓ Async client created with HTTP URL: {client.base_url}")
        print(f"✓ User agent: {client.user_agent}")
        
    except Exception as e:
        print(f"✗ Error creating async client: {e}")

def test_default_behavior():
    """Test that default behavior now uses HTTP"""
    print("\n=== Testing Default HTTP Behavior ===")
    
    try:
        sync_client = GravixLayer(api_key="test-key")
        print(f"✓ Sync client default URL: {sync_client.base_url}")
        assert sync_client.base_url.startswith("http://"), "Default should be HTTP"
        
        async_client = AsyncGravixLayer(api_key="test-key")
        print(f"✓ Async client default URL: {async_client.base_url}")
        assert async_client.base_url.startswith("http://"), "Default should be HTTP"
        
        print("✓ Both clients now default to HTTP as requested")
        
    except Exception as e:
        print(f"✗ Error testing defaults: {e}")

def main():
    """Run all HTTP support tests"""
    print("GravixLayer SDK - HTTP Support Test")
    print("=" * 50)
    
    test_sync_http_support()
    asyncio.run(test_async_http_support())
    test_default_behavior()
    
    print("\n" + "=" * 50)
    print("HTTP Support Test Complete!")

if __name__ == "__main__":
    main()