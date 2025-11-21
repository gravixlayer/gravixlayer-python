from typing import List, Dict, Any
from ..types.deployments import DeploymentCreate, Deployment, DeploymentList, DeploymentResponse
from ..types.accelerators import Accelerator


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
        hw_type: str = "dedicated",
        auto_retry: bool = False,
    ) -> DeploymentResponse:
        """
        Create a new deployment
        
        Args:
            deployment_name: Name for the deployment
            model_name: Model to deploy
            gpu_model: GPU model type (e.g., "NVIDIA_T4_16GB")
            gpu_count: Number of GPUs (1, 2, 4, or 8)
            min_replicas: Minimum number of replicas
            max_replicas: Maximum number of replicas
            hw_type: Hardware type (default: "dedicated")
            auto_retry: If True and deployment name exists, automatically generate unique name
            
        Returns:
            DeploymentResponse: Deployment creation response
        """
        original_name = deployment_name
        
        # Generate unique name if auto_retry is enabled
        if auto_retry:
            import random
            import string
            import time
            
            # Use timestamp + random for better uniqueness
            timestamp = str(int(time.time()))[-4:]  # Last 4 digits of timestamp
            suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
            deployment_name = f"{original_name}-{timestamp}{suffix}"
        
        data = {
            "deployment_name": deployment_name,
            "hw_type": hw_type,
            "gpu_model": gpu_model,
            "gpu_count": gpu_count,
            "min_replicas": min_replicas,
            "max_replicas": max_replicas,
            "model_name": model_name,
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
            elif isinstance(deployments_data, dict) and "deployments" in deployments_data:
                return [Deployment(**deployment) for deployment in deployments_data["deployments"]]
            elif isinstance(deployments_data, dict) and not deployments_data:
                # Empty dict response means no deployments
                return []
            else:
                # If it's a different format, return empty list and log the issue
                print(f"Unexpected response format: {type(deployments_data)}, content: {deployments_data}")
                return []
        finally:
            self.client.base_url = original_base_url

    def get(self, deployment_id: str) -> Deployment:
        """
        Get a deployment by ID or Name
        
        Args:
            deployment_id: The ID or Name of the deployment to retrieve
            
        Returns:
            Deployment: The deployment object
        """
        # Since there is no direct get endpoint documented or working,
        # we use list() and filter by ID or Name.
        deployments = self.list()
        for deployment in deployments:
            # Check both ID and Name
            if deployment.deployment_id == deployment_id or deployment.deployment_name == deployment_id:
                return deployment
        
        raise ValueError(f"Deployment with ID or Name '{deployment_id}' not found")

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

    def list_hardware(self) -> List[Accelerator]:
        """
        List available hardware/GPU options for deployments.
        
        This is a convenience method that calls client.accelerators.list().
        
        Returns:
            List[Accelerator]: List of available GPU/accelerator options
            
        Example:
            >>> hardware = client.deployments.list_hardware()
            >>> for hw in hardware:
            ...     print(f"{hw.gpu_model}: {hw.memory}, ${hw.pricing}/hour")
        """
        return self.client.accelerators.list()
