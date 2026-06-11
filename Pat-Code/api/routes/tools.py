"""
Tool registry routes (Phase 2).

Tools are seeded at startup from builtin tool names. These endpoints
let admins and users discover what tools exist in the system.
"""
from fastapi import APIRouter, Depends, Request
from api.auth.models import ToolResponse
from api.auth.dependencies import get_current_user

router = APIRouter(tags=["tools"])


@router.get("", response_model=list[ToolResponse])
async def list_tools(request: Request, current_user: dict = Depends(get_current_user)):
    auth_service = request.app.state.auth_service
    tools = await auth_service.list_tools()
    return [ToolResponse(**t) for t in tools]
