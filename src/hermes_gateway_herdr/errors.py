class GatewayError(Exception):
    """A public error code with a deliberately non-sensitive explanation."""

    def __init__(self, code: str, message: str = ""):
        self.code = code
        super().__init__(message or code)

    @property
    def exit_code(self) -> int:
        if self.code in {"BUSY", "PENDING", "PENDING_UNKNOWN", "UNKNOWN", "OWNER_UNAVAILABLE"}:
            return 10
        if self.code in {"IO_ERROR", "STOP_FAILED"}:
            return 30
        return 20
