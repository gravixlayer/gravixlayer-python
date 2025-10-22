#!/usr/bin/env python3
"""
Test script to verify both sync and async memory implementations work correctly
"""
import os
import asyncio
from gravixlayer import GravixLayer, AsyncGravixLayer


def test_sync_memory():
    """Test synchronous memory functionality"""
    print("🔄 Testing Synchronous Memory...")
    
    try:
        # Initialize sync client
        client = GravixLayer()
        memory = client.memory
        
        print("✅ Sync client and memory initialized successfully")
        
        # Test configuration methods
        config = memory.get_current_configuration()
        print(f"✅ Current config: {config['embedding_model']}, {config['index_name']}")
        
        # Test basic memory operations
        user_id = "test_sync_user"
        
        # Add memory
        result = memory.add("I love pizza", user_id)
        print(f"✅ Added memory: {result['results'][0]['memory']}")
        
        # Search memory
        search_result = memory.search("food", user_id, limit=5)
        print(f"✅ Search found {len(search_result['results'])} memories")
        
        # Get all memories
        all_memories = memory.get_all(user_id, limit=10)
        print(f"✅ Retrieved {len(all_memories['results'])} total memories")
        
        # Test configuration switching
        memory.switch_configuration(embedding_model="microsoft/multilingual-e5-large")
        new_config = memory.get_current_configuration()
        print(f"✅ Switched to: {new_config['embedding_model']}")
        
        # Reset to defaults
        memory.reset_to_defaults()
        print("✅ Reset to defaults")
        
        print("🎉 Synchronous memory test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Sync memory test failed: {e}")
        return False


async def test_async_memory():
    """Test asynchronous memory functionality"""
    print("\n🔄 Testing Asynchronous Memory...")
    
    try:
        # Initialize async client
        client = AsyncGravixLayer()
        memory = client.memory
        
        print("✅ Async client and memory initialized successfully")
        
        # Test configuration methods
        config = memory.get_current_configuration()
        print(f"✅ Current config: {config['embedding_model']}, {config['index_name']}")
        
        # Test basic memory operations
        user_id = "test_async_user"
        
        # Add memory
        result = await memory.add("I love sushi", user_id)
        print(f"✅ Added memory: {result['results'][0]['memory']}")
        
        # Search memory
        search_result = await memory.search("food", user_id, limit=5)
        print(f"✅ Search found {len(search_result['results'])} memories")
        
        # Get all memories
        all_memories = await memory.get_all(user_id, limit=10)
        print(f"✅ Retrieved {len(all_memories['results'])} total memories")
        
        # Test configuration switching
        memory.switch_configuration(embedding_model="microsoft/multilingual-e5-large")
        new_config = memory.get_current_configuration()
        print(f"✅ Switched to: {new_config['embedding_model']}")
        
        # Reset to defaults
        memory.reset_to_defaults()
        print("✅ Reset to defaults")
        
        # Test advanced operations
        available_indexes = await memory.list_available_indexes()
        print(f"✅ Found {len(available_indexes)} available indexes")
        
        print("🎉 Asynchronous memory test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Async memory test failed: {e}")
        return False


def test_memory_compatibility():
    """Test that both sync and async memory have the same interface"""
    print("\n🔄 Testing Memory Interface Compatibility...")
    
    try:
        # Initialize both clients
        sync_client = GravixLayer()
        async_client = AsyncGravixLayer()
        
        sync_memory = sync_client.memory
        async_memory = async_client.memory
        
        # Check that both have the same methods
        expected_methods = [
            'add', 'search', 'get', 'get_all', 'update', 'delete', 'delete_all',
            'switch_configuration', 'get_current_configuration', 'reset_to_defaults',
            'list_available_indexes', 'switch_index'
        ]
        
        sync_methods = [method for method in dir(sync_memory) if not method.startswith('_')]
        async_methods = [method for method in dir(async_memory) if not method.startswith('_')]
        
        print(f"✅ Sync memory methods: {len(sync_methods)}")
        print(f"✅ Async memory methods: {len(async_methods)}")
        
        # Check for expected methods
        missing_sync = [method for method in expected_methods if not hasattr(sync_memory, method)]
        missing_async = [method for method in expected_methods if not hasattr(async_memory, method)]
        
        if missing_sync:
            print(f"⚠️  Sync memory missing methods: {missing_sync}")
        else:
            print("✅ Sync memory has all expected methods")
            
        if missing_async:
            print(f"⚠️  Async memory missing methods: {missing_async}")
        else:
            print("✅ Async memory has all expected methods")
        
        print("🎉 Memory interface compatibility test completed!")
        return len(missing_sync) == 0 and len(missing_async) == 0
        
    except Exception as e:
        print(f"❌ Compatibility test failed: {e}")
        return False


async def main():
    """Run all tests"""
    print("🚀 Starting Memory Implementation Tests...")
    print("=" * 60)
    
    # Test sync memory
    sync_success = test_sync_memory()
    
    # Test async memory
    async_success = await test_async_memory()
    
    # Test compatibility
    compat_success = test_memory_compatibility()
    
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")
    print(f"   Sync Memory: {'✅ PASS' if sync_success else '❌ FAIL'}")
    print(f"   Async Memory: {'✅ PASS' if async_success else '❌ FAIL'}")
    print(f"   Compatibility: {'✅ PASS' if compat_success else '❌ FAIL'}")
    
    if sync_success and async_success and compat_success:
        print("\n🎉 All tests passed! Both sync and async memory implementations are working correctly.")
        return True
    else:
        print("\n❌ Some tests failed. Please check the implementation.")
        return False


if __name__ == "__main__":
    # Set a dummy API key for testing (if not already set)
    if not os.environ.get("GRAVIXLAYER_API_KEY"):
        os.environ["GRAVIXLAYER_API_KEY"] = "test-key-for-interface-testing"
    
    success = asyncio.run(main())
    exit(0 if success else 1)