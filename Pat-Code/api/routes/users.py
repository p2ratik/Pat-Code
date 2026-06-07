from fastapi import APIRouter, Depends, HTTPException, Request
from api.auth.models import UserCreate, UserResponse, TokenResponse, RoleAssign
from api.auth.dependencies import get_current_user

router = APIRouter(tags=["users"])


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
        await auth_service.assign_role(user_id, body.role_name)
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
