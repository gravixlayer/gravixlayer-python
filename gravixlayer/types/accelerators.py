from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, computed_field, ConfigDict, model_validator

class Accelerator(BaseModel):
    """Represents a GPU/accelerator specification"""
    model_config = ConfigDict(populate_by_name=True, extra='allow')
    
    # Core fields - make them all optional to handle various API response formats
    accelerator_id: Optional[str] = None
    gpu_id: Optional[str] = None
    pricing: Optional[float] = None
    hw_model: Optional[str] = None
    hw_link: Optional[str] = None
    hw_memory: Optional[int] = None
    provider: Optional[str] = None
    status: Optional[str] = None
    updated_at: Optional[str] = None
    
    # Additional fields that might be in the API response
    gpu_model: Optional[str] = None
    memory_gb: Optional[int] = None
    gpu_type: Optional[str] = None
    hardware_string: Optional[str] = None
    
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
        """Generate a friendly name from the accelerator_id"""
        id_to_use = self.accelerator_id or self.gpu_id or "unknown"
        return id_to_use.replace("_", " ")
    
    @computed_field
    @property
    def hardware_string_computed(self) -> str:
        """Generate hardware string in the expected format"""
        # Use existing hardware_string if available, otherwise compute it
        if self.hardware_string:
            return self.hardware_string
            
        # Fallback computation if we have the required fields
        if self.provider and self.hw_model and self.hw_memory and self.hw_link:
            provider_lower = self.provider.lower()
            model_lower = self.hw_model.lower()
            memory_str = f"{self.hw_memory}gb"
            link_lower = self.hw_link.lower()
            return f"{provider_lower}-{model_lower}-{memory_str}-{link_lower}_1"
        
        # Final fallback - use accelerator_id or gpu_id
        id_to_use = self.accelerator_id or self.gpu_id or "unknown"
        return id_to_use.lower().replace("_", "-")
    
    @computed_field
    @property
    def memory(self) -> str:
        """Format memory as string"""
        if self.hw_memory:
            return f"{self.hw_memory}GB"
        elif self.memory_gb:
            return f"{self.memory_gb}GB"
        else:
            return "N/A"
    
    @computed_field
    @property
    def gpu_type_computed(self) -> str:
        """Get GPU type (model)"""
        if self.gpu_type:
            return self.gpu_type
        elif self.hw_model:
            return self.hw_model.lower()
        elif self.gpu_model:
            return self.gpu_model.lower()
        else:
            id_to_use = self.accelerator_id or self.gpu_id or "unknown"
            return id_to_use.lower()
    
    @computed_field
    @property
    def use_case(self) -> str:
        """Determine use case based on memory and model"""
        memory = self.hw_memory or self.memory_gb or 0
        model = (self.hw_model or self.gpu_model or self.gpu_type or "").lower()
        
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