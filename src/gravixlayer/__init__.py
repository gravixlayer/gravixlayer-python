"""
GravixLayer Python SDK

Official Python client for the GravixLayer API. Provides cloud runtime
environments and template management for AI workloads.
"""

__version__ = "0.1.3"

from .client import GravixLayer
from .types.async_client import AsyncGravixLayer
from .types.runtime import (
    Runtime,
    RuntimeList,
    RuntimeMetrics,
    RuntimeTimeoutResponse,
    RuntimeHostURL,
    FileReadResponse,
    FileWriteResponse,
    FileInfo,
    DirectoryCreateResponse,
    CommandRunResponse,
    CodeRunResponse,
    CodeContext,
    CodeContextDeleteResponse,
    Template,
    TemplateList,
    RuntimeKillResponse,
    Execution,
    WriteEntry,
    WriteResult,
    WriteFilesResponse,
    SSHInfo,
    SSHStatus,
    ExecutionResult,
    ExecutionError,
    ExecutionLogs,
)
from .types.templates import (
    BuildStepType,
    BuildStep,
    TemplateBuildStatusEnum,
    TemplateBuildPhase,
    TemplateBuildResponse,
    TemplateBuildStatus,
    TemplateInfo,
    TemplateSnapshot,
    TemplateListResponse,
    TemplateDeleteResponse,
    BuildLogEntry,
    TemplateBuilder,
)
from .resources.templates import (
    Templates,
    TemplateBuildError,
    TemplateBuildTimeoutError,
)
from .resources.async_templates import (
    AsyncTemplates,
    AsyncTemplateBuildError,
    AsyncTemplateBuildTimeoutError,
)
from .types.exceptions import (
    GravixLayerError,
    GravixLayerAuthenticationError,
    GravixLayerRateLimitError,
    GravixLayerServerError,
    GravixLayerBadRequestError,
    GravixLayerConnectionError,
)

__all__ = [
    # Clients
    "GravixLayer",
    "AsyncGravixLayer",
    # Runtime types
    "Runtime",
    "RuntimeList",
    "RuntimeMetrics",
    "RuntimeTimeoutResponse",
    "RuntimeHostURL",
    "RuntimeKillResponse",
    "Execution",
    "WriteEntry",
    "WriteResult",
    "WriteFilesResponse",
    "SSHInfo",
    "SSHStatus",
    "ExecutionResult",
    "ExecutionError",
    "ExecutionLogs",
    # Runtime file/code types
    "FileReadResponse",
    "FileWriteResponse",
    "FileInfo",
    "DirectoryCreateResponse",
    "CommandRunResponse",
    "CodeRunResponse",
    "CodeContext",
    "CodeContextDeleteResponse",
    "Template",
    "TemplateList",
    # Template build pipeline
    "BuildStepType",
    "BuildStep",
    "TemplateBuildStatusEnum",
    "TemplateBuildPhase",
    "TemplateBuildResponse",
    "TemplateBuildStatus",
    "TemplateInfo",
    "TemplateSnapshot",
    "TemplateListResponse",
    "TemplateDeleteResponse",
    "BuildLogEntry",
    "TemplateBuilder",
    "Templates",
    "TemplateBuildError",
    "TemplateBuildTimeoutError",
    "AsyncTemplates",
    "AsyncTemplateBuildError",
    "AsyncTemplateBuildTimeoutError",
    # Exceptions
    "GravixLayerError",
    "GravixLayerAuthenticationError",
    "GravixLayerRateLimitError",
    "GravixLayerServerError",
    "GravixLayerBadRequestError",
    "GravixLayerConnectionError",
]
