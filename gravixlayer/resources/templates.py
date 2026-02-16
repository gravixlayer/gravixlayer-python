"""
Template Build Pipeline resource for synchronous client.

Provides methods for creating, building, polling, listing, and
deleting VM templates via the backend API.
"""

import time
import logging
from typing import Dict, Any, List, Optional, Union

from ..types.templates import (
    TemplateBuilder,
    TemplateBuildResponse,
    TemplateBuildStatus,
    TemplateBuildStatusEnum,
    TemplateInfo,
    TemplateSnapshot,
    TemplateListResponse,
    TemplateDeleteResponse,
    BuildLogEntry,
    BuildLogCallback,
)

logger = logging.getLogger(__name__)


class TemplateBuildError(Exception):
    """Raised when a template build fails."""

    def __init__(self, build_id: str, message: str, status: Optional[TemplateBuildStatus] = None):
        self.build_id = build_id
        self.status = status
        super().__init__(f"Template build {build_id} failed: {message}")


class TemplateBuildTimeoutError(TemplateBuildError):
    """Raised when a template build exceeds the timeout."""

    def __init__(self, build_id: str, timeout_secs: int, status: Optional[TemplateBuildStatus] = None):
        self.timeout_secs = timeout_secs
        super().__init__(
            build_id,
            f"Build did not complete within {timeout_secs}s",
            status=status,
        )


class Templates:
    """Template Build Pipeline resource.

    Exposes methods aligned with the backend template API:
        POST   /v1/agents/templates/build
        GET    /v1/agents/templates/builds/:build_id/status
        GET    /v1/agents/templates
        GET    /v1/agents/templates/:id
        GET    /v1/agents/templates/:id/snapshot
        DELETE /v1/agents/templates/:id

    Example:
        >>> from gravixlayer import GravixLayer
        >>> from gravixlayer.types.templates import TemplateBuilder
        >>>
        >>> client = GravixLayer(api_key="...", cloud="aws", region="us-east-1")
        >>> templates = Templates(client)
        >>>
        >>> builder = (
        ...     TemplateBuilder("my-ml-env")
        ...     .from_python("3.11-slim")
        ...     .apt_install("git", "curl")
        ...     .pip_install("numpy", "pandas")
        ...     .set_start_cmd("python /app/serve.py")
        ... )
        >>>
        >>> # Blocking build with status polling
        >>> status = templates.build_and_wait(builder, timeout_secs=600)
        >>> print(status.template_id)
    """

    def __init__(self, client):
        self.client = client

    # -- Internal helpers ---------------------------------------------------

    def _make_agents_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """Issue a request against the agents API (/v1/agents/...)."""
        return self.client._make_request(method, endpoint, data, _service="v1/agents", **kwargs)

    @staticmethod
    def _parse_build_response(data: Dict[str, Any]) -> TemplateBuildResponse:
        return TemplateBuildResponse(
            build_id=data["build_id"],
            template_id=data["template_id"],
            status=data.get("status", ""),
            message=data.get("message", ""),
        )

    @staticmethod
    def _parse_build_status(data: Dict[str, Any]) -> TemplateBuildStatus:
        return TemplateBuildStatus(
            build_id=data["build_id"],
            template_id=data["template_id"],
            status=data.get("status", ""),
            phase=data.get("phase", ""),
            progress_percent=data.get("progress_percent", 0),
            error=data.get("error"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )

    @staticmethod
    def _parse_template_info(data: Dict[str, Any]) -> TemplateInfo:
        return TemplateInfo(
            id=data["id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            vcpu_count=data.get("vcpu_count", 0),
            memory_mb=data.get("memory_mb", 0),
            disk_size_mb=data.get("disk_size_mb", 0),
            visibility=data.get("visibility", "private"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            base_image=data.get("base_image"),
            environment=data.get("environment"),
            tags=data.get("tags"),
        )

    @staticmethod
    def _parse_snapshot(data: Dict[str, Any]) -> TemplateSnapshot:
        return TemplateSnapshot(
            template_id=data["template_id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            has_snapshot=data.get("has_snapshot", False),
            vcpu_count=data.get("vcpu_count", 0),
            memory_mb=data.get("memory_mb", 0),
            created_at=data.get("created_at", ""),
            envd_version=data.get("envd_version"),
            snapshot_size_bytes=data.get("snapshot_size_bytes"),
        )

    # -- Build operations ---------------------------------------------------

    def build(
        self,
        builder: Union[TemplateBuilder, Dict[str, Any]],
    ) -> TemplateBuildResponse:
        """Start an asynchronous template build.

        Args:
            builder: A TemplateBuilder instance or a raw dict matching
                     the BuildTemplateRequest schema.

        Returns:
            TemplateBuildResponse with build_id for status polling.
        """
        if isinstance(builder, TemplateBuilder):
            payload = builder.to_dict()
        else:
            payload = builder

        response = self._make_agents_request("POST", "templates/build", payload)
        return self._parse_build_response(response.json())

    def get_build_status(self, build_id: str) -> TemplateBuildStatus:
        """Poll the status of a running template build.

        Args:
            build_id: The build ID returned by build().

        Returns:
            TemplateBuildStatus with current phase and progress.
        """
        response = self._make_agents_request(
            "GET", f"templates/builds/{build_id}/status"
        )
        return self._parse_build_status(response.json())

    def build_and_wait(
        self,
        builder: Union[TemplateBuilder, Dict[str, Any]],
        poll_interval_secs: float = 5.0,
        timeout_secs: int = 600,
        on_status: Optional[BuildLogCallback] = None,
    ) -> TemplateBuildStatus:
        """Start a build and block until it completes or fails.

        Args:
            builder: A TemplateBuilder or raw dict for the build request.
            poll_interval_secs: Seconds between status polls (default 5).
            timeout_secs: Maximum seconds to wait (default 600).
            on_status: Optional callback invoked on each status poll.

        Returns:
            Final TemplateBuildStatus when the build reaches a terminal state.

        Raises:
            TemplateBuildError: If the build fails.
            TemplateBuildTimeoutError: If the build exceeds timeout.
        """
        build_response = self.build(builder)
        build_id = build_response.build_id

        logger.info(
            "Template build started: build_id=%s template_id=%s",
            build_id,
            build_response.template_id,
        )

        if on_status:
            on_status(BuildLogEntry(
                level="info",
                message=f"Build started: {build_response.message}",
            ))

        deadline = time.monotonic() + timeout_secs
        last_phase = ""

        while True:
            if time.monotonic() > deadline:
                # Fetch one last status for the caller
                try:
                    final = self.get_build_status(build_id)
                except Exception:
                    final = None
                raise TemplateBuildTimeoutError(
                    build_id, timeout_secs, status=final
                )

            time.sleep(poll_interval_secs)
            status = self.get_build_status(build_id)

            # Notify on phase transitions
            if status.phase != last_phase:
                last_phase = status.phase
                logger.info(
                    "Build %s: phase=%s progress=%d%%",
                    build_id,
                    status.phase,
                    status.progress_percent,
                )
                if on_status:
                    on_status(BuildLogEntry(
                        level="info",
                        message=f"Phase: {status.phase} ({status.progress_percent}%)",
                    ))

            if status.is_terminal:
                if status.is_success:
                    logger.info("Build %s completed successfully", build_id)
                    if on_status:
                        on_status(BuildLogEntry(
                            level="info",
                            message="Build completed successfully",
                        ))
                    return status
                else:
                    error_msg = status.error or "Unknown build failure"
                    logger.error("Build %s failed: %s", build_id, error_msg)
                    if on_status:
                        on_status(BuildLogEntry(
                            level="error",
                            message=f"Build failed: {error_msg}",
                        ))
                    raise TemplateBuildError(
                        build_id, error_msg, status=status
                    )

    # -- Template CRUD ------------------------------------------------------

    def list(
        self,
        limit: int = 100,
        offset: int = 0,
        project_id: Optional[str] = None,
    ) -> TemplateListResponse:
        """List available templates.

        Args:
            limit: Max number of templates to return (default 100).
            offset: Pagination offset (default 0).
            project_id: Optional project filter.

        Returns:
            TemplateListResponse containing template list and pagination info.
        """
        params = [f"limit={limit}", f"offset={offset}"]
        if project_id:
            params.append(f"project_id={project_id}")
        query = "&".join(params)
        endpoint = f"templates?{query}"

        response = self._make_agents_request("GET", endpoint)
        data = response.json()
        templates = [self._parse_template_info(t) for t in data.get("templates", [])]
        return TemplateListResponse(
            templates=templates,
            limit=data.get("limit", limit),
            offset=data.get("offset", offset),
        )

    def get(self, template_id: str) -> TemplateInfo:
        """Get a single template by ID.

        Args:
            template_id: The template UUID.

        Returns:
            TemplateInfo with full template metadata.
        """
        response = self._make_agents_request("GET", f"templates/{template_id}")
        return self._parse_template_info(response.json())

    def get_snapshot(self, template_id: str) -> TemplateSnapshot:
        """Get template snapshot information.

        Args:
            template_id: The template UUID.

        Returns:
            TemplateSnapshot with snapshot metadata.
        """
        response = self._make_agents_request(
            "GET", f"templates/{template_id}/snapshot"
        )
        return self._parse_snapshot(response.json())

    def delete(self, template_id: str) -> TemplateDeleteResponse:
        """Delete a template and its snapshot.

        Args:
            template_id: The template UUID.

        Returns:
            TemplateDeleteResponse confirming deletion.
        """
        self._make_agents_request("DELETE", f"templates/{template_id}")
        # Backend returns 204 No Content
        return TemplateDeleteResponse(template_id=template_id, deleted=True)
