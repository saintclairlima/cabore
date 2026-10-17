from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

class Configuracoes(BaseSettings):
    AMBIENTE: Literal["desenvolvimento", "producao"] = "producao"
    DATABASE_URL: SecretStr
    ADMIN_KEY: SecretStr
    DISPOSITIVO: str ="cpu"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("DATABASE_URL")
    @classmethod
    def validar_url_banco(cls, url_banco: SecretStr) -> SecretStr:
        valor = url_banco.get_secret_value().strip()
        try:
            url_analisada = make_url(valor)
        except ArgumentError as erro:
            raise ValueError("DATABASE_URL não contém uma URL válida.") from erro

        if url_analisada.drivername != "postgresql+asyncpg":
            raise ValueError(
                "DATABASE_URL deve usar o driver assíncrono postgresql+asyncpg."
            )
        return SecretStr(valor)

    @field_validator("ADMIN_KEY")
    @classmethod
    def validar_chave_admin(cls, chave: SecretStr) -> SecretStr:
        valor = chave.get_secret_value().strip()
        if len(valor) < 32:
            raise ValueError("ADMIN_KEY deve ter pelo menos 32 caracteres.")
        return SecretStr(valor)

configuracoes = Configuracoes()