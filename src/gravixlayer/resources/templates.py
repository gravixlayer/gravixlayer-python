"""
Template Build Pipeline resource for synchronous client.

Provides methods for creating, building, polling, listing, and
deleting VM templates via the backend API.
"""

import sys
import time
import logging
from typing import Dict, Any, Optional, Union

from .._cli_progress import TEMPLATE_BUILD_PHASE_LABELS, PhaseSpinner, fmt_duration
from .._resource_utils import build_list_endpoint, parse_paginated_items
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
    _parse_build_response,
    _parse_build_status,
    _parse_template_info,
    _parse_snapshot,
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
        POST   /v1/agents/template/build
        GET    /v1/agents/template/builds/:build_id/status
        GET    /v1/agents/template
        GET    /v1/agents/template/:id
        GET    /v1/agents/template/:id/snapshot
        DELETE /v1/agents/template/:id

    Example:
        >>> from gravixlayer import GravixLayer
        >>> from gravixlayer.types.templates import TemplateBuilder
        >>>
        >>> client = GravixLayer(api_key="...", cloud="azure", region="eastus2")
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

        response = self._make_agents_request("POST", "template/build", payload)
        return _parse_build_response(response.json())

    def get_build_status(self, build_id: str) -> TemplateBuildStatus:
        """Poll the status of a running template build.

        Args:
            build_id: The build ID returned by build().

        Returns:
            TemplateBuildStatus with current phase and progress.
        """
        response = self._make_agents_request(
            "GET", f"template/builds/{build_id}/status"
        )
        return _parse_build_status(response.json())

    def build_and_wait(
        self,
        builder: Union[TemplateBuilder, Dict[str, Any]],
        poll_interval_secs: float = 5.0,
        timeout_secs: int = 600,
        on_status: Optional[BuildLogCallback] = None,
    ) -> TemplateBuildStatus:
        """Start a build and block until it completes or fails.

        On a TTY, shows the same PACKAGING / BUILDING / VERIFYING spinner and
        elapsed times as agent deploy. Pass ``on_status`` to disable the
        built-in display and handle updates yourself.

        Args:
            builder: A TemplateBuilder or raw dict for the build request.
            poll_interval_secs: Seconds between status polls (default 5).
            timeout_secs: Maximum seconds to wait (default 600).
            on_status: Optional callback on each **phase change** (not every poll).

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
        last_phase_raw = ""
        last_display_label = ""
        phase_start = time.monotonic()
        build_start = time.monotonic()

        show_spinner = on_status is None and sys.stderr.isatty()
        spinner = PhaseSpinner() if show_spinner else None

        if show_spinner:
            sys.stderr.write("\nBuilding template...\n\n")
            sys.stderr.flush()

        while True:
            if time.monotonic() > deadline:
                if spinner:
                    spinner.stop()
                try:
                    final = self.get_build_status(build_id)
                except Exception:
                    final = None
                raise TemplateBuildTimeoutError(
                    build_id, timeout_secs, status=final
                )

            status = self.get_build_status(build_id)

            if status.phase != last_phase_raw:
                last_phase_raw = status.phase
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
                elapsed_s = time.monotonic() - phase_start
                total_s = time.monotonic() - build_start
                if status.is_success:
                    if spinner:
                        spinner.finish(
                            last_display_label,
                            elapsed_s,
                            total_s,
                            ready_message="Template build successful",
                        )
                        sys.stderr.write(f"  Template ID: {status.template_id}\n")
                        sys.stderr.flush()
                    else:
                        logger.info("Build %s completed successfully", build_id)
                        if on_status:
                            on_status(BuildLogEntry(
                                level="info",
                                message="Build completed successfully",
                            ))
                    return status

                error_msg = status.error or "Unknown build failure"
                if spinner:
                    spinner.stop()
                    sys.stderr.write(
                        f"\r  FAILED: {error_msg} ({fmt_duration(total_s)})\n"
                    )
                    sys.stderr.flush()
                else:
                    logger.error("Build %s failed: %s", build_id, error_msg)
                    if on_status:
                        on_status(BuildLogEntry(
                            level="error",
                            message=f"Build failed: {error_msg}",
                        ))
                raise TemplateBuildError(
                    build_id, error_msg, status=status
                )

            current_display = TEMPLATE_BUILD_PHASE_LABELS.get(
                status.phase, status.phase.upper()
            )
            if current_display != last_display_label:
                now = time.monotonic()
                elapsed_s = now - phase_start
                if spinner:
                    spinner.update(current_display, now, elapsed_s, last_display_label)
                elif on_status is None and last_display_label:
                    logger.info("%s: DONE (%s)", last_display_label, fmt_duration(elapsed_s))
                phase_start = now
                last_display_label = current_display

            time.sleep(poll_interval_secs)

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
        endpoint = build_list_endpoint(
            "template",
            limit=limit,
            offset=offset,
            extra_params={"project_id": project_id},
        )

        response = self._make_agents_request("GET", endpoint)
        data = response.json()
        templates, page_limit, page_offset = parse_paginated_items(
            data,
            "templates",
            _parse_template_info,
            default_limit=limit,
            default_offset=offset,
        )
        return TemplateListResponse(
            templates=templates,
            limit=page_limit,
            offset=page_offset,
        )

    def get(self, template_id: str) -> TemplateInfo:
        """Get a single template by ID.

        Args:
            template_id: The template UUID.

        Returns:
            TemplateInfo with full template metadata.
        """
        response = self._make_agents_request("GET", f"template/{template_id}")
        return _parse_template_info(response.json())

    def get_snapshot(self, template_id: str) -> TemplateSnapshot:
        """Get template snapshot information.

        Args:
            template_id: The template UUID.

        Returns:
            TemplateSnapshot with snapshot metadata.
        """
        response = self._make_agents_request(
            "GET", f"template/{template_id}/snapshot"
        )
        return _parse_snapshot(response.json())

    def delete(self, template_id: str) -> TemplateDeleteResponse:
        """Delete a template and its snapshot.

        Args:
            template_id: The template UUID.

        Returns:
            TemplateDeleteResponse confirming deletion.
        """
        self._make_agents_request("DELETE", f"template/{template_id}")
        # Backend returns 204 No Content
        return TemplateDeleteResponse(template_id=template_id, deleted=True)
