"""Exceptions for Hyundai Kia Developers."""


class HyundaiKiaError(Exception):
    """Base integration error."""


class HyundaiKiaAuthenticationError(HyundaiKiaError):
    """Authentication failed and user action is required."""


class HyundaiKiaConnectionError(HyundaiKiaError):
    """The remote API could not be reached."""


class HyundaiKiaRateLimitError(HyundaiKiaError):
    """The remote API rate limit was reached."""


class HyundaiKiaVehicleError(HyundaiKiaError):
    """A vehicle or vehicle metric request was rejected."""
