"""Exceptions for Hyundai Kia Developers."""


class HyundaiKiaError(Exception):
    """Base integration error."""

    def __init__(
        self,
        message: str = "",
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Store upstream error metadata when available."""
        super().__init__(message)
        self.error_code = error_code
        self.error_message = error_message


class HyundaiKiaAuthenticationError(HyundaiKiaError):
    """Authentication failed and user action is required."""


class HyundaiKiaOAuthRedirectError(HyundaiKiaAuthenticationError):
    """A pasted OAuth redirect failed validation for a safe, known reason."""

    def __init__(self, error_key: str) -> None:
        """Store a translation key without retaining sensitive redirect data."""
        self.error_key = error_key
        super().__init__(error_key)


class HyundaiKiaConnectionError(HyundaiKiaError):
    """The remote API could not be reached."""


class HyundaiKiaRateLimitError(HyundaiKiaError):
    """The remote API rate limit was reached."""


class HyundaiKiaVehicleError(HyundaiKiaError):
    """A vehicle or vehicle metric request was rejected."""
