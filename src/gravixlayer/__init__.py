"""
GravixLayer Python SDK

Official Python client for the GravixLayer API. Provides cloud runtime
environments and template management for AI workloads.
"""

__version__ = "0.1.8"

# Eagerly import only the sync client (always needed)
from .client import GravixLayer

# Everything else is lazy-loaded via __getattr__ to reduce CLI startup time.
# Importing asyncio + async_client + async_templates + all type classes
# eagerly adds ~30ms+ of import overhead that the CLI never uses.

_LAZY_IMPORTS = {
    # Async client
    "AsyncGravixLayer": ".types.async_client",
    # Runtime types
    "Runtime": ".types.runtime",
    "RuntimeList": ".types.runtime",
    "RuntimeMetrics": ".types.runtime",
    "RuntimeTimeoutResponse": ".types.runtime",
    "RuntimeHostURL": ".types.runtime",
    "FileReadResponse": ".types.runtime",
    "FileWriteResponse": ".types.runtime",
    "FileInfo": ".types.runtime",
    "DirectoryCreateResponse": ".types.runtime",
    "CommandRunResponse": ".types.runtime",
    "CodeRunResponse": ".types.runtime",
    "CodeContext": ".types.runtime",
    "CodeContextDeleteResponse": ".types.runtime",
    "Template": ".types.runtime",
    "TemplateList": ".types.runtime",
    "RuntimeKillResponse": ".types.runtime",
    "Execution": ".types.runtime",
    "WriteEntry": ".types.runtime",
    "WriteResult": ".types.runtime",
    "WriteFilesResponse": ".types.runtime",
    "SSHInfo": ".types.runtime",
    "SSHStatus": ".types.runtime",
    "ExecutionResult": ".types.runtime",
    "ExecutionError": ".types.runtime",
    "ExecutionLogs": ".types.runtime",
    # Template types
    "BuildStepType": ".types.templates",
    "BuildStep": ".types.templates",
    "TemplateBuildStatusEnum": ".types.templates",
    "TemplateBuildPhase": ".types.templates",
    "TemplateBuildResponse": ".types.templates",
    "TemplateBuildStatus": ".types.templates",
    "TemplateInfo": ".types.templates",
    "TemplateSnapshot": ".types.templates",
    "TemplateListResponse": ".types.templates",
    "TemplateDeleteResponse": ".types.templates",
    "BuildLogEntry": ".types.templates",
    "TemplateBuilder": ".types.templates",
    # Template resources
    "Templates": ".resources.templates",
    "TemplateBuildError": ".resources.templates",
    "TemplateBuildTimeoutError": ".resources.templates",
    # Async template resources
    "AsyncTemplates": ".resources.async_templates",
    "AsyncTemplateBuildError": ".resources.async_templates",
    "AsyncTemplateBuildTimeoutError": ".resources.async_templates",
    # Exceptions
    "GravixLayerError": ".types.exceptions",
    "GravixLayerAuthenticationError": ".types.exceptions",
    "GravixLayerRateLimitError": ".types.exceptions",
    "GravixLayerRateLimitError": ".types.exceptions",
    "GravixLayerServerError": ".types.exceptions",
    "GravixLayerBadRequestError": ".types.exceptions",
    "GravixLayerConnectionError": ".types.exceptions",
}


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        import importlib
        module = importlib.import_module(_LAZY_IMPORTS[name], __name__)
        value = getattr(module, name)
        globals()[name] = value  # cache for subsequent access
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

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
