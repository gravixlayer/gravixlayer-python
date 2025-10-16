from typing import List, Optional, Union, BinaryIO
from dataclasses import dataclass

@dataclass
class FileObject:
    """Represents a file object in the GravixLayer File Management API."""
    id: str
    object: str = "file"
    bytes: int = 0
    created_at: int = 0
    filename: str = ""
    purpose: str = ""
    expires_after: Optional[int] = None
    
    def model_dump(self):
        """Convert to dictionary for JSON serialization ."""
        result = {
            "id": self.id,
            "object": self.object,
            "bytes": self.bytes,
            "created_at": self.created_at,
            "filename": self.filename,
            "purpose": self.purpose
        }
        if self.expires_after is not None:
            result["expires_after"] = self.expires_after
        return result

@dataclass
class FileUploadResponse:
    """Response from file upload API."""
    message: str
    file_name: str
    purpose: str
    
    def model_dump(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "message": self.message,
            "file_name": self.file_name,
            "purpose": self.purpose
        }

@dataclass
class FileListResponse:
    """Response from list files API."""
    data: List[FileObject]
    
    def __post_init__(self):
        if self.data is None:
            self.data = []
    
    def model_dump(self):
        """Convert to dictionary for JSON serialization ."""
        return {
            "data": [file_obj.model_dump() for file_obj in self.data]
        }

@dataclass
class FileDeleteResponse:
    """Response from file delete API."""
    message: str
    file_id: str
    file_name: str
    
    def model_dump(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "message": self.message,
            "file_id": self.file_id,
            "file_name": self.file_name
        }

# Valid file purposes as defined in the API
FILE_PURPOSES = [
    "assistants",
    "batch", 
    "batch_output",
    "fine-tune",
    "vision",
    "user_data",
    "evals"
]