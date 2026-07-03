import uuid
from sqlalchemy import select
from api.db.database import CloudDatabase
from api.db.models import IntegrationProvider
from api.integrations.models import IntegrationProviderCreate, IntegrationProviderUpdate
from api.integrations.encryption import encrypt_token

class IntegrationService:
    """CRUD service for IntegrationProviders."""

    def __init__(self, db: CloudDatabase):
        self.db = db

    async def list_providers(self) -> list[dict]:
        async with self.db.get_session() as session:
            result = await session.execute(select(IntegrationProvider).order_by(IntegrationProvider.name))
            providers = result.scalars().all()
            return [self._to_dict(p) for p in providers]

    async def create_provider(self, data: IntegrationProviderCreate) -> dict:
        async with self.db.get_session() as session:
            provider = IntegrationProvider(
                name=data.name,
                display_name=data.display_name,
                auth_type=data.auth_type,
                client_id=encrypt_token(data.client_id) if data.client_id else None,
                client_secret=encrypt_token(data.client_secret) if data.client_secret else None,
                auth_url=data.auth_url,
                token_url=data.token_url,
                revoke_url=data.revoke_url,
                max_scopes=data.max_scopes,
                icon_url=data.icon_url,
            )
            session.add(provider)
            await session.commit()
            await session.refresh(provider)
            return self._to_dict(provider)

    async def update_provider(self, name: str, data: IntegrationProviderUpdate) -> dict | None:
        async with self.db.get_session() as session:
            result = await session.execute(select(IntegrationProvider).where(IntegrationProvider.name == name))
            provider = result.scalar_one_or_none()
            if not provider:
                return None

            if data.display_name is not None:
                provider.display_name = data.display_name
            if data.client_id is not None:
                provider.client_id = encrypt_token(data.client_id)
            if data.client_secret is not None:
                provider.client_secret = encrypt_token(data.client_secret)
            if data.max_scopes is not None:
                provider.max_scopes = data.max_scopes
            if data.icon_url is not None:
                provider.icon_url = data.icon_url
            if data.enabled is not None:
                provider.enabled = data.enabled

            await session.commit()
            await session.refresh(provider)
            return self._to_dict(provider)

    def _to_dict(self, provider: IntegrationProvider) -> dict:
        return {
            "id": str(provider.id),
            "name": provider.name,
            "display_name": provider.display_name,
            "auth_type": provider.auth_type,
            "max_scopes": provider.max_scopes,
            "icon_url": provider.icon_url,
            "enabled": provider.enabled,
            "created_at": provider.created_at,
            "updated_at": provider.updated_at,
        }
