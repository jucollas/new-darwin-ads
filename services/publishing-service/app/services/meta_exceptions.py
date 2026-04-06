class MetaApiError(Exception):
    """Base exception for Meta API errors."""

    def __init__(self, message: str, error_code: int | None = None, error_subcode: int | None = None):
        self.message = message
        self.error_code = error_code
        self.error_subcode = error_subcode
        super().__init__(message)


class MetaTokenInvalidError(MetaApiError):
    """Error code 190 — OAuth token is invalid or expired."""
    pass


class MetaRateLimitError(MetaApiError):
    """Error codes 17, 613 — API rate limit reached."""
    pass


class MetaInvalidParameterError(MetaApiError):
    """Error code 100 — Invalid parameter in API call."""
    pass


class MetaMissingPermissionError(MetaApiError):
    """Error code 275 — Missing required permission."""
    pass


class MetaValidationError(MetaApiError):
    """Error code 1487901 — Validation error with blame_field_specs."""

    def __init__(self, message: str, error_code: int | None = None,
                 error_subcode: int | None = None, blame_field_specs: list | None = None):
        self.blame_field_specs = blame_field_specs or []
        super().__init__(message, error_code, error_subcode)
