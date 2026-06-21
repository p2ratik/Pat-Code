"""
Conversation history routes.

Endpoints:
    GET /conversations          → list conversations for the current user (newest first)
    GET /conversations/{id}/messages → get messages for a conversation
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from api.auth.dependencies import get_current_user

router = APIRouter(tags=["conversations"])


class ConversationOut(BaseModel):
    id: str
    title: str | None
    created_at: str
    updated_at: str


class MessageOut(BaseModel):
    id: str
    role: str
    content: str | None
    created_at: str


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    request: Request,
    current_user: dict = Depends(get_current_user),
    limit: int = Query(default=50, le=200),
):
    auth_service = request.app.state.auth_service
    conversations = await auth_service.list_user_conversations(
        current_user["id"], limit=limit
    )
    return [ConversationOut(**c) for c in conversations]


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
async def get_conversation_messages(
    conversation_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    auth_service = request.app.state.auth_service
    messages = await auth_service.get_conversation_messages(
        conversation_id, current_user["id"]
    )
    if messages is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return [MessageOut(**m) for m in messages]
