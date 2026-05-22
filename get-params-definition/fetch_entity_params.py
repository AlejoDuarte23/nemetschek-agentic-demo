"""
Fetch VIKTOR entity parameters via REST API.

This script retrieves entity data including parameter values and types
from a VIKTOR workspace using the REST API.
"""

import json
import os
from typing import Any

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class EntityResponse(BaseModel):
    """Entity response from VIKTOR REST API."""

    id: int
    name: str
    properties: dict[str, Any] | None = None
    entity_type: int
    entity_type_name: str | None = None
    parent_count: int = 0
    path: list[int] = Field(default_factory=list)


class ViktorRestClient:
    """Minimal VIKTOR REST API client."""

    def __init__(
        self,
        *,
        api_base: str,
        token: str,
        connect_timeout: float = 5.0,
        read_timeout: float = 30.0,
    ) -> None:
        token = token.strip()
        if not token:
            raise ValueError("Missing VIKTOR token.")

        base = api_base.strip().rstrip("/")
        self.api_base = base if base.endswith("/api") else f"{base}/api"
        self.timeout = (connect_timeout, read_timeout)
        self.auth_headers = {"Authorization": f"Bearer {token}"}

    def _url(self, path: str) -> str:
        """Build full URL from path."""
        return f"{self.api_base}/{path.lstrip('/')}"

    def _check(self, response: requests.Response, *, action: str) -> None:
        """Check response status and raise on error."""
        if response.ok:
            return
        body = response.text[:500]
        raise RuntimeError(f"{action} failed (status={response.status_code}): {body}")

    def get_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        action: str = "GET request",
    ) -> Any:
        """Execute GET request and return JSON."""
        url = self._url(path)
        response = requests.get(url, headers=self.auth_headers, params=params, timeout=self.timeout)
        self._check(response, action=action)
        return response.json()

    def get_entity(
        self,
        *,
        workspace_id: int,
        entity_id: int,
        properties: bool = False,
        clean_params: bool = False,
        param_types: bool = False,
    ) -> EntityResponse:
        """Fetch entity data with optional parameter information."""
        payload = self.get_json(
            f"workspaces/{workspace_id}/entities/{entity_id}/",
            params={
                "properties": str(properties).lower(),
                "clean_params": str(clean_params).lower(),
                "param_types": str(param_types).lower(),
            },
            action="Get entity",
        )
        return EntityResponse.model_validate(payload)

    def build_entity_editor_url(self, *, workspace_id: int, entity_id: int) -> str:
        """Build the UI URL for the entity editor."""
        ui_base = self.api_base[:-4] if self.api_base.endswith("/api") else self.api_base
        return f"{ui_base}/workspaces/{workspace_id}/app/editor/{entity_id}"


def get_api_base() -> str:
    """Build API base URL from environment."""
    environment = os.environ.get("VIKTOR_ENVIRONMENT", "cloud").strip().rstrip("/")
    if not environment:
        raise ValueError("Missing VIKTOR_ENVIRONMENT.")

    if environment.startswith("http"):
        base = environment
    elif environment.endswith(".viktor.ai"):
        base = f"https://{environment}"
    else:
        base = f"https://{environment}.viktor.ai"

    return base if base.endswith("/api") else f"{base}/api"


def main() -> None:
    """Fetch and display entity parameters."""
    # Load environment variables
    load_dotenv()

    # Get configuration
    token = os.environ.get("VK_TOKEN")
    if not token or not token.strip():
        raise ValueError("Missing VK_TOKEN in .env file. Please add your Personal Access Token.")

    workspace_id = int(os.environ.get("WORKSPACE_ID", "2494"))
    entity_id = int(os.environ.get("ENTITY_ID", "11967"))

    # Initialize client
    api_base = get_api_base()
    client = ViktorRestClient(api_base=api_base, token=token)

    print(f"Fetching entity {entity_id} from workspace {workspace_id}...")
    print(f"API Base: {api_base}")
    print()

    # Fetch entity with full parameter information
    entity = client.get_entity(
        workspace_id=workspace_id,
        entity_id=entity_id,
        properties=True,
        clean_params=True,
        param_types=True,
    )

    # Display results
    print(f"Entity ID: {entity.id}")
    print(f"Entity Name: {entity.name}")
    print(f"Entity Type: {entity.entity_type_name} (ID: {entity.entity_type})")
    print(f"Parent Count: {entity.parent_count}")
    print(f"Path: {entity.path}")
    print()

    # Display editor URL
    editor_url = client.build_entity_editor_url(workspace_id=workspace_id, entity_id=entity.id)
    print(f"Editor URL: {editor_url}")
    print()

    # Save full response to JSON file
    output_file = f"entity_{entity_id}_params.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(entity.model_dump(exclude_none=True), f, indent=2, ensure_ascii=False)

    print(f"Full entity data saved to: {output_file}")

    # Display properties if available
    if entity.properties:
        print("\nParameter Structure:")
        print(json.dumps(entity.properties, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
