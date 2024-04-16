import logging
from datetime import datetime, time
from typing import List

from pydantic import BaseModel, Field, HttpUrl, field_validator


class LoadOpenaiContentRequest(BaseModel):
    storage_domain_name: str
    storage_container_name: str = Field(min_length=3, max_length=63)
    storage_blob_name: str
    instance_id: str

    @staticmethod
    def to_json(obj) -> str:
        return obj.model_dump_json()

    @staticmethod
    def from_json(data: str):
        return LoadOpenaiContentRequest.model_validate_json(data)


class VideoTimestamp(BaseModel):
    start_time: time
    end_time: time


class LoadOpenaiContentResponse(BaseModel):
    video_timestamps: List[VideoTimestamp]

    @staticmethod
    def to_json(obj) -> str:
        return obj.model_dump_json()

    @staticmethod
    def from_json(data: str):
        return LoadOpenaiContentResponse.model_validate_json(data)


class LoadVideoContentRequest(BaseModel):
    storage_domain_name: str
    storage_container_name: str = Field(min_length=3, max_length=63)
    storage_blob_name: str
    instance_id: str

    @staticmethod
    def to_json(obj) -> str:
        return obj.model_dump_json()

    @staticmethod
    def from_json(data: str):
        return LoadVideoContentRequest.model_validate_json(data)


class LoadVideoContentResponse(BaseModel):
    video_file_path: str

    @staticmethod
    def to_json(obj) -> str:
        return obj.model_dump_json()

    @staticmethod
    def from_json(data: str):
        return LoadVideoContentResponse.model_validate_json(data)


class ExtractVideoClipRequest(BaseModel):
    video_file_path: str
    start_time: time
    end_time: time
    instance_id: str

    @staticmethod
    def to_json(obj) -> str:
        return obj.model_dump_json()

    @staticmethod
    def from_json(data: str):
        return ExtractVideoClipRequest.model_validate_json(data)


class ExtractVideoClipResponse(BaseModel):
    video_clip_file_path: str
    start_time: time
    end_time: time

    @staticmethod
    def to_json(obj) -> str:
        return obj.model_dump_json()

    @staticmethod
    def from_json(data: str):
        return ExtractVideoClipResponse.model_validate_json(data)


class UploadVideoRequest(BaseModel):
    video_file_path: str
    start_time: time
    end_time: time
    instance_id: str

    @staticmethod
    def to_json(obj) -> str:
        return obj.model_dump_json()

    @staticmethod
    def from_json(data: str):
        return UploadVideoRequest.model_validate_json(data)


class UploadVideoResponse(BaseModel):
    content_url_videoclip: str
    start_time: time
    end_time: time

    @staticmethod
    def to_json(obj) -> str:
        return obj.model_dump_json()

    @staticmethod
    def from_json(data: str):
        return UploadVideoResponse.model_validate_json(data)


class DeleteVideoRequest(BaseModel):
    instance_id: str

    @staticmethod
    def to_json(obj) -> str:
        return obj.model_dump_json()

    @staticmethod
    def from_json(data: str):
        return DeleteVideoRequest.model_validate_json(data)


class ContentOpenAiScene(BaseModel):
    id: str
    title: str
    rating: int
    reasoning: str
    description: str
    start_time: time
    end_time: time
    transcript: str
    translation: str

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def check_time(cls, s: str):
        try:
            t = datetime.strptime(s, "%H:%M:%S.%f").time()
        except ValueError:
            try:
                t = datetime.strptime(s, "%H:%M:%S").time()
            except ValueError:
                raise ValueError(
                    "Provided time does not follow the expected format. Expected format '%H:%M:%S.%f' (e.g. '0:04:57.32')"
                )
        return t


class ContentOpenAi(BaseModel):
    summary: str
    scenes: List[ContentOpenAiScene]

    @staticmethod
    def to_json(obj) -> str:
        return obj.model_dump_json()

    @staticmethod
    def from_json(data: str):
        return ContentOpenAi.model_validate_json(data)


class VideoExtractionOrchestratorRequest(BaseModel):
    content_url_video: HttpUrl
    content_url_openai: HttpUrl

    @field_validator("content_url_video", "content_url_openai", mode="after")
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
            logging.error(f"Username provided in content url: {u.username}")
            raise ValueError(
                f"Please provide a valid blob storage url without a username. Provided value '{u.username}'."
            )
        elif u.password:
            logging.error(f"Password provided in content url: {u.password}")
            raise ValueError(
                f"Please provide a valid blob storage url without a password. Provided value '{u.password}'."
            )
        return u


class VideoExtractionOrchestratorResponse(BaseModel):
    error_code: int = 0
    extracted_video_clips: List[UploadVideoResponse] = []
