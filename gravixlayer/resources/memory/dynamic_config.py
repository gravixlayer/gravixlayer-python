"""
Dynamic Configuration Manager for GravixLayer Memory System
Handles switching between different embedding models, cloud configurations, and databases
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class CloudConfig:
    """Cloud configuration settings"""
    cloud_provider: str = "AWS"
    region: str = "us-east-1"
    index_type: str = "serverless"
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "cloud_provider": self.cloud_provider,
            "region": self.region,
            "index_type": self.index_type
        }


@dataclass
class MemoryConfig:
    """Complete memory system configuration"""
    embedding_model: str = "baai/bge-large-en-v1.5"
    inference_model: str = "mistralai/mistral-nemo-instruct-2407"
    database_name: str = "gravixlayer_memories"
    cloud_config: CloudConfig = field(default_factory=CloudConfig)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "embedding_model": self.embedding_model,
            "inference_model": self.inference_model,
            "database_name": self.database_name,
            "cloud_config": self.cloud_config.to_dict()
        }


class DynamicMemoryConfig:
    """
    Dynamic configuration manager for memory system
    Supports runtime switching of models, databases, and cloud settings
    """
    
    def __init__(self):
        # System defaults
        self.defaults = MemoryConfig()
        
        # Current active configuration
        self.current = MemoryConfig()
        
        # Available model options
        self.available_embedding_models = [
            "baai/bge-large-en-v1.5",      # 1024 dim
            "microsoft/multilingual-e5-large",  # 1536 dim
            "multilingual-e5-large",        # 1536 dim
            "nomic-ai/nomic-embed-text:v1.5",   # 768 dim
        ]
        
        self.available_inference_models = [
            "mistralai/mistral-nemo-instruct-2407",
            "meta-llama/llama-3.1-8b-instruct",
            "meta-llama/llama-3.1-70b-instruct",
            "anthropic/claude-3-haiku-20240307",
            "openai/gpt-4o-mini",
        ]
        
        self.available_cloud_providers = ["AWS", "GCP", "Azure"]
        self.available_regions = {
            "AWS": ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"],
            "GCP": ["us-central1", "europe-west1", "asia-southeast1"],
            "Azure": ["eastus", "westus2", "westeurope", "southeastasia"]
        }
    
    def get_embedding_dimension(self, model: str) -> int:
        """Get embedding dimension for a model"""
        dimensions = {
            # Server-side actual dimensions (what the server actually produces)
            "microsoft/multilingual-e5-large": 1024,  # Server maps this to baai/bge-large-en-v1.5
            "multilingual-e5-large": 1024,
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "baai/bge-large-en-v1.5": 1024,
            "baai/bge-base-en-v1.5": 768,
            "baai/bge-small-en-v1.5": 384,
            "all-MiniLM-L6-v2": 384,
            "sentence-transformers/all-MiniLM-L6-v2": 384,
            "all-mpnet-base-v2": 768,
            "embed-english-v3.0": 1024,
            "embed-english-light-v3.0": 384,
            "nomic-embed-text-v1": 768,
            "nomic-embed-text-v1.5": 768,
            "nomic-ai/nomic-embed-text:v1.5": 768
        }
        return dimensions.get(model, 1024)  # Default to 1024 if model not found
    
    def switch_embedding_model(self, model: str) -> bool:
        """Switch to a different embedding model"""
        if model in self.available_embedding_models:
            self.current.embedding_model = model
            print(f"✅ Switched embedding model to: {model}")
            print(f"📏 Dimension: {self.get_embedding_dimension(model)}")
            return True
        else:
            print(f"❌ Unknown embedding model: {model}")
            print(f"Available models: {self.available_embedding_models}")
            return False
    
    def switch_inference_model(self, model: str) -> bool:
        """Switch to a different inference model"""
        if model in self.available_inference_models:
            self.current.inference_model = model
            print(f"✅ Switched inference model to: {model}")
            return True
        else:
            print(f"❌ Unknown inference model: {model}")
            print(f"Available models: {self.available_inference_models}")
            return False
    
    def switch_database(self, database_name: str) -> bool:
        """Switch to a different database"""
        self.current.database_name = database_name
        print(f"✅ Switched to database: {database_name}")
        return True
    
    def switch_cloud_config(self, provider: Optional[str] = None, 
                           region: Optional[str] = None,
                           index_type: Optional[str] = None) -> bool:
        """Switch cloud configuration"""
        if provider:
            if provider in self.available_cloud_providers:
                self.current.cloud_config.cloud_provider = provider
                # Auto-switch to default region for provider if current region is invalid
                if region is None and self.current.cloud_config.region not in self.available_regions.get(provider, []):
                    self.current.cloud_config.region = self.available_regions[provider][0]
                print(f"✅ Switched cloud provider to: {provider}")
            else:
                print(f"❌ Unknown cloud provider: {provider}")
                return False
        
        if region:
            current_provider = self.current.cloud_config.cloud_provider
            if region in self.available_regions.get(current_provider, []):
                self.current.cloud_config.region = region
                print(f"✅ Switched region to: {region}")
            else:
                print(f"❌ Invalid region {region} for provider {current_provider}")
                return False
        
        if index_type:
            self.current.cloud_config.index_type = index_type
            print(f"✅ Switched index type to: {index_type}")
        
        return True
    
    def reset_to_defaults(self):
        """Reset all configuration to defaults"""
        self.current = MemoryConfig()
        print("🔄 Reset to default configuration")
    
    def get_current_config(self) -> Dict[str, Any]:
        """Get current configuration as dictionary"""
        return self.current.to_dict()
    
    def print_current_config(self):
        """Print current configuration in a readable format"""
        print("\n📋 Current Memory Configuration:")
        print(f"  🤖 Embedding Model: {self.current.embedding_model}")
        print(f"  📏 Embedding Dimension: {self.get_embedding_dimension(self.current.embedding_model)}")
        print(f"  🧠 Inference Model: {self.current.inference_model}")
        print(f"  🗄️  Database: {self.current.database_name}")
        print(f"  ☁️  Cloud Provider: {self.current.cloud_config.cloud_provider}")
        print(f"  🌍 Region: {self.current.cloud_config.region}")
        print(f"  📊 Index Type: {self.current.cloud_config.index_type}")
    
    def print_available_options(self):
        """Print all available configuration options"""
        print("\n🔧 Available Configuration Options:")
        print(f"\n🤖 Embedding Models:")
        for model in self.available_embedding_models:
            dim = self.get_embedding_dimension(model)
            current = " (current)" if model == self.current.embedding_model else ""
            print(f"  - {model} ({dim} dim){current}")
        
        print(f"\n🧠 Inference Models:")
        for model in self.available_inference_models:
            current = " (current)" if model == self.current.inference_model else ""
            print(f"  - {model}{current}")
        
        print(f"\n☁️  Cloud Providers:")
        for provider in self.available_cloud_providers:
            current = " (current)" if provider == self.current.cloud_config.cloud_provider else ""
            print(f"  - {provider}: {self.available_regions[provider]}{current}")