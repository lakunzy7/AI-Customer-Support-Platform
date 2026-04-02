from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str | None = Field(
        default=None, description="Existing conversation ID to continue"
    )
    file_ids: list[str] = Field(
        default_factory=list, description="IDs of uploaded files to include as context"
    )


class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    cached: bool = False


class RagRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    top_k: int = Field(default=3, ge=1, le=10)


class RagResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)
    cached: bool = False
