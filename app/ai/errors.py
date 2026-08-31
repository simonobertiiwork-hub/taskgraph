"""Controlled failures for the AI incident-analysis boundary."""


class AIIncidentError(RuntimeError):
    """Base class for failures safe to expose as a demo error."""


class LLMUnavailableError(AIIncidentError):
    """The configured model provider could not complete a request."""


class LLMInvalidResponseError(AIIncidentError):
    """The provider envelope or model output violated its contract."""


class ToolPlanError(AIIncidentError):
    """The model selected an unknown, unsafe, or malformed tool call."""
