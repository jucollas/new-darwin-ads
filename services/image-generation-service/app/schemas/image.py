from pydantic import BaseModel, field_validator


class GenerateImageRequest(BaseModel):
    prompt: str
    aspect_ratio: str = "1:1"
    campaign_id: str
    proposal_id: str

    @field_validator("prompt")
    @classmethod
    def prompt_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("prompt cannot be empty")
        return v.strip()

    @field_validator("aspect_ratio")
    @classmethod
    def valid_ratio(cls, v: str) -> str:
        allowed = {"1:1", "9:16", "16:9", "4:3", "3:4"}
        if v not in allowed:
            raise ValueError(f"aspect_ratio must be one of {allowed}")
        return v


class GenerateImageResponse(BaseModel):
    image_url: str
    storage_path: str
    campaign_id: str
    proposal_id: str


class DeleteImageResponse(BaseModel):
    deleted: bool
    storage_path: str
