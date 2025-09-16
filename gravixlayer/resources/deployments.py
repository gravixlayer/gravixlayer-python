from typing import List, Dict, Any
from ..types.deployments import DeploymentCreate, Deployment, DeploymentList, DeploymentResponse

class Deployments:
    def __init__(self, client):
        self.client = client

    def create(
        self,
        deployment_name: str,
        model_name: str,
        gpu_model: str,
        gpu_count: int = 1,
        min_replicas: int = 1,
        max_replicas: int = 1,
        hw_type: str = "dedicated"
    ) -> DeploymentResponse:
        """Create a new deployment"""
        data = {
            "deployment_name": deployment_name,
            "hw_type": hw_type,
            "gpu_model": gpu_model,
            "gpu_count": gpu_count,
            "min_replicas": min_replicas,
            "max_replicas": max_replicas,
            "model_name": model_name
        }
        
        # Use a different base URL for deployments API
        original_base_url = self.client.base_url
        self.client.base_url = self.client.base_url.replace("/v1/inference", "/v1/deployments")
        
        try:
            response = self.client._make_request("POST", "create", data=data)
            result = response.json()
            return DeploymentResponse(**result)
        finally:
            self.client.base_url = original_base_url

    def list(self) -> List[Deployment]:
        """List all deployments"""
        # Use a different base URL for deployments API
        original_base_url = self.client.base_url
        self.client.base_url = self.client.base_url.replace("/v1/inference", "/v1/deployments")
        
        try:
            response = self.client._make_request("GET", "list")
            deployments_data = response.json()
            

            
            # Handle different response formats
            if isinstance(deployments_data, list):
                return [Deployment(**deployment) for deployment in deployments_data]
            elif isinstance(deployments_data, dict) and 'deployments' in deployments_data:
                return [Deployment(**deployment) for deployment in deployments_data['deployments']]
            elif isinstance(deployments_data, dict) and not deployments_data:
                # Empty dict response means no deployments
                return []
            else:
                # If it's a different format, return empty list and log the issue
                print(f"Unexpected response format: {type(deployments_data)}, content: {deployments_data}")
                return []
        finally:
            self.client.base_url = original_base_url

    def delete(self, deployment_id: str) -> Dict[str, Any]:
        """Delete a deployment by ID"""
        # Use a different base URL for deployments API
        original_base_url = self.client.base_url
        self.client.base_url = self.client.base_url.replace("/v1/inference", "/v1/deployments")
        
        try:
            response = self.client._make_request("DELETE", f"delete/{deployment_id}")
            return response.json()
        finally:
            self.client.base_url = original_base_url