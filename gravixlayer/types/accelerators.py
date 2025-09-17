from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, computed_field, ConfigDict, model_validator

class Accelerator(BaseModel):
    """Represents a GPU/accelerator specification"""
    model_config = ConfigDict(populate_by_name=True, extra='allow')
    
    # Primary fields from /v1/accelerators endpoint
    gpu_id: Optional[str] = None
    pricing: Optional[float] = None
    gpu_model: Optional[str] = None
    gpu_link: Optional[str] = None
    gpu_memory: Optional[int] = None
    status: Optional[str] = None
    updated_at: Optional[str] = None
    
    # Legacy fields for backward compatibility
    id: Optional[str] = None
    provider: Optional[str] = None
    accelerator_id: Optional[str] = None
    hw_model: Optional[str] = None
    hw_link: Optional[str] = None
    hw_memory: Optional[int] = None
    memory_gb: Optional[int] = None
    gpu_type: Optional[str] = None
    hardware_string: Optional[str] = None
    created_at: Optional[str] = None
    
    @model_validator(mode='before')
    @classmethod
    def handle_gpu_id_alias(cls, data: Any) -> Any:
        """Handle the gpu_id -> accelerator_id mapping"""
        if isinstance(data, dict):
            # If gpu_id exists but accelerator_id doesn't, copy it over
            if 'gpu_id' in data and 'accelerator_id' not in data:
                data['accelerator_id'] = data['gpu_id']
        return data
    
    @computed_field
    @property
    def name(self) -> str:
        """Generate a friendly name from the GPU model"""
        if self.gpu_model:
            # Extract readable name from gpu_model like "NVIDIA_T4_16GB" -> "NVIDIA T4 16GB"
            return self.gpu_model.replace("_", " ")
        elif self.gpu_id:
            return self.gpu_id.replace("_", " ")
        elif self.accelerator_id:
            return self.accelerator_id.replace("_", " ")
        else:
            return "unknown"
    
    @computed_field
    @property
    def hardware_string_computed(self) -> str:
        """Generate hardware string in the expected format"""
        # Use existing hardware_string if available, otherwise compute it
        if self.hardware_string:
            return self.hardware_string
            
        # Primary computation using new fields
        if self.provider and self.gpu_model and self.gpu_memory and self.gpu_link:
            provider_lower = self.provider.lower()
            # Extract model name from gpu_model (e.g., "T4" from "NVIDIA_T4_16GB")
            model_parts = self.gpu_model.split("_")
            if len(model_parts) >= 2:
                model_lower = model_parts[1].lower()  # "T4"
            else:
                model_lower = self.gpu_model.lower()
            memory_str = f"{self.gpu_memory}gb"
            link_lower = self.gpu_link.lower()
            return f"{provider_lower}-{model_lower}-{memory_str}-{link_lower}_1"
        
        # Fallback computation using legacy fields
        elif self.provider and self.hw_model and self.hw_memory and self.hw_link:
            provider_lower = self.provider.lower()
            model_lower = self.hw_model.lower()
            memory_str = f"{self.hw_memory}gb"
            link_lower = self.hw_link.lower()
            return f"{provider_lower}-{model_lower}-{memory_str}-{link_lower}_1"
        
        # Final fallback - use ID
        id_to_use = self.id or self.accelerator_id or self.gpu_id or "unknown"
        return id_to_use.lower().replace("_", "-")
    
    @computed_field
    @property
    def memory(self) -> str:
        """Format memory as string"""
        if self.gpu_memory:
            return f"{self.gpu_memory}GB"
        elif self.hw_memory:
            return f"{self.hw_memory}GB"
        elif self.memory_gb:
            return f"{self.memory_gb}GB"
        else:
            return "N/A"
    
    @computed_field
    @property
    def gpu_type_computed(self) -> str:
        """Get GPU type (model)"""
        if self.gpu_model:
            return self.gpu_model
        elif self.gpu_type:
            return self.gpu_type
        elif self.hw_model:
            return self.hw_model.lower()
        else:
            id_to_use = self.gpu_id or self.id or self.accelerator_id or "unknown"
            return id_to_use.lower()
    
    @computed_field
    @property
    def gpu_type_short(self) -> str:
        """Extract short GPU type from model (e.g., 'T4' from 'NVIDIA_T4_16GB')"""
        if self.gpu_model:
            parts = self.gpu_model.split("_")
            if len(parts) >= 2:
                return parts[1]  # "T4" from ["NVIDIA", "T4", "16GB"]
            return self.gpu_model
        return "Unknown"
    
    @computed_field
    @property
    def use_case(self) -> str:
        """Determine use case based on memory and model"""
        memory = self.gpu_memory or self.hw_memory or self.memory_gb or 0
        model = (self.gpu_model or self.hw_model or self.gpu_type or "").lower()
        
        if memory <= 16:
            return "Small models, development"
        elif memory <= 32:
            return "Medium models"
        elif memory <= 24 and "rtx" in model:
            return "Development, small production"
        else:
            return "Large models, production"

class AcceleratorList(BaseModel):
    """Response model for accelerator list"""
    accelerators: List[Accelerator]