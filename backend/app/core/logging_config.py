import logging
import re
import sys

SENSITIVE_PATTERNS = [
    (re.compile(r'(Bearer\s+)[A-Za-z0-9\-_.]+', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'((?:password|client_secret|token|access_token|password_hash)[\s"\'=:]+)([^\s"\'&,]+)', re.IGNORECASE), r'\1[REDACTED]'),
]


class SensitiveDataFilter(logging.Filter):
    """Filtro de logging que anonimiza tokens Bearer, contraseñas y secretos."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, repl in SENSITIVE_PATTERNS:
                record.msg = pattern.sub(repl, record.msg)
        return True


def setup_logging():
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(SensitiveDataFilter())

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[handler]
    )

    # Reducir verbosidad de logs de terceros
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


logger = logging.getLogger("sunat_validator")
