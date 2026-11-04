"""Einstellungen aus Umgebungsvariablen bzw. der Datei ".env" (siehe .env.example)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Einstellungen(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mealie_url: str = "http://localhost:9000"
    mealie_token: str = ""
    data_dir: Path = Path("./data")

    @property
    def mealie_basis(self) -> str:
        return self.mealie_url.rstrip("/")


@lru_cache
def einstellungen() -> Einstellungen:
    return Einstellungen()
