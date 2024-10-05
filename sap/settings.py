"""Settings utils."""

import os

import pydantic


class IntegrationParams(pydantic.BaseModel):
    """
    Parameters to access an external API.

    These parameters can be set directly in the environment variables.
    ex: to set the public key for Beans you can use:
    APP_SETTINGS_<CUSTOM>__BEANS_PUBLIC=tls_public_xxxxxxxxx
    """

    app_domain: str = "http://localhost:8000"
    beans_public: str = ""
    beans_secret: str = ""
    third_party_public: str = ""
    third_party_secret: str = ""
    third_party_bearer: str = ""
    is_status_available: bool = True


class DatabaseParams(pydantic.BaseModel):
    """
    Parameters to connect the database.

    These parameters can be set directly in the environment variables.
    ex: to set the host you can use for mongodb:
    APP_SETTINGS_MONGO__HOST=example.com
    """

    protocol: str = "mongodb"
    username: str = ""
    password: str = ""
    db: str = "sap"
    host: str = "localhost"
    port: str = ""
    params: str = ""

    def get_dns(self) -> str:
        """Build the DNS URI for the database."""
        credentials: str = f"{self.username}:{self.password}@" if self.username else ""
        port: str = f":{self.port}" if self.port else ""
        query: str = f"?{self.params}" if self.params else ""
        return f"{self.protocol}://{credentials}{self.host}{port}/{self.db}{query}"


class SapSettings:
    """Settings params for SAP."""

    APP_ENV: str = os.getenv("APP_ENV", "").upper()

    # True is environment is set to DEV
    is_env_dev: bool = APP_ENV == "DEV"

    # True is environment is set to PROD
    is_env_prod: bool = APP_ENV == "PROD"
