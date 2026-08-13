"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Neo4jSettings(BaseSettings):
    """Neo4j connection and pool settings.

    Credentials are deliberately separate from the URI so they remain redacted by
    Pydantic and cannot accidentally be emitted as part of connection logging.
    ``NEO4J_AUTH=user/password`` remains supported for the existing deployment,
    but separate username and password variables are preferred.
    """

    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: SecretStr = Field(default_factory=lambda: SecretStr(""))
    auth: SecretStr | None = Field(default=None, exclude=True, repr=False)
    database: str = "neo4j"

    max_connection_pool_size: int = Field(default=50, ge=1, le=1000)
    connection_acquisition_timeout_seconds: float = Field(default=10.0, gt=0)
    connection_timeout_seconds: float = Field(default=5.0, gt=0)
    max_connection_lifetime_seconds: float = Field(default=3600.0, gt=0)
    liveness_check_timeout_seconds: float = Field(default=30.0, ge=0)
    max_transaction_retry_time_seconds: float = Field(default=15.0, ge=0)
    query_timeout_seconds: float = Field(default=10.0, gt=0)
    startup_timeout_seconds: float = Field(default=15.0, gt=0)
    fetch_size: int = Field(default=1000, ge=1)
    keep_alive: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="NEO4J_",
        extra="ignore",
    )

    @field_validator("uri")
    @classmethod
    def validate_uri(cls, value: str) -> str:
        """Accept only Neo4j driver schemes and disallow URI credentials."""

        uri = value.strip()
        parsed = urlsplit(uri)
        allowed_schemes = {
            "bolt",
            "bolt+s",
            "bolt+ssc",
            "neo4j",
            "neo4j+s",
            "neo4j+ssc",
        }
        if parsed.scheme not in allowed_schemes:
            raise ValueError("NEO4J_URI must use a supported bolt or neo4j scheme")
        if not parsed.hostname:
            raise ValueError("NEO4J_URI must include a hostname")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("NEO4J_URI must not contain credentials")
        return uri

    @field_validator("username", "database")
    @classmethod
    def validate_non_empty_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be empty")
        return cleaned

    @model_validator(mode="after")
    def load_legacy_auth(self) -> "Neo4jSettings":
        """Translate the legacy ``NEO4J_AUTH`` value without exposing it."""

        if self.auth is None or self.password.get_secret_value():
            return self

        legacy_auth = self.auth.get_secret_value()
        if "/" not in legacy_auth:
            raise ValueError("NEO4J_AUTH must have the form username/password")
        username, password = legacy_auth.split("/", 1)
        if not username or not password:
            raise ValueError("NEO4J_AUTH must include a username and password")
        self.username = username
        self.password = SecretStr(password)
        return self

    @property
    def uses_encrypted_transport(self) -> bool:
        """Return whether the URI requests certificate-protected transport."""

        return urlsplit(self.uri).scheme in {
            "bolt+s",
            "bolt+ssc",
            "neo4j+s",
            "neo4j+ssc",
        }

    @property
    def uses_trusted_certificate(self) -> bool:
        """Return whether TLS also verifies the server certificate."""

        return urlsplit(self.uri).scheme in {"bolt+s", "neo4j+s"}

    def validate_for_environment(
        self,
        environment: Literal["development", "testing", "staging", "production"],
    ) -> None:
        """Apply deployment-sensitive credential and transport requirements."""

        if environment in {"staging", "production"}:
            if not self.uses_trusted_certificate:
                raise ValueError(
                    "certificate-verified Neo4j TLS is required in staging and production"
                )
            if not self.password.get_secret_value():
                raise ValueError("NEO4J_PASSWORD is required in staging and production")


class Settings(BaseSettings):
    """Runtime settings isolated from the existing services by ``API_`` prefix."""

    name: str = "Job Matching API"
    version: str = "0.1.0"
    environment: Literal["development", "testing", "staging", "production"] = (
        "development"
    )
    debug: bool = False
    docs_enabled: bool = True
    neo4j: Neo4jSettings = Field(default_factory=Neo4jSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="API_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return one settings instance for the lifetime of the process."""

    return Settings()


__all__ = ["Neo4jSettings", "Settings", "get_settings"]
