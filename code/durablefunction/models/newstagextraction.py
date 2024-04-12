from typing import List

from pydantic import BaseModel, Field, HttpUrl


class NewsTagExtractionOrchestratorRequest(BaseModel):
    content_url: HttpUrl


class ExtractTranscriptRequest(BaseModel):
    storage_domain_name: str
    storage_container_name: str = Field(min_length=3, max_length=63)
    storage_blob_name: str
    instance_id: str

    @staticmethod
    def to_json(obj) -> str:
        return obj.model_dump_json()

    @staticmethod
    def from_json(data: str):
        return ExtractTranscriptRequest.model_validate_json(data)


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


class VideoIndexerTranscript(BaseModel):
    transcript_text: str
    transcript: List[VideoIndexerTranscriptItem]

    @staticmethod
    def to_json(obj) -> str:
        return obj.model_dump_json()

    @staticmethod
    def from_json(data: str):
        return VideoIndexerTranscript.model_validate_json(data)
