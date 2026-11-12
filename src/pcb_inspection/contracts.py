from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

CLASS_NAMES = ["open_circuit", "short_circuit", "mouse_bite", "spur", "spurious_copper", "pin_hole"]
CLASS_COLORS = ["#ff6b6b", "#f5b94e", "#b08cff", "#56cce8", "#53d6a0", "#ff8eba"]


class InferenceProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_id: str = "quality-v1"
    imgsz: int = Field(default=640, ge=320, le=2048)
    confidence: float = Field(default=0.25, ge=0.001, le=1)
    iou: float = Field(default=0.5, gt=0, le=1)
    tiled: bool = False
    end2end: bool = False
    nms: bool = True
    device: str = "cpu"


class InspectionRequest(BaseModel):
    image_id: str
    model_id: str
    profile_id: str


class ReviewRequest(BaseModel):
    defect_id: str | None = None
    verdict: Literal["confirmed", "rejected", "uncertain", "missed"]
    note: str = Field(default="", max_length=2000)
