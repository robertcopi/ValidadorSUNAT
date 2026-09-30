import json
from typing import List, Optional, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Sistema de Validación de Comprobantes SUNAT"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    
    # Seguridad y JWT
    SECRET_KEY: str = "dev_secret_key_change_in_production_f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    
    # Base de Datos PostgreSQL
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "sunat_user"
    POSTGRES_PASSWORD: str = "sunat_secure_password_dev"
    POSTGRES_DB: str = "sunat_consultas_db"
    
    @property
    def ASYNC_DATABASE_URI(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def SYNC_DATABASE_URI(self) -> str:
        return f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Semillas de desarrollo
    SEED_ADMIN_EMAIL: str = "admin@sistema.local"
    SEED_ADMIN_PASSWORD: str = "AdminDev2026!"
    SEED_CONTADOR_PASSWORD: str = "ContadorDev2026!"
    
    # Configuración de SUNAT (Fase 2)
    SUNAT_AUTH_BASE_URL: str = "https://api-seguridad.sunat.gob.pe/v1/clientesextranet"
    SUNAT_API_BASE_URL: str = "https://api.sunat.gob.pe/v1/contribuyente/contribuyentes"
    SUNAT_AUTH_SCOPE: str = "https://api.sunat.gob.pe/v1/contribuyente/contribuyentes"
    SUNAT_TIMEOUT_SECONDS: float = 30.0
    SUNAT_REQUEST_TIMEOUT: float = 30.0
    SUNAT_MAX_CONCURRENCY: int = 5
    SUNAT_RETRY_MAX_ATTEMPTS: int = 1
    SUNAT_RETRY_BASE_DELAY: float = 1.0

    # Credenciales SUNAT Multiempresa - DAIRA (RUC 20538976815)
    # Nota: Para la API de Consulta Integrada se utiliza OAuth2 client_credentials (únicamente client_id y client_secret).
    SUNAT_DAIRA_CLIENT_ID: Optional[str] = None
    SUNAT_DAIRA_CLIENT_SECRET: Optional[str] = None
    SUNAT_DAIRA_SOL_USER: Optional[str] = None  # No requerido para Consulta Integrada
    SUNAT_DAIRA_SOL_PASSWORD: Optional[str] = None  # No requerido para Consulta Integrada

    # Credenciales SUNAT Multiempresa - GRUPO JJD MAR (RUC 20612689831)
    # Nota: Para la API de Consulta Integrada se utiliza OAuth2 client_credentials (únicamente client_id y client_secret).
    SUNAT_JJD_CLIENT_ID: Optional[str] = None
    SUNAT_JJD_CLIENT_SECRET: Optional[str] = None
    SUNAT_JJD_SOL_USER: Optional[str] = None  # No requerido para Consulta Integrada
    SUNAT_JJD_SOL_PASSWORD: Optional[str] = None  # No requerido para Consulta Integrada
    
    # Archivos y Procesamiento Masivo
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 10
    MAX_MASSIVE_ITEMS: int = 1000
    SUNAT_REQUEST_DELAY_MS: int = 0
    SUNAT_MASSIVE_MAX_RETRIES: int = 3
    
    # CORS
    BACKEND_CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, str) and v.startswith("["):
            return json.loads(v)
        elif isinstance(v, list):
            return v
        return []

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
