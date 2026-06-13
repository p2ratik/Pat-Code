"""
Profile and Tool management routes (Phase 2).

Endpoints:
    GET  /profiles              → list all active agent profiles
    POST /profiles              → create a new profile
    GET  /profiles/{id}/tools   → list tools assigned to profile
    PUT  /profiles/{id}/tools   → replace tools for profile
    GET  /tools                 → list all registered tools
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from api.auth.models import (
    ProfileCreate, ProfileResponse, ToolResponse, ProfileToolsAssign,
)
from api.auth.dependencies import get_current_user

router = APIRouter(tags=["profiles"])


# ------------------------------------------------------------------
# Agent Profiles
# ------------------------------------------------------------------

@router.get("", response_model=list[ProfileResponse])
async def list_profiles(request: Request, current_user: dict = Depends(get_current_user)):
    auth_service = request.app.state.auth_service
    profiles = await auth_service.list_profiles()
    return [ProfileResponse(**p) for p in profiles]


@router.post("", response_model=ProfileResponse)
async def create_profile(
    body: ProfileCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    auth_service = request.app.state.auth_service

    # Only admins can create profiles
    if not await auth_service.has_admin_role(current_user["id"]):
        raise HTTPException(status_code=403, detail="Only admins can create profiles")

    try:
        profile = await auth_service.create_profile(
            name=body.name,
            model_name=body.model_name,
            temperature=body.temperature,
            max_turns=body.max_turns,
            description=body.description,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ProfileResponse(**profile)


# ------------------------------------------------------------------
# Profile → Tool assignments
# ------------------------------------------------------------------

@router.get("/{profile_id}/tools", response_model=list[ToolResponse])
async def get_profile_tools(
    profile_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    auth_service = request.app.state.auth_service
    tools = await auth_service.get_profile_tools(profile_id)
    return [ToolResponse(**t) for t in tools]


@router.put("/{profile_id}/tools")
async def assign_tools_to_profile(
    profile_id: str,
    body: ProfileToolsAssign,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    auth_service = request.app.state.auth_service

    # Only admins can assign tools
    if not await auth_service.has_admin_role(current_user["id"]):
        raise HTTPException(status_code=403, detail="Only admins can modify profile tools")

    try:
        await auth_service.assign_tools_to_profile(profile_id, body.tool_names)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"detail": f"Assigned {len(body.tool_names)} tools to profile {profile_id}"}
