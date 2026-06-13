from fastapi import Depends, HTTPException, Request
from api.auth.service import AuthService


async def get_current_user(request: Request) -> dict:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = auth_header.split(" ", 1)[1]
    auth_service: AuthService = request.app.state.auth_service

    try:
        payload = auth_service.verify_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = await auth_service.get_user(payload["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="User account is disabled")

    return user
