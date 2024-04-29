from pydantic import BaseModel


class HeartbeatResponse(BaseModel):
    is_alive: bool = True

    @staticmethod
    def to_json(obj) -> str:
        return obj.model_dump_json()

    @staticmethod
    def from_json(data: str):
        return HeartbeatResponse.model_validate_json(data)
