"""Domain errors raised by actions and mapped to HTTP responses by the API."""


class ActionError(Exception):
    """A rejected action. `status_code` is the HTTP status the API should return."""

    def __init__(self, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
