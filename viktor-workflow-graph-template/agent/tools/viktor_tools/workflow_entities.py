import copy
import json
import os
from datetime import datetime
from typing import Any, Literal

import requests
import viktor as vkt
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.tools.viktor_tools.responses import (
    execution_error_response,
    tool_response,
    validation_error_response,
)
from agent.tools.viktor_tools.sdk_compute import (
    get_optional_environment,
    get_required_token,
)
from agent.tools.viktor_tools.wind_turbine_common import (
    COST_STORAGE_KEY,
    CPT_PILE_BEARING_STORAGE_KEY,
    FOUNDATION_STORAGE_KEY,
    REINFORCEMENT_STORAGE_KEY,
    WIND_TURBINE_SELECTOR_STORAGE_KEY,
)
from workflow_graph.models import Connection, Node, Workflow
from workflow_graph.state import build_canvas_state, save_canvas_state
from workflow_graph.viewer import WorkflowViewer


WORKFLOW_ENTITY_DIRECTORY_KEY = "workflow_entity_directory"

WorkflowNodeId = Literal[
    "wind_turbine_selector",
    "cpt_pile_bearing",
    "foundation_analysis",
    "reinforcement",
    "cost_analysis",
]


class WorkflowAppTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: WorkflowNodeId
    app_name: str
    label: str
    workspace_id: int
    sibling_entity_id: int
    method_name: str
    result_key: str
    storage_key: str
    icon: str
    icon_bg: str
    depends_on: list[WorkflowNodeId] = Field(default_factory=list)


class WorkflowRunEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: WorkflowNodeId
    app_name: str
    label: str
    workspace_id: int
    sibling_entity_id: int
    entity_id: int
    entity_name: str
    url: str
    method_name: str
    result_key: str
    storage_key: str
    icon: str
    icon_bg: str
    depends_on: list[WorkflowNodeId] = Field(default_factory=list)


class WorkflowEntityDirectory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_name: str
    created_at: str
    storage_key: str = WORKFLOW_ENTITY_DIRECTORY_KEY
    entities: dict[WorkflowNodeId, WorkflowRunEntity]


class CreateWorkflowEntityDirectoryArgs(BaseModel):
    run_name: str | None = Field(
        default=None,
        description="Optional run name. Defaults to 'Workflow Run - YYYY-MM-DD HH:MM'.",
    )
    include_nodes: list[WorkflowNodeId] = Field(
        ...,
        min_length=1,
        description="Known workflow nodes to create. Upstream dependencies are added by default.",
    )
    include_dependencies: bool = Field(
        default=True,
        description="Automatically add upstream dependencies required by selected nodes.",
    )
    replace_existing: bool = Field(
        default=False,
        description="Replace an existing active workflow entity directory.",
    )


class GetWorkflowEntityDirectoryArgs(BaseModel):
    pass


class ResetWorkflowEntityDirectoryArgs(BaseModel):
    confirm: bool = Field(
        default=False,
        description="Must be true to clear the active workflow entity directory.",
    )


class RestEntityResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    name: str
    entity_type: int | str
    entity_type_name: str | None = None
    properties: dict[str, Any] | None = None


WORKFLOW_APP_REGISTRY: dict[WorkflowNodeId, WorkflowAppTemplate] = {
    "wind_turbine_selector": WorkflowAppTemplate(
        node_id="wind_turbine_selector",
        app_name="Wind Turbine Selector",
        label="Wind Turbine Selector",
        workspace_id=2544,
        sibling_entity_id=12164,
        method_name="view_turbine_data",
        result_key="data",
        storage_key=WIND_TURBINE_SELECTOR_STORAGE_KEY,
        icon="WT",
        icon_bg="#dbeafe",
        depends_on=[],
    ),
    "cpt_pile_bearing": WorkflowAppTemplate(
        node_id="cpt_pile_bearing",
        app_name="CPT Pile Bearing",
        label="CPT Pile Bearing",
        workspace_id=2564,
        sibling_entity_id=12165,
        method_name="view_results",
        result_key="data",
        storage_key=CPT_PILE_BEARING_STORAGE_KEY,
        icon="CPT",
        icon_bg="#dcfce7",
        depends_on=[],
    ),
    "foundation_analysis": WorkflowAppTemplate(
        node_id="foundation_analysis",
        app_name="Wind Turbine Foundation Analysis",
        label="Foundation Analysis",
        workspace_id=2677,
        sibling_entity_id=12173,
        method_name="view_results",
        result_key="data",
        storage_key=FOUNDATION_STORAGE_KEY,
        icon="FND",
        icon_bg="#fef3c7",
        depends_on=["wind_turbine_selector", "cpt_pile_bearing"],
    ),
    "reinforcement": WorkflowAppTemplate(
        node_id="reinforcement",
        app_name="Reinforcement",
        label="Reinforcement",
        workspace_id=2640,
        sibling_entity_id=12166,
        method_name="view_results",
        result_key="data",
        storage_key=REINFORCEMENT_STORAGE_KEY,
        icon="RF",
        icon_bg="#ede9fe",
        depends_on=["foundation_analysis"],
    ),
    "cost_analysis": WorkflowAppTemplate(
        node_id="cost_analysis",
        app_name="Wind Turbine Cost Analysis",
        label="Cost Analysis",
        workspace_id=2647,
        sibling_entity_id=12169,
        method_name="view_data",
        result_key="data",
        storage_key=COST_STORAGE_KEY,
        icon="$",
        icon_bg="#ccfbf1",
        depends_on=["foundation_analysis", "reinforcement"],
    ),
}


def default_run_name() -> str:
    return f"Workflow Run - {datetime.now().strftime('%Y-%m-%d %H:%M')}"


def normalize_api_base() -> str:
    configured_base = os.getenv("VIKTOR_API_BASE")
    if configured_base and configured_base.strip():
        base = configured_base.strip().rstrip("/")
        if not base.startswith("https://"):
            raise ValueError("VIKTOR_API_BASE must be an absolute HTTPS URL.")
        return base if base.endswith("/api") else f"{base}/api"

    environment = get_optional_environment() or "demo.viktor.ai"
    host = environment.strip().rstrip("/")
    if host.startswith("https://"):
        host = host.removeprefix("https://")
    if "/" in host or not host.endswith(".viktor.ai"):
        raise ValueError("VIKTOR_ENVIRONMENT must be host-only, for example demo.viktor.ai.")
    return f"https://{host}/api"


class ViktorRestEntityClient:
    def __init__(
        self,
        *,
        token: str | None = None,
        api_base: str | None = None,
        connect_timeout: float = 5.0,
        read_timeout: float = 30.0,
    ) -> None:
        self.api_base = (api_base or normalize_api_base()).strip().rstrip("/")
        self.timeout = (connect_timeout, read_timeout)
        self.auth_headers = {"Authorization": f"Bearer {(token or get_required_token()).strip()}"}

    @property
    def ui_base(self) -> str:
        return self.api_base[:-4] if self.api_base.endswith("/api") else self.api_base

    def editor_url(self, *, workspace_id: int, entity_id: int) -> str:
        return f"{self.ui_base}/workspaces/{workspace_id}/app/editor/{entity_id}"

    def _url(self, path: str) -> str:
        return f"{self.api_base}/{path.lstrip('/')}"

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        action: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        allow_not_found: bool = False,
    ) -> Any | None:
        response = requests.request(
            method,
            self._url(path),
            headers={
                **self.auth_headers,
                **({"Content-Type": "application/json"} if json_body is not None else {}),
            },
            params=params,
            json=json_body,
            timeout=self.timeout,
        )
        body = response.text[:500]
        if allow_not_found and response.status_code == 404:
            return None
        if (
            allow_not_found
            and response.status_code == 403
            and ("parent" in body.lower() or "tree" in body.lower())
        ):
            return None
        if response.ok:
            if not response.text.strip():
                return {}
            return response.json()
        raise RuntimeError(f"{action} failed (status={response.status_code}): {body}")

    def get_entity(
        self,
        *,
        workspace_id: int,
        entity_id: int,
        properties: bool = False,
        clean_params: bool = False,
    ) -> RestEntityResponse:
        payload = self._request_json(
            "GET",
            f"workspaces/{workspace_id}/entities/{entity_id}/",
            params={
                "properties": str(properties).lower(),
                "clean_params": str(clean_params).lower(),
                "param_types": "false",
            },
            action="Get entity",
        )
        return RestEntityResponse.model_validate(payload)

    def get_parent_entity(
        self,
        *,
        workspace_id: int,
        entity_id: int,
    ) -> RestEntityResponse | None:
        payload = self._request_json(
            "GET",
            f"workspaces/{workspace_id}/entities/{entity_id}/parent/",
            action="Get parent entity",
            allow_not_found=True,
        )
        if not payload:
            return None
        return RestEntityResponse.model_validate(payload)

    def create_entity(
        self,
        *,
        workspace_id: int,
        entity_type: int | str,
        name: str,
        parent_entity_id: int | None,
    ) -> RestEntityResponse:
        body = {"entity_type": entity_type, "name": name, "properties": {}}
        path = (
            f"workspaces/{workspace_id}/entities/{parent_entity_id}/entities/"
            if parent_entity_id
            else f"workspaces/{workspace_id}/entities/"
        )
        payload = self._request_json("POST", path, json_body=body, action="Create entity")
        if isinstance(payload, list):
            if not payload:
                raise RuntimeError("Create entity returned an empty list.")
            payload = payload[0]
        return RestEntityResponse.model_validate(payload)

    def set_entity_params(
        self,
        *,
        workspace_id: int,
        entity_id: int,
        params: dict[str, Any],
        message: str,
    ) -> None:
        entity = self.get_entity(workspace_id=workspace_id, entity_id=entity_id)
        self._request_json(
            "PUT",
            f"workspaces/{workspace_id}/entities/{entity_id}/",
            json_body={
                "name": entity.name,
                "properties": params,
                "message": message,
            },
            action="Set entity params",
        )


def save_entity_directory(directory: WorkflowEntityDirectory) -> None:
    vkt.Storage().set(
        WORKFLOW_ENTITY_DIRECTORY_KEY,
        data=vkt.File.from_data(directory.model_dump_json(indent=2)),
        scope="entity",
    )


def try_load_entity_directory() -> WorkflowEntityDirectory | None:
    try:
        stored_file = vkt.Storage().get(WORKFLOW_ENTITY_DIRECTORY_KEY, scope="entity")
        raw = stored_file.getvalue_binary().decode("utf-8")
        return WorkflowEntityDirectory.model_validate_json(raw)
    except Exception:
        return None


def load_entity_directory() -> WorkflowEntityDirectory:
    directory = try_load_entity_directory()
    if directory is None:
        raise FileNotFoundError(f"Missing VIKTOR Storage key '{WORKFLOW_ENTITY_DIRECTORY_KEY}'.")
    return directory


def delete_entity_directory() -> None:
    try:
        vkt.Storage().delete(WORKFLOW_ENTITY_DIRECTORY_KEY, scope="entity")
    except Exception:
        pass


def expand_node_ids(
    include_nodes: list[WorkflowNodeId],
    *,
    include_dependencies: bool,
) -> list[WorkflowNodeId]:
    ordered: list[WorkflowNodeId] = []

    def add(node_id: WorkflowNodeId) -> None:
        if include_dependencies:
            for dependency in WORKFLOW_APP_REGISTRY[node_id].depends_on:
                add(dependency)
        if node_id not in ordered:
            ordered.append(node_id)

    for node_id in include_nodes:
        add(node_id)
    return ordered


def create_empty_sibling_entity(
    *,
    client: ViktorRestEntityClient,
    template: WorkflowAppTemplate,
    run_name: str,
) -> WorkflowRunEntity:
    sibling = client.get_entity(
        workspace_id=template.workspace_id,
        entity_id=template.sibling_entity_id,
    )
    parent = client.get_parent_entity(
        workspace_id=template.workspace_id,
        entity_id=template.sibling_entity_id,
    )
    entity_name = f"{run_name} - {template.app_name}"
    try:
        created = client.create_entity(
            workspace_id=template.workspace_id,
            entity_type=sibling.entity_type,
            name=entity_name,
            parent_entity_id=parent.id if parent else None,
        )
    except RuntimeError:
        if not sibling.entity_type_name:
            raise
        created = client.create_entity(
            workspace_id=template.workspace_id,
            entity_type=sibling.entity_type_name,
            name=entity_name,
            parent_entity_id=parent.id if parent else None,
        )
    return WorkflowRunEntity(
        node_id=template.node_id,
        app_name=template.app_name,
        label=template.label,
        workspace_id=template.workspace_id,
        sibling_entity_id=template.sibling_entity_id,
        entity_id=created.id,
        entity_name=created.name,
        url=client.editor_url(workspace_id=template.workspace_id, entity_id=created.id),
        method_name=template.method_name,
        result_key=template.result_key,
        storage_key=template.storage_key,
        icon=template.icon,
        icon_bg=template.icon_bg,
        depends_on=template.depends_on,
    )


def save_workflow_graph_for_directory(directory: WorkflowEntityDirectory) -> None:
    included = set(directory.entities)
    workflow = Workflow(
        nodes=[
            Node(
                id=entity.node_id,
                title=entity.label,
                icon=entity.icon,
                icon_bg=entity.icon_bg,
                url=entity.url,
                depends_on=[
                    Connection(node_id=dependency)
                    for dependency in entity.depends_on
                    if dependency in included
                ],
            )
            for entity in directory.entities.values()
        ]
    )
    state = build_canvas_state(directory.run_name, workflow)
    viewer = WorkflowViewer(lambda: state)
    save_canvas_state(state)
    vkt.Storage().set(
        "workflow_html",
        data=vkt.File.from_data(
            json.dumps({"workflow_name": directory.run_name, "html": viewer.write()})
        ),
        scope="entity",
    )


def resolve_workflow_entity(node_id: WorkflowNodeId) -> WorkflowRunEntity:
    directory = load_entity_directory()
    try:
        return directory.entities[node_id]
    except KeyError as exc:
        raise KeyError(
            f"Workflow run does not include node '{node_id}'. "
            "Create a new directory including this node."
        ) from exc


def needs_workflow_run_response(*, tool: str, node_id: WorkflowNodeId) -> str:
    return tool_response(
        "needs_workflow_run",
        tool=tool,
        node_id=node_id,
        message=(
            "No active workflow entity directory includes this node. "
            "Create a workflow run first so the tool can use fresh VIKTOR entities."
        ),
        retry_action={
            "tool": "create_workflow_entity_directory",
            "reason": "Create fresh entities for the required workflow nodes.",
        },
    )


def read_last_saved_params(target: WorkflowRunEntity) -> dict[str, Any]:
    client = ViktorRestEntityClient()
    entity = client.get_entity(
        workspace_id=target.workspace_id,
        entity_id=target.entity_id,
        properties=True,
        clean_params=True,
    )
    return entity.properties or {}


def set_last_saved_params(
    target: WorkflowRunEntity,
    params: dict[str, Any],
    *,
    message: str,
) -> None:
    ViktorRestEntityClient().set_entity_params(
        workspace_id=target.workspace_id,
        entity_id=target.entity_id,
        params=params,
        message=message,
    )


def deep_merge_params(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in updates.items():
        if (
            isinstance(value, dict)
            and isinstance(merged.get(key), dict)
        ):
            merged[key] = deep_merge_params(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


async def create_workflow_entity_directory_func(context: Any, args: str) -> str:
    try:
        payload = CreateWorkflowEntityDirectoryArgs.model_validate_json(args or "{}")
    except ValidationError as exc:
        return validation_error_response(
            tool="create_workflow_entity_directory",
            message="Invalid workflow entity directory arguments.",
            error=exc,
            retry_tool="create_workflow_entity_directory",
            retry_reason="Retry with include_nodes containing known workflow node ids.",
        )

    existing = try_load_entity_directory()
    if existing and not payload.replace_existing:
        return tool_response(
            "workflow_exists",
            message="An active workflow entity directory already exists.",
            run_name=existing.run_name,
            directory_storage_key=WORKFLOW_ENTITY_DIRECTORY_KEY,
            retry_action={
                "tool": "get_workflow_entity_directory",
                "reason": "Inspect the existing run before replacing it.",
            },
        )

    try:
        run_name = (payload.run_name or default_run_name()).strip() or default_run_name()
        node_ids = expand_node_ids(
            list(dict.fromkeys(payload.include_nodes)),
            include_dependencies=payload.include_dependencies,
        )
        client = ViktorRestEntityClient()
        entities = {
            node_id: create_empty_sibling_entity(
                client=client,
                template=WORKFLOW_APP_REGISTRY[node_id],
                run_name=run_name,
            )
            for node_id in node_ids
        }
        directory = WorkflowEntityDirectory(
            run_name=run_name,
            created_at=datetime.now().isoformat(timespec="seconds"),
            entities=entities,
        )
        save_entity_directory(directory)
        save_workflow_graph_for_directory(directory)
    except Exception as exc:
        return execution_error_response(
            tool="create_workflow_entity_directory",
            message="Could not create fresh workflow entities.",
            error=exc,
        )

    return tool_response(
        "completed",
        message=(
            "Created fresh workflow entities. Open the node URLs, enter inputs, "
            "save each VIKTOR app, then ask the agent to run the workflow."
        ),
        run_name=directory.run_name,
        directory_storage_key=WORKFLOW_ENTITY_DIRECTORY_KEY,
        nodes=[entity.model_dump() for entity in directory.entities.values()],
    )


async def get_workflow_entity_directory_func(context: Any, args: str) -> str:
    try:
        GetWorkflowEntityDirectoryArgs.model_validate_json(args or "{}")
        directory = load_entity_directory()
    except FileNotFoundError:
        return tool_response(
            "needs_workflow_run",
            message="No active workflow entity directory exists.",
            retry_action={
                "tool": "create_workflow_entity_directory",
                "reason": "Create fresh entities for the required workflow nodes.",
            },
        )
    except Exception as exc:
        return execution_error_response(
            tool="get_workflow_entity_directory",
            message="Could not read the workflow entity directory.",
            error=exc,
        )

    return tool_response(
        "completed",
        run_name=directory.run_name,
        directory_storage_key=WORKFLOW_ENTITY_DIRECTORY_KEY,
        nodes=[entity.model_dump() for entity in directory.entities.values()],
    )


async def reset_workflow_entity_directory_func(context: Any, args: str) -> str:
    try:
        payload = ResetWorkflowEntityDirectoryArgs.model_validate_json(args or "{}")
    except ValidationError as exc:
        return validation_error_response(
            tool="reset_workflow_entity_directory",
            message="Invalid reset arguments.",
            error=exc,
            retry_tool="reset_workflow_entity_directory",
            retry_reason="Retry with confirm=true.",
        )

    if not payload.confirm:
        return tool_response(
            "confirmation_required",
            message="Set confirm=true to clear the active workflow entity directory.",
        )

    delete_entity_directory()
    return tool_response(
        "completed",
        message="Workflow entity directory cleared.",
        cleared_storage_key=WORKFLOW_ENTITY_DIRECTORY_KEY,
    )
