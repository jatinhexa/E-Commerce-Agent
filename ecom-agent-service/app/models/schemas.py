"""Pydantic schemas for the agent service API."""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(
        ..., description="Chat session identifier"
    )
    message: str = Field(
        ..., min_length=1, description="The customer's message"
    )


class ChatResponse(BaseModel):
    session_id: str
    response: str = Field(description="The assistant's reply text")
    tool_data: list[dict] = Field(
        default_factory=list,
        description="Structured data from tool calls (products, orders, tickets, etc.)",
    )
    tool_names_used: list[str] = Field(
        default_factory=list,
        description="Names of tools that were called during this turn",
    )


class SessionCreateResponse(BaseModel):
    session_id: str


class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: list[dict]


class IndexSyncResponse(BaseModel):
    products: dict
    faq: dict
