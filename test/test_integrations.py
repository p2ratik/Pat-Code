import os
import uuid
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# Set encryption key before importing anything from integrations
os.environ["INTEGRATION_ENCRYPTION_KEY"] = "52dpekz2CVoQtOXUuoX72r_7E6TjbVvFNw2RDbU20Co="

from api.integrations.credential_manager import CredentialManager, TOKEN_CACHE_KEY
from api.integrations.connection_manager import ConnectionManager, _OAUTH_STATE_KEY
from api.integrations.providers.base import BaseProvider
from api.integrations.exceptions import (
    AuthorizationRequiredError,
    TokenExpiredError,
    InsufficientScopesError,
    ProviderNotEnabledError,
)
from api.integrations.encryption import encrypt_token

@pytest.fixture
def mock_db():
    db = MagicMock()
    session = AsyncMock()
    # Support async with db.get_session() as session:
    session.__aenter__.return_value = session
    db.get_session.return_value = session
    return db

@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get.return_value = None
    return redis

@pytest.fixture
def mock_provider():
    provider = AsyncMock(spec=BaseProvider)
    provider.name = "test_provider"
    provider.build_auth_url.return_value = "https://auth.url"
    provider.exchange_code.return_value = {
        "access_token": "new_access",
        "refresh_token": "new_refresh",
        "expires_in": 3600,
        "scope": "read write"
    }
    provider.refresh_token.return_value = {
        "access_token": "refreshed_access",
        "expires_in": 3600,
    }
    return provider

@pytest.fixture
def providers_dict(mock_provider):
    return {"test_provider": mock_provider}

@pytest.fixture
def credential_manager(mock_db, mock_redis, providers_dict):
    return CredentialManager(db=mock_db, redis=mock_redis, providers=providers_dict)

@pytest.fixture
def connection_manager(mock_db, mock_redis, credential_manager, providers_dict):
    return ConnectionManager(
        db=mock_db,
        redis=mock_redis,
        credential_manager=credential_manager,
        providers=providers_dict
    )

# --- ConnectionManager Tests ---

@pytest.mark.asyncio
async def test_initiate_oauth(connection_manager, mock_db, mock_redis, mock_provider):
    user_id = str(uuid.uuid4())
    
    # Mock _get_provider_row
    provider_row = MagicMock()
    provider_row.enabled = True
    provider_row.client_id = encrypt_token("client_id")
    
    mock_session = mock_db.get_session.return_value
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = provider_row
    mock_session.execute.return_value = mock_result
    
    # Mock _resolve_scopes
    mock_result_scopes = MagicMock()
    mock_result_scopes.first.return_value = (["read", "write"],)
    mock_session.execute.side_effect = [mock_result, mock_result_scopes]

    res = await connection_manager.initiate_oauth(user_id, "test_provider", "http://redirect")
    
    assert "authorization_url" in res
    assert "state" in res
    mock_redis.setex.assert_called_once()
    mock_provider.build_auth_url.assert_called_once()

@pytest.mark.asyncio
async def test_handle_callback(connection_manager, mock_db, mock_redis, mock_provider, credential_manager):
    user_id = str(uuid.uuid4())
    state = "test_state"
    
    # Mock Redis state
    mock_redis.get.return_value = json.dumps({
        "user_id": user_id,
        "provider": "test_provider",
        "redirect_uri": "http://redirect"
    })
    
    # Mock _get_provider_row
    provider_row = MagicMock()
    provider_row.id = uuid.uuid4()
    provider_row.client_id = encrypt_token("client_id")
    provider_row.client_secret = encrypt_token("client_secret")
    
    mock_session = mock_db.get_session.return_value
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = provider_row
    mock_session.execute.return_value = mock_result
    
    # Mock _upsert_connection
    conn_row = MagicMock()
    conn_row.id = uuid.uuid4()
    mock_result.scalar_one_or_none.side_effect = [provider_row, conn_row]

    # Mock fetch_provider_email (prevent real HTTP request)
    connection_manager._fetch_provider_email = AsyncMock(return_value="test@test.com")
    
    credential_manager.store_tokens = AsyncMock()

    res = await connection_manager.handle_callback("auth_code", state, "http://redirect")
    
    assert res["status"] == "connected"
    assert res["email"] == "test@test.com"
    assert "read" in res["scopes"]
    
    credential_manager.store_tokens.assert_called_once()
    mock_provider.exchange_code.assert_called_once()
    mock_redis.delete.assert_called_with(_OAUTH_STATE_KEY.format(state=state))

@pytest.mark.asyncio
async def test_disconnect(connection_manager, mock_db, mock_redis, mock_provider, credential_manager):
    user_id = str(uuid.uuid4())
    
    provider_row = MagicMock()
    provider_row.id = uuid.uuid4()
    provider_row.client_id = encrypt_token("client_id")
    provider_row.client_secret = encrypt_token("client_secret")
    
    conn_row = MagicMock()
    conn_row.credentials.encrypted_access_token = encrypt_token("access")
    
    mock_session = mock_db.get_session.return_value
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.side_effect = [provider_row, conn_row]
    mock_session.execute.return_value = mock_result
    
    credential_manager.invalidate_cache = AsyncMock()

    res = await connection_manager.disconnect(user_id, "test_provider")
    
    assert res["status"] == "disconnected"
    assert conn_row.status == "disconnected"
    assert conn_row.connected_at is None
    
    mock_provider.revoke_token.assert_called_once()
    credential_manager.invalidate_cache.assert_called_once_with(user_id, "test_provider")

# --- CredentialManager Tests ---

@pytest.mark.asyncio
async def test_get_client_cache_hit(credential_manager, mock_redis, mock_provider):
    user_id = "user1"
    provider = "test_provider"
    
    # Mock token in Redis
    mock_redis.get.return_value = "cached_token"
    
    # Mock _check_scopes and _touch_last_used
    credential_manager._check_scopes = AsyncMock()
    credential_manager._touch_last_used = AsyncMock()
    
    client = await credential_manager.get_client(provider, user_id, ["read"])
    
    mock_redis.get.assert_called_once_with(TOKEN_CACHE_KEY.format(user_id=user_id, provider=provider))
    mock_provider.build_client.assert_called_once_with("cached_token")
    credential_manager._check_scopes.assert_called_once_with(provider, user_id, ["read"])

@pytest.mark.asyncio
async def test_get_client_cache_miss_valid_db(credential_manager, mock_db, mock_redis, mock_provider):
    user_id = str(uuid.uuid4())
    provider = "test_provider"
    
    # Cache miss
    mock_redis.get.return_value = None
    
    # DB Hit valid token
    conn_row = MagicMock()
    provider_row = MagicMock(enabled=True)
    cred_row = MagicMock()
    cred_row.encrypted_access_token = encrypt_token("db_token")
    cred_row.expires_at = datetime.utcnow() + timedelta(hours=1)
    
    mock_session = mock_db.get_session.return_value
    
    # Mock _fetch_connection_row (it executes twice, one for connection+provider, one for credential)
    mock_result_conn = MagicMock()
    mock_result_conn.first.return_value = (conn_row, provider_row)
    
    mock_result_cred = MagicMock()
    mock_result_cred.scalar_one_or_none.return_value = cred_row
    
    mock_session.execute.side_effect = [mock_result_conn, mock_result_cred]
    
    credential_manager._check_scopes = AsyncMock()
    credential_manager._touch_last_used = AsyncMock()
    
    client = await credential_manager.get_client(provider, user_id, [])
    
    mock_redis.setex.assert_called_once_with(
        TOKEN_CACHE_KEY.format(user_id=user_id, provider=provider),
        2400, # 40 mins
        "db_token"
    )
    mock_provider.build_client.assert_called_once_with("db_token")

@pytest.mark.asyncio
async def test_get_client_cache_miss_expired_db_refresh(credential_manager, mock_db, mock_redis, mock_provider):
    user_id = str(uuid.uuid4())
    provider = "test_provider"
    
    mock_redis.get.return_value = None
    
    # DB Hit expired token
    conn_row = MagicMock()
    provider_row = MagicMock(enabled=True)
    provider_row.client_id = encrypt_token("client_id")
    provider_row.client_secret = encrypt_token("client_secret")
    
    cred_row = MagicMock()
    cred_row.encrypted_access_token = encrypt_token("old_db_token")
    cred_row.encrypted_refresh_token = encrypt_token("refresh_token")
    cred_row.expires_at = datetime.utcnow() - timedelta(hours=1) # Expired
    cred_row.id = uuid.uuid4()
    
    mock_session = mock_db.get_session.return_value
    
    mock_result_conn = MagicMock()
    mock_result_conn.first.return_value = (conn_row, provider_row)
    
    mock_result_cred = MagicMock()
    mock_result_cred.scalar_one_or_none.return_value = cred_row
    
    # The last execute is to get the cred again to update it during refresh
    mock_session.execute.side_effect = [mock_result_conn, mock_result_cred, mock_result_cred]
    
    credential_manager._check_scopes = AsyncMock()
    credential_manager._touch_last_used = AsyncMock()
    
    client = await credential_manager.get_client(provider, user_id, [])
    
    mock_provider.refresh_token.assert_called_once()
    mock_provider.build_client.assert_called_once_with("refreshed_access")
    
    mock_redis.setex.assert_called_once_with(
        TOKEN_CACHE_KEY.format(user_id=user_id, provider=provider),
        2400,
        "refreshed_access"
    )
    mock_session.commit.assert_called_once() # During refresh persist

@pytest.mark.asyncio
async def test_get_client_missing_scopes(credential_manager, mock_db):
    user_id = str(uuid.uuid4())
    provider = "test_provider"
    
    # Mock _resolve_token to just return string
    credential_manager._resolve_token = AsyncMock(return_value="token")
    
    # Mock DB return scopes missing
    mock_session = mock_db.get_session.return_value
    mock_result = MagicMock()
    mock_result.first.return_value = (["read"],)
    mock_session.execute.return_value = mock_result
    
    with pytest.raises(InsufficientScopesError) as exc:
        await credential_manager.get_client(provider, user_id, ["read", "write"])
        
    assert "write" in exc.value.missing_scopes
