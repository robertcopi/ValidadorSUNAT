import time
from typing import Dict, List, Optional
from app.core.config import settings


class LoginRateLimiter:
    """
    Limitador de tasa en memoria para intentos fallidos de autenticación.
    Bloquea temporalmente solicitudes que excedan el límite de intentos fallidos.
    """

    def __init__(self, max_attempts: Optional[int] = None, window_seconds: Optional[int] = None):
        self._custom_max = max_attempts
        self._custom_window = window_seconds
        # Mapea clave (ej: IP o email) a lista de timestamps de fallos: { key: [t1, t2, ...] }
        self._attempts: Dict[str, List[float]] = {}

    @property
    def max_attempts(self) -> int:
        return self._custom_max or getattr(settings, "RATE_LIMIT_LOGIN_MAX_ATTEMPTS", 5)

    @property
    def window_seconds(self) -> int:
        return self._custom_window or getattr(settings, "RATE_LIMIT_LOGIN_WINDOW_SECONDS", 300)

    def _cleanup_old_attempts(self, key: str, now: float) -> None:
        if key in self._attempts:
            cutoff = now - self.window_seconds
            self._attempts[key] = [t for t in self._attempts[key] if t > cutoff]
            if not self._attempts[key]:
                del self._attempts[key]

    def is_rate_limited(self, key: str) -> bool:
        """Verifica si la clave ha superado el número máximo de fallos en la ventana."""
        now = time.time()
        self._cleanup_old_attempts(key, now)
        attempts = self._attempts.get(key, [])
        return len(attempts) >= self.max_attempts

    def record_failure(self, key: str) -> int:
        """Registra un fallo para la clave y retorna la cantidad de intentos en la ventana."""
        now = time.time()
        self._cleanup_old_attempts(key, now)
        if key not in self._attempts:
            self._attempts[key] = []
        self._attempts[key].append(now)
        return len(self._attempts[key])

    def reset(self, key: str) -> None:
        """Limpia los intentos fallidos tras un inicio de sesión exitoso."""
        if key in self._attempts:
            del self._attempts[key]

    def clear_all(self) -> None:
        """Limpia completamente el estado (usado en tests y mantenimiento)."""
        self._attempts.clear()


class ActionRateLimiter:
    """
    Limitador genérico en memoria de peticiones por ventana temporal
    para endpoints de alto costo computacional (ej. uploads, exportaciones).
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = {}

    def is_rate_limited(self, key: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        if key in self._requests:
            self._requests[key] = [t for t in self._requests[key] if t > cutoff]
            if not self._requests[key]:
                del self._requests[key]

        reqs = self._requests.get(key, [])
        if len(reqs) >= self.max_requests:
            return True

        if key not in self._requests:
            self._requests[key] = []
        self._requests[key].append(now)
        return False

    def clear_all(self) -> None:
        self._requests.clear()


# Instancia singleton para login
login_rate_limiter = LoginRateLimiter()

# Instancias singleton para operaciones pesadas
upload_rate_limiter = ActionRateLimiter(
    max_requests=getattr(settings, "RATE_LIMIT_UPLOAD_MAX", 20),
    window_seconds=getattr(settings, "RATE_LIMIT_UPLOAD_WINDOW_SECONDS", 60)
)
export_rate_limiter = ActionRateLimiter(
    max_requests=getattr(settings, "RATE_LIMIT_EXPORT_MAX", 30),
    window_seconds=getattr(settings, "RATE_LIMIT_EXPORT_WINDOW_SECONDS", 60)
)
