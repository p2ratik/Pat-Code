import os
import uuid
import logging
from datetime import datetime, timedelta
import jwt
from sqlalchemy import select, func
from api.db.database import CloudDatabase
from api.db.models import (
    User, Role, UserRole, AgentProfile, UserAgentProfile,
    ProfileTool, Tool, AuditLog,
)

logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Roles that bypass tool filtering (see all tools)
ADMIN_ROLES = {"super_admin", "admin"}


class AuthService:
    def __init__(self, db: CloudDatabase):
        self.db = db

    # ------------------------------------------------------------------
    # User CRUD
    # ------------------------------------------------------------------

    async def create_user(self, email: str, display_name: str) -> dict:
        async with self.db.get_session() as session:
            user = User(email=email, display_name=display_name)
            session.add(user)
            await session.commit()
            await session.refresh(user)

        # Auto-assign the default_user profile (secure-by-default).
        # Every user starts with a restricted tool set. Admins can upgrade.
        await self._assign_default_profile(str(user.id))

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

    # ------------------------------------------------------------------
    # Roles
    # ------------------------------------------------------------------

    async def get_user_roles(self, user_id: str) -> list[str]:
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Role.name)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == uuid.UUID(user_id))
            )
            return [row[0] for row in result.all()]

    async def assign_role(self, user_id: str, role_name: str, assigned_by: str | None = None):
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

            # Audit log
            session.add(AuditLog(
                user_id=uuid.UUID(assigned_by or user_id),
                action="ROLE_ASSIGNED",
                metadata_json={"target_user": user_id, "role": role_name},
            ))

            await session.commit()
            logger.info(f"Assigned role '{role_name}' to user {user_id}")

    async def has_admin_role(self, user_id: str) -> bool:
        roles = await self.get_user_roles(user_id)
        return bool(ADMIN_ROLES & set(roles))

    # ------------------------------------------------------------------
    # Agent Profiles
    # ------------------------------------------------------------------

    async def get_user_profile(self, user_id: str) -> dict | None:
        """Get the active agent profile assigned to this user."""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(AgentProfile)
                .join(UserAgentProfile, UserAgentProfile.profile_id == AgentProfile.id)
                .where(UserAgentProfile.user_id == uuid.UUID(user_id))
                .where(AgentProfile.is_active == True)
                .limit(1)
            )
            profile = result.scalar_one_or_none()
            if not profile:
                return None

            return {
                "id": str(profile.id),
                "name": profile.name,
                "description": profile.description,
                "model_name": profile.model_name,
                "temperature": profile.temperature,
                "max_turns": profile.max_turns,
                "version": profile.version,
                "is_active": profile.is_active,
            }

    async def _assign_default_profile(self, user_id: str) -> None:
        """Silently assign the seeded 'default_user' profile to a new user.

        If the default profile doesn't exist yet (e.g. seeding not done),
        log a warning and continue — create_user still succeeds, but the user
        will have no tools (fail-closed) until an admin assigns a profile.
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(AgentProfile).where(
                    AgentProfile.name == "default_user",
                    AgentProfile.is_active == True,
                )
            )
            profile = result.scalar_one_or_none()

        if not profile:
            logger.warning(
                f"Default profile 'default_user' not found — user {user_id} "
                f"has no tools. Run seed or assign a profile manually."
            )
            return

        # Use existing assign_profile logic (handles dedup + audit log)
        try:
            await self.assign_profile(user_id, str(profile.id), assigned_by=user_id)
        except Exception as e:
            logger.warning(f"Failed to auto-assign default profile to {user_id}: {e}")

    async def assign_profile(self, user_id: str, profile_id: str, assigned_by: str | None = None):
        """Assign an agent profile to a user. Replaces any existing assignment."""
        async with self.db.get_session() as session:
            # Verify profile exists
            result = await session.execute(
                select(AgentProfile).where(AgentProfile.id == uuid.UUID(profile_id))
            )
            profile = result.scalar_one_or_none()
            if not profile:
                raise ValueError(f"Profile not found: {profile_id}")

            # Remove existing assignments for this user
            existing = await session.execute(
                select(UserAgentProfile).where(
                    UserAgentProfile.user_id == uuid.UUID(user_id)
                )
            )
            for row in existing.scalars().all():
                await session.delete(row)

            # Assign new profile
            session.add(UserAgentProfile(
                user_id=uuid.UUID(user_id),
                profile_id=uuid.UUID(profile_id),
            ))

            # Audit log
            session.add(AuditLog(
                user_id=uuid.UUID(assigned_by or user_id),
                action="PROFILE_UPDATED",
                metadata_json={"target_user": user_id, "profile_id": profile_id, "profile_name": profile.name},
            ))

            await session.commit()
            logger.info(f"Assigned profile '{profile.name}' to user {user_id}")

    async def list_profiles(self) -> list[dict]:
        """List all active agent profiles."""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(AgentProfile).where(AgentProfile.is_active == True)
            )
            profiles = result.scalars().all()
            return [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "description": p.description,
                    "model_name": p.model_name,
                    "temperature": p.temperature,
                    "max_turns": p.max_turns,
                    "version": p.version,
                }
                for p in profiles
            ]

    async def create_profile(
        self,
        name: str,
        model_name: str,
        temperature: float = 0.7,
        max_turns: int = 100,
        description: str | None = None,
    ) -> dict:
        """Create a new agent profile."""
        async with self.db.get_session() as session:
            profile = AgentProfile(
                name=name,
                description=description,
                model_name=model_name,
                temperature=temperature,
                max_turns=max_turns,
                version=1,
            )
            session.add(profile)
            await session.commit()
            await session.refresh(profile)

            return {
                "id": str(profile.id),
                "name": profile.name,
                "description": profile.description,
                "model_name": profile.model_name,
                "temperature": profile.temperature,
                "max_turns": profile.max_turns,
                "version": profile.version,
            }

    # ------------------------------------------------------------------
    # Tool Authorization (Phase 2 core)
    # ------------------------------------------------------------------

    async def get_allowed_tools(self, user_id: str) -> list[str] | None:
        """Resolve the tool whitelist for a user.

        Flow: user → roles → admin check
              user → user_agent_profiles → agent_profiles → profile_tools → tools

        Returns:
            None  = all tools allowed (admins only)
            []    = no tools (no profile assigned, or profile has no tools)
            list  = only these tool names are visible to the model

        SECURITY: Fail-closed. No profile → empty list, not all tools.
        Bug in profile assignment → user gets no tools, not all tools.
        """
        # Admin bypass — admins see everything
        if await self.has_admin_role(user_id):
            return None

        async with self.db.get_session() as session:
            # Find user's active profile
            result = await session.execute(
                select(AgentProfile.id)
                .join(UserAgentProfile, UserAgentProfile.profile_id == AgentProfile.id)
                .where(UserAgentProfile.user_id == uuid.UUID(user_id))
                .where(AgentProfile.is_active == True)
                .limit(1)
            )
            profile_row = result.first()
            if not profile_row:
                # No profile assigned → deny all tools (fail-closed)
                logger.warning(f"User {user_id} has no agent profile — denying all tools")
                return []

            profile_id = profile_row[0]

            # Get tool names from profile_tools join
            result = await session.execute(
                select(Tool.name)
                .join(ProfileTool, ProfileTool.tool_id == Tool.id)
                .where(ProfileTool.profile_id == profile_id)
            )
            tool_names = [row[0] for row in result.all()]

            # Empty profile_tools → deny all (profile exists but no tools configured)
            if not tool_names:
                logger.warning(f"User {user_id} profile has no tools configured — denying all tools")
                return []

            return tool_names

    async def get_profile_tools(self, profile_id: str) -> list[dict]:
        """Get tools assigned to a specific profile."""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Tool)
                .join(ProfileTool, ProfileTool.tool_id == Tool.id)
                .where(ProfileTool.profile_id == uuid.UUID(profile_id))
            )
            tools = result.scalars().all()
            return [
                {"id": str(t.id), "name": t.name, "description": t.description}
                for t in tools
            ]

    async def assign_tools_to_profile(self, profile_id: str, tool_names: list[str]):
        """Replace the tool set for a profile. Accepts tool names, resolves to IDs."""
        async with self.db.get_session() as session:
            # Verify profile exists
            result = await session.execute(
                select(AgentProfile).where(AgentProfile.id == uuid.UUID(profile_id))
            )
            if not result.scalar_one_or_none():
                raise ValueError(f"Profile not found: {profile_id}")

            # Resolve tool names to IDs
            result = await session.execute(
                select(Tool).where(Tool.name.in_(tool_names))
            )
            found_tools = result.scalars().all()
            found_names = {t.name for t in found_tools}
            missing = set(tool_names) - found_names
            if missing:
                raise ValueError(f"Unknown tools: {', '.join(sorted(missing))}")

            # Remove old assignments
            old = await session.execute(
                select(ProfileTool).where(ProfileTool.profile_id == uuid.UUID(profile_id))
            )
            for row in old.scalars().all():
                await session.delete(row)

            # Add new assignments
            for tool in found_tools:
                session.add(ProfileTool(
                    profile_id=uuid.UUID(profile_id),
                    tool_id=tool.id,
                ))

            await session.commit()
            logger.info(f"Assigned {len(found_tools)} tools to profile {profile_id}")

    async def list_tools(self) -> list[dict]:
        """List all registered tools."""
        async with self.db.get_session() as session:
            result = await session.execute(select(Tool).order_by(Tool.name))
            tools = result.scalars().all()
            return [
                {"id": str(t.id), "name": t.name, "description": t.description}
                for t in tools
            ]

    # ------------------------------------------------------------------
    # JWT
    # ------------------------------------------------------------------

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
