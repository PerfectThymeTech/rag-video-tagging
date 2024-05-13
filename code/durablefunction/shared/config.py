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
    AZURE_OPEN_AI_BASE_URL: str = "https://durable-aoai001.openai.azure.com/"
    AZURE_OPEN_AI_API_VERSION: str = "2024-02-15-preview"
    AZURE_OPEN_AI_DEPLOYMENT_NAME: str = "gpt-4"
    AZURE_OPEN_AI_TEMPERATURE: float = 0.0

    NEWSTAGEXTRACTION_SYSTEM_PROMPT: str = """
    You are a world class assistant for identifying news sections.
    Do the following with the provided news content and provide a valid JSON response that uses the schema mentioned below:
    1. Split the provided news content into broad thematic sections. The content of each section must cover a common news topic, whereas each section must comply with the following rules:
        a) The first sentence in the provided news content must be part of the first section. The last sentence in the provided news content must be part of the last section.
        b) Each section must start and end with a full sentence.
        c) Each section should consist of at least 3 sentences.
        d) Every sentences of the provided new content must be part of exactly one section. If you are unsure about one sentence, then assign it to the previous section.
        e) The last sentence of one section must by followed by the first sentence of the next section.
        f) The sections are not allowed to overlap and must be mutually exclusive.
        g) It is ok if some sections consist of 20 or more sentences and other sections only consist of 3 or more sentences.
    3. You must find the first sentence and last sentence of each section. Define the first sentence as start and the last sentence as end.
    4. Generate a title for each news section.
    5. Add tags to each section. Samples for tags are: sports, weather, international news, national news, politics, crime, technology, celebrity, other. Add up to 5 additional tags based on the content of each section.
    6. Generate a score between 0 and 10 for each section. The score indicates how good the defined tags match the content of the section. 0 indicates that the tags don't match the content, and 10 means that the tags are a perfect match.
    7. Translate the title and tags for each section into the language of the news content.
    Here is a sample JSON response:
    {format_sample}
    """
    NEWSTAGEXTRACTION_USER_PROMPT: str = """
    News Content: "{news_content}"
    ---
    Identify news sections for the provided news text according to the instructions. The text is from the following tv show: {news_show_details}
    """


settings = Settings()
