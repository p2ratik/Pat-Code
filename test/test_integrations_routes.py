import os
import uuid
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

os.environ["INTEGRATION_ENCRYPTION_KEY"] = "52dpekz2CVoQtOXUuoX72r_7E6TjbVvFNw2RDbU20Co="

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.integrations.routes import router
from api.integrations.service import IntegrationService
from api.integrations.models import IntegrationProviderCreate, IntegrationProviderUpdate
from api.auth.dependencies import get_current_user
from api.integrations.encryption import decrypt_token

# --- IntegrationService Tests ---

@pytest.fixture
def mock_db():
    db = MagicMock()
    session = AsyncMock()
    session.__aenter__.return_value = session
    db.get_session.return_value = session
    return db

@pytest.mark.asyncio
async def test_integration_service_create_provider(mock_db):
    service = IntegrationService(db=mock_db)
    data = IntegrationProviderCreate(
        name="test_prov",
        display_name="Test Prov",
        auth_type="oauth2",
        client_id="my_client_id",
        client_secret="my_secret"
    )
    
    mock_session = mock_db.get_session.return_value
    
    result = await service.create_provider(data)
    
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
    
    added_provider = mock_session.add.call_args[0][0]
    assert added_provider.name == "test_prov"
    assert added_provider.display_name == "Test Prov"
    
    # Check encryption
    assert decrypt_token(added_provider.client_id) == "my_client_id"
    assert decrypt_token(added_provider.client_secret) == "my_secret"
    
    assert result["name"] == "test_prov"

@pytest.mark.asyncio
async def test_integration_service_update_provider(mock_db):
    service = IntegrationService(db=mock_db)
    
    existing_provider = MagicMock()
    existing_provider.id = uuid.uuid4()
    existing_provider.name = "test_prov"
    existing_provider.created_at = datetime.utcnow()
    existing_provider.updated_at = datetime.utcnow()
    
    mock_session = mock_db.get_session.return_value
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_provider
    mock_session.execute.return_value = mock_result
    
    update_data = IntegrationProviderUpdate(
        display_name="New Display",
        enabled=False
    )
    
    result = await service.update_provider("test_prov", update_data)
    
    assert existing_provider.display_name == "New Display"
    assert existing_provider.enabled is False
    mock_session.commit.assert_called_once()
    assert result["display_name"] == "New Display"

# --- API Route Tests ---

@pytest.fixture
def app_with_mocks():
    app = FastAPI()
    
    mock_integration_service = AsyncMock()
    mock_integration_service.list_providers.return_value = [
        {"id": "1", "name": "google", "display_name": "Google", "auth_type": "oauth2", "max_scopes": [], "icon_url": None, "enabled": True, "created_at": datetime.utcnow(), "updated_at": datetime.utcnow()}
    ]
    mock_integration_service.create_provider.return_value = {
        "id": "2", "name": "slack", "display_name": "Slack", "auth_type": "oauth2", "max_scopes": [], "icon_url": None, "enabled": True, "created_at": datetime.utcnow(), "updated_at": datetime.utcnow()
    }
    mock_integration_service.update_provider.return_value = {
        "id": "2", "name": "slack", "display_name": "Slack Updated", "auth_type": "oauth2", "max_scopes": [], "icon_url": None, "enabled": False, "created_at": datetime.utcnow(), "updated_at": datetime.utcnow()
    }
    
    mock_connection_manager = AsyncMock()
    mock_connection_manager.get_connections.return_value = [
        {"provider": "google", "display_name": "Google", "status": "connected", "connected_at": "2023-01-01T00:00:00", "last_used_at": None}
    ]
    mock_connection_manager.disconnect.return_value = {"provider": "google", "status": "disconnected"}
    mock_connection_manager.initiate_oauth.return_value = {"authorization_url": "http://auth", "state": "123"}
    mock_connection_manager.handle_callback.return_value = {"provider": "google", "status": "connected", "email": "test@test.com", "scopes": []}
    
    app.state.integration_service = mock_integration_service
    app.state.connection_manager = mock_connection_manager
    
    app.include_router(router, prefix="/integrations")
    
    app.dependency_overrides[get_current_user] = lambda: {"id": str(uuid.uuid4())}
    
    return app, mock_integration_service, mock_connection_manager

@pytest.fixture
def client(app_with_mocks):
    app, _, _ = app_with_mocks
    return TestClient(app)

def test_list_providers(client, app_with_mocks):
    _, svc, _ = app_with_mocks
    response = client.get("/integrations/providers")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "google"
    svc.list_providers.assert_called_once()

def test_create_provider(client, app_with_mocks):
    _, svc, _ = app_with_mocks
    response = client.post("/integrations/providers", json={
        "name": "slack",
        "display_name": "Slack"
    })
    assert response.status_code == 200
    assert response.json()["name"] == "slack"
    svc.create_provider.assert_called_once()

def test_update_provider(client, app_with_mocks):
    _, svc, _ = app_with_mocks
    response = client.patch("/integrations/providers/slack", json={
        "enabled": False
    })
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    svc.update_provider.assert_called_once()

def test_get_connections(client, app_with_mocks):
    _, _, conn_mgr = app_with_mocks
    response = client.get("/integrations/connections")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["provider"] == "google"
    conn_mgr.get_connections.assert_called_once()

def test_disconnect(client, app_with_mocks):
    _, _, conn_mgr = app_with_mocks
    response = client.delete("/integrations/connections/google")
    assert response.status_code == 200
    assert response.json()["status"] == "disconnected"
    conn_mgr.disconnect.assert_called_once()

def test_oauth_initiate(client, app_with_mocks):
    _, _, conn_mgr = app_with_mocks
    response = client.post("/integrations/oauth/initiate", json={
        "provider_name": "google",
        "redirect_uri": "http://localhost/cb"
    })
    assert response.status_code == 200
    assert response.json()["authorization_url"] == "http://auth"
    conn_mgr.initiate_oauth.assert_called_once()

def test_oauth_callback(client, app_with_mocks):
    _, _, conn_mgr = app_with_mocks
    response = client.post("/integrations/oauth/callback", json={
        "code": "authcode123",
        "state": "state123",
        "redirect_uri": "http://localhost/cb"
    })
    assert response.status_code == 200
    assert response.json()["status"] == "connected"
    assert response.json()["email"] == "test@test.com"
    conn_mgr.handle_callback.assert_called_once_with("authcode123", "state123", "http://localhost/cb")
