class AppException(Exception):
    """Base application exception with structured error metadata."""

    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        super().__init__(message)


class BadRequestException(AppException):
    """Exception raised for invalid client requests."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(status_code=400, error_code=error_code, message=message)


class UnauthorizedException(AppException):
    """Exception raised when authentication or authorization fails."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(status_code=401, error_code=error_code, message=message)


class ForbiddenException(AppException):
    """Exception raised when user lacks permission for an action."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(status_code=403, error_code=error_code, message=message)


class NotFoundException(AppException):
    """Exception raised when a resource cannot be found."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(status_code=404, error_code=error_code, message=message)


class ConflictException(AppException):
    """Exception raised when resource state conflicts with the request."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(status_code=409, error_code=error_code, message=message)


class ServiceUnavailableException(AppException):
    """Exception raised when an external dependency is unavailable."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(status_code=503, error_code=error_code, message=message)


class TooManyRequestsException(AppException):
    """Exception raised when a request exceeds configured rate limits."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(status_code=429, error_code=error_code, message=message)
