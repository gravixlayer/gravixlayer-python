"""
Files resource for GravixLayer SDK 
"""
from typing import Optional, Union, BinaryIO, IO
import os
from ..types.files import FileObject, FileUploadResponse, FileListResponse, FileDeleteResponse, FILE_PURPOSES
from ..types.exceptions import GravixLayerBadRequestError


class Files:
    """Files resource for file management operations"""

    def __init__(self, client):
        self.client = client
        # Remove the _base_url since we'll use endpoints instead
        # self._base_url = self.client.base_url.replace('/v1/inference', '/v1/files')

    def create(
        self,
        file: Union[str, BinaryIO, IO],
        purpose: str,
        expires_after: Optional[int] = None,
        filename: Optional[str] = None,
        **kwargs
    ) -> FileUploadResponse:
        """
        Upload a file for use with AI models.

        Args:
            file: File to upload (file path string or file-like object)
            purpose: File purpose (assistants, batch, batch_output, fine-tune, vision, user_data, evals)
            expires_after: Optional expiration time in seconds
            filename: Optional custom filename for the uploaded file

        Returns:
            FileUploadResponse: Upload response with file details

        Raises:
            GravixLayerBadRequestError: If purpose is invalid or file is invalid
        """
        # Validate purpose
        if purpose not in FILE_PURPOSES:
            raise GravixLayerBadRequestError(
                f"Invalid purpose. Supported: {', '.join(FILE_PURPOSES)}"
            )

        # Prepare form data
        form_data = {'purpose': purpose}
        if expires_after is not None:
            if not isinstance(expires_after, int) or expires_after <= 0:
                raise GravixLayerBadRequestError(
                    "expires_after must be a positive integer (seconds)"
                )
            form_data['expires_after'] = str(expires_after)

        # Handle file input
        files = {}
        if isinstance(file, str):
            # File path
            if not os.path.exists(file):
                raise GravixLayerBadRequestError(f"File not found: {file}")

            file_size = os.path.getsize(file)
            if file_size == 0:
                raise GravixLayerBadRequestError(
                    "File size must be between 1 byte and 200MB")
            if file_size > 200 * 1024 * 1024:  # 200MB
                raise GravixLayerBadRequestError(
                    "File size must be between 1 byte and 200MB")

            # Use custom filename if provided, otherwise use the original filename
            upload_filename = filename if filename else os.path.basename(file)
            files['file'] = (upload_filename, open(file, 'rb'))
            should_close = True
        else:
            # File-like object
            upload_filename = filename if filename else getattr(
                file, 'name', 'uploaded_file')
            files['file'] = (upload_filename, file)
            should_close = False

        # Use a different base URL for files API
        original_base_url = self.client.base_url
        self.client.base_url = self.client.base_url.replace(
            "/v1/inference", "/v1/files")

        try:
            response = self.client._make_request(
                method="POST",
                endpoint="",  # Empty endpoint since base_url already points to /v1/files
                data=form_data,
                files=files
            )

            result = response.json()
            return FileUploadResponse(
                message=result.get('message', ''),
                file_name=result.get('file_name', ''),
                purpose=result.get('purpose', '')
            )
        finally:
            self.client.base_url = original_base_url
            if should_close and 'file' in files:
                # Close the file object from the tuple
                files['file'][1].close()

    def upload(
        self,
        file: Union[str, BinaryIO, IO],
        purpose: str,
        expires_after: Optional[int] = None,
        filename: Optional[str] = None,
        **kwargs
    ) -> FileUploadResponse:
        """
        Upload a file for use with AI models (alias for create).

        Args:
            file: File to upload (file path string or file-like object)
            purpose: File purpose (assistants, batch, batch_output, fine-tune, vision, user_data, evals)
            expires_after: Optional expiration time in seconds
            filename: Optional custom filename for the uploaded file

        Returns:
            FileUploadResponse: Upload response with file details
        """
        return self.create(file=file, purpose=purpose, expires_after=expires_after, filename=filename, **kwargs)

    def list(self) -> FileListResponse:
        """
        List all files belonging to the user.

        Returns:
            FileListResponse: List of file objects
        """
        # Use a different base URL for files API
        original_base_url = self.client.base_url
        self.client.base_url = self.client.base_url.replace(
            "/v1/inference", "/v1/files")

        try:
            response = self.client._make_request(
                method="GET",
                endpoint=""
            )

            result = response.json()
            files_data = result.get('data', [])

            files = []
            for file_data in files_data:
                files.append(FileObject(
                    id=file_data.get('id', ''),
                    object=file_data.get('object', 'file'),
                    bytes=file_data.get('bytes', 0),
                    created_at=file_data.get('created_at', 0),
                    filename=file_data.get('filename', ''),
                    purpose=file_data.get('purpose', ''),
                    expires_after=file_data.get('expires_after')
                ))

            return FileListResponse(data=files)
        finally:
            self.client.base_url = original_base_url

    def retrieve(self, file_id: str) -> FileObject:
        """
        Retrieve metadata for a specific file by its ID.

        Args:
            file_id: File ID (UUID format)

        Returns:
            FileObject: File metadata

        Raises:
            GravixLayerBadRequestError: If file_id is missing
        """
        if not file_id:
            raise GravixLayerBadRequestError("file ID required")

        # Use a different base URL for files API
        original_base_url = self.client.base_url
        self.client.base_url = self.client.base_url.replace(
            "/v1/inference", "/v1/files")

        try:
            response = self.client._make_request(
                method="GET",
                endpoint=file_id
            )

            result = response.json()
            return FileObject(
                id=result.get('id', ''),
                object=result.get('object', 'file'),
                bytes=result.get('bytes', 0),
                created_at=result.get('created_at', 0),
                filename=result.get('filename', ''),
                purpose=result.get('purpose', ''),
                expires_after=result.get('expires_after')
            )
        finally:
            self.client.base_url = original_base_url

    def content(self, file_id: str) -> bytes:
        """
        Download the actual file content.

        Args:
            file_id: File ID (UUID format)

        Returns:
            bytes: Raw file content

        Raises:
            GravixLayerBadRequestError: If file_id is missing
        """
        if not file_id:
            raise GravixLayerBadRequestError("file ID required")

        # Use raw request for binary content
        import requests

        headers = {
            "Authorization": f"Bearer {self.client.api_key}",
            "User-Agent": self.client.user_agent
        }

        # Use the correct base URL for files API
        files_base_url = self.client.base_url.replace(
            "/v1/inference", "/v1/files")

        response = requests.get(
            f"{files_base_url}/{file_id}/content",
            headers=headers,
            timeout=self.client.timeout
        )

        if response.status_code != 200:
            self.client._handle_error_response(response)

        return response.content

    def delete(self, file_id: str) -> FileDeleteResponse:
        """
        Delete a file permanently. This action cannot be undone.

        Args:
            file_id: File ID (UUID format)

        Returns:
            FileDeleteResponse: Delete confirmation

        Raises:
            GravixLayerBadRequestError: If file_id is missing
        """
        if not file_id:
            raise GravixLayerBadRequestError("File ID is required")

        # Use a different base URL for files API
        original_base_url = self.client.base_url
        self.client.base_url = self.client.base_url.replace(
            "/v1/inference", "/v1/files")

        try:
            response = self.client._make_request(
                method="DELETE",
                endpoint=file_id
            )

            result = response.json()
            return FileDeleteResponse(
                message=result.get('message', ''),
                file_id=result.get('file_id', ''),
                file_name=result.get('file_name', '')
            )
        finally:
            self.client.base_url = original_base_url
