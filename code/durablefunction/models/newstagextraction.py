import logging
from typing import List

from pydantic import AliasChoices, BaseModel, Field, HttpUrl, RootModel, field_validator


class NewsTagExtractionOrchestratorRequest(BaseModel):
    content_url_videoindexer: HttpUrl

    @field_validator("content_url_videoindexer", mode="after")
    @classmethod
    def check_content_url(cls, u: HttpUrl):
        if u.scheme != "https":
            logging.error(f"Scheme provided in content url: {u.port}")
            raise ValueError(
                f"Please provide a valid blob storage url with an 'https' scheme. Provided value '{u.scheme}'."
            )
        elif not u.host.endswith(".blob.core.windows.net"):
            logging.error(f"Host provided in content url: {u.port}")
            raise ValueError(
                f"Please provide a valid blob storage url with a '.blob.core.windows.net' host url. Provided value '{u.host}'."
            )
        elif not u.path or len(u.path.split("/")) <= 2:
            logging.error(f"Path provided in content url: {u.port}")
            raise ValueError(
                f"Please provide a valid blob storage url with a container and file name. Provided value '{u.path}'."
            )
        elif u.port and u.port != 443:
            logging.error(f"Port provided in content url: {u.port}")
            raise ValueError(
                f"Please provide a valid blob storage url without any port parameters. Provided value '{u.port}'."
            )
        elif u.query:
            logging.error(f"Query provided in content url: {u.query}")
            raise ValueError(
                f"Please provide a valid blob storage url without any query parameters. Provided value '{u.query}'."
            )
        elif u.fragment:
            logging.error(f"Fragment provided in content url: {u.fragment}")
            raise ValueError(
                f"Please provide a valid blob storage url without any url fragments. Provided value '{u.fragment}'."
            )
        elif u.username:
            logging.error(f"Username provided in content url: [REDACTED]")
            raise ValueError(
                f"Please provide a valid blob storage url without a username. Provided value '[REDACTED]'."
            )
        elif u.password:
            logging.error(f"Password provided in content url: [REDACTED]")
            raise ValueError(
                f"Please provide a valid blob storage url without a password. Provided value '[REDACTED]'."
            )
        return u


class LoadVideoindexerContentRequest(BaseModel):
    storage_domain_name: str
    storage_container_name: str = Field(min_length=3, max_length=63)
    storage_blob_name: str
    instance_id: str

    @staticmethod
    def to_json(obj) -> str:
        return obj.model_dump_json()

    @staticmethod
    def from_json(data: str):
        return LoadVideoindexerContentRequest.model_validate_json(data)


class VideoIndexerTranscriptInstance(BaseModel):
    adjustedStart: str
    adjustedEnd: str
    start: str
    end: str


class VideoIndexerTranscriptItem(BaseModel):
    id: int
    text: str
    confidence: float
    speaker_id: int = Field(default=None, alias="speakerId")
    language: str
    instances: List[VideoIndexerTranscriptInstance]
    index_start: int
    index_end: int


class LoadVideoindexerContentResponse(BaseModel):
    language: str
    transcript_text: str
    transcript: List[VideoIndexerTranscriptItem]

    @staticmethod
    def to_json(obj) -> str:
        return obj.model_dump_json()

    @staticmethod
    def from_json(data: str):
        return LoadVideoindexerContentResponse.model_validate_json(data)


class InvokeLlmRequest(BaseModel):
    content_text: str
    content_details: str
    content_language: str
    instance_id: str

    @staticmethod
    def to_json(obj) -> str:
        return obj.model_dump_json()

    @staticmethod
    def from_json(data: str):
        return InvokeLlmRequest.model_validate_json(data)


class LlmResponseItem(BaseModel):
    id: int = Field(description="id of the subsection")
    title: str = Field(description="title of the subsection")
    tags: List[str] = Field(description="tags of the subsection")
    score: int = Field(description="score of the subsection")
    start: str = Field(
        description="start of the text of the subsection",
        validation_alias=AliasChoices("start", "start_sentence"),
    )
    end: str = Field(
        description="end of the text of the subsection",
        validation_alias=AliasChoices("end", "end_sentence"),
    )

    def get_item_text(self, start: bool = True) -> str:
        if start:
            return self.start
        else:
            return self.end


class InvokeLlmResponse(BaseModel):
    sections: List[LlmResponseItem] = Field(
        description="list of items describing the subsections",
        validation_alias=AliasChoices("sections", "news_sections", "root"),
    )

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, item):
        return self.root[item]

    @staticmethod
    def to_json(obj) -> str:
        return obj.model_dump_json()

    @staticmethod
    def from_json(data: str):
        return InvokeLlmResponse.model_validate_json(data)


class ComputeTimestampsRequest(BaseModel):
    result_video_indexer: LoadVideoindexerContentResponse
    result_llm: List[LlmResponseItem]
    instance_id: str

    @staticmethod
    def to_json(obj) -> str:
        return obj.model_dump_json()

    @staticmethod
    def from_json(data: str):
        return ComputeTimestampsRequest.model_validate_json(data)


class ComputeTimestampsItem(BaseModel):
    id: int
    title: str
    tags: List[str]
    score: int
    start_time: str
    end_time: str


class ComputeTimestampsResponse(RootModel):
    root: List[ComputeTimestampsItem]

    @staticmethod
    def to_json(obj) -> str:
        return obj.model_dump_json()

    @staticmethod
    def from_json(data: str):
        return ComputeTimestampsResponse.model_validate_json(data)
