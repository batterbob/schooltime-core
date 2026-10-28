"""Package-specific failure types."""


class ValidationError(ValueError):
    """Raised when untrusted normalized input violates the public contract."""
