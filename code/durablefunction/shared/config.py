import logging

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "DurableFunctionOrchestrator"
    APP_VERSION: str = "v0.0.1"
    LOGGING_LEVEL: int = logging.INFO
    HOME_DIRECTORY: str = Field(default="", alias="HOME")
    STORAGE_DOMAIN_NAME: str = Field(
        default="rgdurablefunctiona8c3.blob.core.windows.net",
        alias="STORAGE_DOMAIN_NAME",
    )
    STORAGE_CONTAINER_NAME: str = Field(
        default="video", alias="STORAGE_CONTAINER_NAME", min_length=3, max_length=63
    )
    FUNCTION_DEFAULT_ORCHESTRATOR_NAME: str = "video_extraction_orchestrator"


settings = Settings()
