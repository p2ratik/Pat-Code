import os
import uuid
import logging
from datetime import datetime, timedelta
import jwt
from sqlalchemy import select
from api.db.database import CloudDatabase
from api.db.models import User, Role, UserRole

logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


class AuthService:
    def __init__(self, db: CloudDatabase):
        self.db = db

    async def create_user(self, email: str, display_name: str) -> dict:
        async with self.db.get_session() as session:
            user = User(email=email, display_name=display_name)
            session.add(user)
            await session.commit()
            await session.refresh(user)

            return {
                "id": str(user.id),
                "email": user.email,
                "display_name": user.display_name,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat(),
                "roles": [],
            }

    async def get_user(self, user_id: str) -> dict | None:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(User).where(User.id == uuid.UUID(user_id))
            )
            user = result.scalar_one_or_none()
            if not user:
                return None

            roles = await self.get_user_roles(user_id)

            return {
                "id": str(user.id),
                "email": user.email,
                "display_name": user.display_name,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat(),
                "roles": roles,
            }

    async def get_user_roles(self, user_id: str) -> list[str]:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Role.name)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == uuid.UUID(user_id))
            )
            return [row[0] for row in result.all()]

    async def assign_role(self, user_id: str, role_name: str):
        if not os.environ.get("DEV_MODE"):
            raise PermissionError("Role assignment disabled outside DEV_MODE")

        async with self.db.get_session() as session:
            # Find role
            result = await session.execute(
                select(Role).where(Role.name == role_name)
            )
            role = result.scalar_one_or_none()
            if not role:
                raise ValueError(f"Role not found: {role_name}")

            # Check if already assigned
            existing = await session.execute(
                select(UserRole).where(
                    UserRole.user_id == uuid.UUID(user_id),
                    UserRole.role_id == role.id,
                )
            )
            if existing.scalar_one_or_none():
                return

            user_role = UserRole(
                user_id=uuid.UUID(user_id),
                role_id=role.id,
            )
            session.add(user_role)
            await session.commit()
            logger.info(f"Assigned role '{role_name}' to user {user_id}")

    def create_token(self, user_id: str) -> str:
        secret = os.environ.get("JWT_SECRET", "dev-secret-change-me")
        payload = {
            "sub": user_id,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        }
        return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)

    def verify_token(self, token: str) -> dict:
        secret = os.environ.get("JWT_SECRET", "dev-secret-change-me")
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        return {"user_id": payload["sub"]}
