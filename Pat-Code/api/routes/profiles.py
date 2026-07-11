"""
Profile and Tool management routes (Phase 2).

Endpoints:
    GET   /profiles              → list all active agent profiles
    POST  /profiles              → create a new profile
    PATCH /profiles/{id}         → update profile fields (admin only)
    GET   /profiles/{id}/tools   → list tools assigned to profile
    PUT   /profiles/{id}/tools   → replace tools for profile
    GET   /tools                 → list all registered tools
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from api.auth.models import (
    ProfileCreate, ProfileUpdate, ProfileResponse, ToolResponse, ProfileToolsAssign,
)
from api.auth.dependencies import get_current_user

router = APIRouter(tags=["profiles"])


# ------------------------------------------------------------------
# Agent Profiles
# ------------------------------------------------------------------

@router.get("", response_model=list[ProfileResponse])
async def list_profiles(request: Request, current_user: dict = Depends(get_current_user)):
    auth_service = request.app.state.auth_service
    is_admin = await auth_service.has_admin_role(current_user["id"])
    profiles = await auth_service.list_profiles(current_user["id"], is_admin=is_admin)
    return [ProfileResponse(**p) for p in profiles]


@router.post("", response_model=ProfileResponse)
async def create_profile(
    body: ProfileCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    auth_service = request.app.state.auth_service

    try:
        profile = await auth_service.create_profile(
            name=body.name,
            model_name=body.model_name,
            owner_user_id=current_user["id"],
            temperature=body.temperature,
            max_turns=body.max_turns,
            description=body.description,
            prompt_id=body.prompt_id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ProfileResponse(**profile)


@router.patch("/{profile_id}", response_model=ProfileResponse)
async def update_profile(
    profile_id: str,
    body: ProfileUpdate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    auth_service = request.app.state.auth_service
    is_admin = await auth_service.has_admin_role(current_user["id"])

    try:
        profile = await auth_service.update_profile(
            profile_id, body,
            requesting_user_id=current_user["id"],
            is_admin=is_admin,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
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
    is_admin = await auth_service.has_admin_role(current_user["id"])
    # Owners and admins may view; others get a 403.
    ownership_ok = await auth_service.is_profile_owner(
        profile_id, current_user["id"], is_admin
    )
    if not ownership_ok:
        raise HTTPException(status_code=403, detail="Not authorised to view this profile's tools")
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
    is_admin = await auth_service.has_admin_role(current_user["id"])

    ownership_ok = await auth_service.is_profile_owner(
        profile_id, current_user["id"], is_admin
    )
    if not ownership_ok:
        raise HTTPException(status_code=403, detail="Not authorised to modify this profile's tools")

    try:
        await auth_service.assign_tools_to_profile(profile_id, body.tool_names)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"detail": f"Assigned {len(body.tool_names)} tools to profile {profile_id}"}
