from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass


class OrchestratorWorkflowEnum(str, Enum):
    VIDEOEXTRACTION = "video_extraction_orchestrator"


@dataclass
class StartWorkflowRequest(BaseModel):
    orchestrator_workflow_name: OrchestratorWorkflowEnum = Field(
        default=OrchestratorWorkflowEnum.VIDEOEXTRACTION,
        alias="orchestrator_workflow_name",
    )
    orchestrator_workflow_properties: Dict[str, Any] | None = Field(
        default=None, alias="orchestrator_workflow_properties"
    )
