from fastapi import APIRouter, Depends, HTTPException, Request
from api.auth.models import (
    UserCreate, UserResponse, TokenResponse, RoleAssign,
    ProfileAssign, ProfileResponse,
)
from api.auth.dependencies import get_current_user

router = APIRouter(tags=["users"])


@router.get("", response_model=list[UserResponse])
async def list_users(request: Request, current_user: dict = Depends(get_current_user)):
    auth_service = request.app.state.auth_service
    users = await auth_service.list_users()
    return [UserResponse(**u) for u in users]


@router.post("", response_model=UserResponse)
async def create_user(body: UserCreate, request: Request):
    auth_service = request.app.state.auth_service

    try:
        user = await auth_service.create_user(body.email, body.display_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return UserResponse(**user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    auth_service = request.app.state.auth_service
    user = await auth_service.get_user(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(**user)


@router.post("/{user_id}/roles")
async def assign_role(
    user_id: str,
    body: RoleAssign,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    auth_service = request.app.state.auth_service

    try:
        await auth_service.assign_role(user_id, body.role_name, assigned_by=current_user["id"])
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"detail": f"Role '{body.role_name}' assigned to user {user_id}"}


@router.post("/{user_id}/token", response_model=TokenResponse)
async def generate_token(user_id: str, request: Request):
    auth_service = request.app.state.auth_service
    user = await auth_service.get_user(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token = auth_service.create_token(user_id)
    return TokenResponse(access_token=token)


# ------------------------------------------------------------------
# Phase 2: Profile assignment
# ------------------------------------------------------------------

@router.get("/{user_id}/profile", response_model=ProfileResponse | None)
async def get_user_profile(
    user_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    auth_service = request.app.state.auth_service
    profile = await auth_service.get_user_profile(user_id)

    if not profile:
        return None

    return ProfileResponse(**profile)


@router.post("/{user_id}/profile")
async def assign_profile(
    user_id: str,
    body: ProfileAssign,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    auth_service = request.app.state.auth_service

    # Only admins can assign profiles to other users
    if user_id != current_user["id"] and not await auth_service.has_admin_role(current_user["id"]):
        raise HTTPException(status_code=403, detail="Only admins can assign profiles to other users")

    try:
        await auth_service.assign_profile(user_id, body.profile_id, assigned_by=current_user["id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"detail": f"Profile assigned to user {user_id}"}
