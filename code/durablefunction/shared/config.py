import logging

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "DurableFunctionOrchestrator"
    APP_VERSION: str = "v0.0.1"
    LOGGING_LEVEL: int = logging.INFO
    FUNCTION_DEFAULT_ORCHESTRATOR_NAME: str = "video_extraction_orchestrator"
    # AZURE_AI_SPEECH_REGION: str = Field(default="", alias="AZURE_AI_SPEECH_REGION")
    # AZURE_AI_SPEECH_KEY: str = Field(default="", alias="AZURE_AI_SPEECH_KEY")
    HOME_DIRECTORY : str = Field(default="", alias="HOME")


settings = Settings()
