import logging
from typing import List

from pydantic import BaseModel, Field, FilePath, HttpUrl, field_validator
from pydantic.dataclasses import dataclass


@dataclass
class Timestamp(BaseModel):
    start: str
    offset: str


@dataclass
class VideoExtractionOrchestratorRequest(BaseModel):
    content_url: HttpUrl
    timestamps: List[Timestamp]

    @field_validator("content_url", mode="after")
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


@dataclass
class DownloadVideoRequest(BaseModel):
    storage_domain_name: str
    storage_container_name: str = Field(min_length=3, max_length=63)
    storage_blob_name: str
    instance_id: str


@dataclass
class UploadVideoRequest(BaseModel):
    video_file_path: FilePath
    storage_domain_name: str
    storage_container_name: str = Field(min_length=3, max_length=63)
    instance_id: str


@dataclass
class DeleteVideoRequest(BaseModel):
    video_file_path: FilePath
    instance_id: str
