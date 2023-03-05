# pylint: disable=too-few-public-methods

"""
Application Settings.

The settings file contains all the configuration of the application.
Use this file to configure any parameters that should be set server-side.

Settings can be adjusted depending on the environment the app is running on.
The environment is usually defined by the `APP_ENV` OS environment variable that
can be set on the local machine or on the server.

!!! warning !!!
For security reason, do not put in this file any secret key.
Add them as OS environment variables or put them in the `.env` file.

https://github.com/theskumar/python-dotenv

"""

import os
import pathlib

import pydantic

from sap.settings import DatabaseParams, IntegrationParams


class TestcasesParams(pydantic.BaseModel):
    """
    Parameters to for testcases.

    This params are only used to automate testcases.
    """

    beans_card_id: str = ""
    beans_access_token: str = ""


class _Settings(pydantic.BaseSettings):
    """
    Application Settings.

    The setting are load from environment variables:
    https://pydantic-docs.helpmanual.io/usage/settings/

    All env variable should be prefixed with APP_SETTINGS_
    For example to set the LOG_DIR, use: APP_SETTINGS_LOG_DIR="/tmp/"
    """

    # Envs
    APP_ENV: str = os.getenv("APP_ENV", "DEV")
    LOG_DIR: str = "/tmp/"
    APP_DIR: pathlib.Path = pathlib.Path(__file__).parent.parent

    # Databases
    MONGO: DatabaseParams
    RABBITMQ: DatabaseParams
    REDIS: DatabaseParams

    # Tokens
    CRYPTO_SECRET: str  # a key used for encryption
    AIRTABLE_TOKEN: str = ""
    BEANS_OAUTH_URL: str = "https://connect.trybeans.com/auth/authorize/?client_id={client_id}"

    TESTCASES: TestcasesParams = TestcasesParams()
    TOKENIFY: IntegrationParams

    class Config:
        env_nested_delimiter = "__"
        env_prefix = "APP_SETTINGS_"
        env_file = os.getenv("APP_DOTENV", ".env")


AppSettings = _Settings()
