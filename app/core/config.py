from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional, Union

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str
    CERT_KEY: str
    CORS_ORIGINS: Union[str, List[str], None] = None
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    def parse_cors_origins(self) -> List[str]:
        if not self.CORS_ORIGINS:
            return ["*"]

        if isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS

        if isinstance(self.CORS_ORIGINS, str):
            if "," in self.CORS_ORIGINS:
                return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
            return [self.CORS_ORIGINS]

        return ["*"]

    @property
    def cors_origins(self) -> List[str]:
        return self.parse_cors_origins()

settings = Settings()
