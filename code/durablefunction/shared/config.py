import logging

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "DurableFunctionOrchestrator"
    APP_VERSION: str = "v0.0.1"
    LOGGING_LEVEL: int = logging.INFO
    HOME_DIRECTORY: str = Field(default="", alias="HOME")
    FUNCTION_DEFAULT_ORCHESTRATOR_NAME: str = "video_extraction_orchestrator"


settings = Settings()
