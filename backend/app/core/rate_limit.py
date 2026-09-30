import time
from typing import Dict, List


class LoginRateLimiter:
    """
    Limitador de tasa en memoria para intentos fallidos de autenticación.
    Bloquea temporalmente solicitudes que excedan el límite de intentos fallidos.
    """

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        # Mapea clave (ej: IP o email) a lista de timestamps de fallos: { key: [t1, t2, ...] }
        self._attempts: Dict[str, List[float]] = {}

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


# Instancia singleton para login
login_rate_limiter = LoginRateLimiter(max_attempts=5, window_seconds=300)
