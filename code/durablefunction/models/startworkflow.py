from typing import Any, Dict
from enum import Enum

from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass
from shared.config import settings

class OrchestratorWorkflowEnum(str, Enum):
    VIDEOEXTRACTION = "video_extraction_orchestrator"


@dataclass
class StartWorkflowRequest(BaseModel):
    orchestrator_workflow_name: OrchestratorWorkflowEnum = Field(
        default=settings.FUNCTION_DEFAULT_ORCHESTRATOR_NAME,
        alias="orchestrator_workflow_name",
    )
    orchestrator_workflow_properties: Dict[str, Any] | None = Field(
        default=None, alias="orchestrator_workflow_properties"
    )
