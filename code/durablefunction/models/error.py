from typing import Any

from pydantic import BaseModel


class ErrorModel(BaseModel):
    error_code: int
    error_message: str
    error_details: Any
