import logging
from typing import Any, Dict, Optional


class AppLogger:
    """Thin wrapper around the stdlib logger that adds lightweight context binding."""

    def __init__(
        self,
        name: str,
        context: Optional[Dict[str, Any]] = None,
        _logger: Optional[logging.Logger] = None,
    ):
        self._logger = _logger or logging.getLogger(name)
        self._name = name
        self._context = context or {}

    def bind(self, **extra: Any) -> "AppLogger":
        """Return a new logger instance with additional contextual key/value pairs."""
        merged = {**self._context, **extra}
        return AppLogger(self._name, merged, _logger=self._logger)

    def debug(self, message: str, **context: Any) -> None:
        self._log(logging.DEBUG, message, context)

    def info(self, message: str, **context: Any) -> None:
        self._log(logging.INFO, message, context)

    def warning(self, message: str, **context: Any) -> None:
        self._log(logging.WARNING, message, context)

    def error(self, message: str, **context: Any) -> None:
        self._log(logging.ERROR, message, context)

    def exception(self, message: str, **context: Any) -> None:
        """Log an error message along with the active exception."""
        payload = {**self._context, **context}
        self._logger.error(self._format(message, payload), exc_info=True)

    def _log(self, level: int, message: str, context: Dict[str, Any]) -> None:
        payload = {**self._context, **context} if context else dict(self._context)
        self._logger.log(level, self._format(message, payload))

    @staticmethod
    def _format(message: str, context: Dict[str, Any]) -> str:
        if not context:
            return message
        ctx_str = " ".join(
            f"{key}={AppLogger._stringify(value)}" for key, value in context.items()
        )
        return f"{message} | {ctx_str}"

    @staticmethod
    def _stringify(value: Any) -> str:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return str(value)
        return repr(value)


def get_logger(name: str) -> AppLogger:
    return AppLogger(name)
