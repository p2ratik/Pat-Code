import base64
import json
import secrets
from typing import Any
from urllib.parse import urlencode, urljoin

import httpx
from mcp.client.auth.oauth2 import (
    PKCEParameters,
    build_oauth_authorization_server_metadata_discovery_urls,
    build_protected_resource_metadata_discovery_urls,
    create_client_registration_request,
    create_oauth_metadata_request,
    extract_resource_metadata_from_www_auth,
    extract_scope_from_www_auth,
    get_client_metadata_scopes,
    handle_auth_metadata_response,
    handle_protected_resource_response,
    handle_registration_response,
    resource_url_from_server_url,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata
from pydantic import AnyHttpUrl


async def build_authorization_flow(server_url: str, redirect_uri: str) -> dict[str, Any]:
    """Discover MCP OAuth metadata, register a client, and build the authorization URL."""
    async with httpx.AsyncClient(follow_redirects=False, timeout=15.0) as client:
        initial_response = await client.get(server_url)
        resource_metadata_url = extract_resource_metadata_from_www_auth(initial_response)

        protected_resource = None
        for url in build_protected_resource_metadata_discovery_urls(resource_metadata_url, server_url):
            response = await client.send(create_oauth_metadata_request(url))
            protected_resource = await handle_protected_resource_response(response)
            if protected_resource:
                break

        auth_server_url = (
            str(protected_resource.authorization_servers[0])
            if protected_resource and protected_resource.authorization_servers
            else None
        )

        oauth_metadata = None
        for url in build_oauth_authorization_server_metadata_discovery_urls(auth_server_url, server_url):
            response = await client.send(create_oauth_metadata_request(url))
            should_continue, metadata = await handle_auth_metadata_response(response)
            if metadata:
                oauth_metadata = metadata
                break
            if not should_continue:
                break

        scopes = get_client_metadata_scopes(
            extract_scope_from_www_auth(initial_response),
            protected_resource,
            oauth_metadata,
        )
        client_metadata = OAuthClientMetadata(
            client_name="PAT MCP Client",
            redirect_uris=[AnyHttpUrl(redirect_uri)],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            scope=scopes,
        )

        auth_base_url = _authorization_base_url(auth_server_url or server_url)
        registration_request = create_client_registration_request(
            oauth_metadata,
            client_metadata,
            auth_base_url,
        )
        registration_response = await client.send(registration_request)
        client_info = await handle_registration_response(registration_response)

    pkce = PKCEParameters.generate()
    state = secrets.token_urlsafe(32)
    authorization_endpoint = (
        str(oauth_metadata.authorization_endpoint)
        if oauth_metadata and oauth_metadata.authorization_endpoint
        else urljoin(auth_base_url, "/authorize")
    )
    resource = _resource_for_flow(server_url, protected_resource)
    auth_params = {
        "response_type": "code",
        "client_id": client_info.client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": pkce.code_challenge,
        "code_challenge_method": "S256",
    }
    if scopes:
        auth_params["scope"] = scopes
    if resource:
        auth_params["resource"] = resource

    token_endpoint = (
        str(oauth_metadata.token_endpoint)
        if oauth_metadata and oauth_metadata.token_endpoint
        else urljoin(auth_base_url, "/token")
    )

    return {
        "state": state,
        "authorization_url": f"{authorization_endpoint}?{urlencode(auth_params)}",
        "code_verifier": pkce.code_verifier,
        "redirect_uri": redirect_uri,
        "token_endpoint": token_endpoint,
        "client_info": client_info.model_dump(mode="json", exclude_none=True),
        "resource": resource,
    }


async def exchange_authorization_code(flow: dict[str, Any], code: str) -> dict[str, Any]:
    """Exchange an OAuth authorization code for provider tokens."""
    client_info = OAuthClientInformationFull.model_validate(flow["client_info"])
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": flow["redirect_uri"],
        "client_id": client_info.client_id,
        "code_verifier": flow["code_verifier"],
    }
    if flow.get("resource"):
        token_data["resource"] = flow["resource"]

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    auth_method = client_info.token_endpoint_auth_method
    if auth_method == "client_secret_basic" and client_info.client_secret:
        credentials = f"{client_info.client_id}:{client_info.client_secret}"
        headers["Authorization"] = "Basic " + base64.b64encode(credentials.encode()).decode()
    elif auth_method == "client_secret_post" and client_info.client_secret:
        token_data["client_secret"] = client_info.client_secret

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(flow["token_endpoint"], data=token_data, headers=headers)
        response.raise_for_status()
        return response.json()


def dumps_flow(flow: dict[str, Any]) -> str:
    return json.dumps(flow)


def loads_flow(raw: str) -> dict[str, Any]:
    return json.loads(raw)


def _authorization_base_url(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _resource_for_flow(server_url: str, protected_resource: Any) -> str | None:
    if not protected_resource:
        return None
    if protected_resource.resource:
        return str(protected_resource.resource)
    return resource_url_from_server_url(server_url)
