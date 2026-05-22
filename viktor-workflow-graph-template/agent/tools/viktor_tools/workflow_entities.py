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
WORKFLOW_HTML_STORAGE_KEY = "workflow_html"

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


class WorkflowAlreadyExistsError(RuntimeError):
    def __init__(self, directory: WorkflowEntityDirectory) -> None:
        super().__init__("An active workflow entity directory already exists.")
        self.directory = directory


class WorkflowAppRegistry:
    """Fixed app metadata for known workflow nodes."""

    def __init__(self, templates: dict[WorkflowNodeId, WorkflowAppTemplate]) -> None:
        self._templates = templates

    @classmethod
    def wind_turbine_defaults(cls) -> "WorkflowAppRegistry":
        return cls(
            {
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
        )

    def get(self, node_id: WorkflowNodeId) -> WorkflowAppTemplate:
        return self._templates[node_id]

    def as_dict(self) -> dict[WorkflowNodeId, WorkflowAppTemplate]:
        return dict(self._templates)

    def expand_node_ids(
        self,
        include_nodes: list[WorkflowNodeId],
        *,
        include_dependencies: bool,
    ) -> list[WorkflowNodeId]:
        ordered: list[WorkflowNodeId] = []

        def add(node_id: WorkflowNodeId) -> None:
            template = self.get(node_id)
            if include_dependencies:
                for dependency in template.depends_on:
                    add(dependency)
            if node_id not in ordered:
                ordered.append(node_id)

        for node_id in include_nodes:
            add(node_id)
        return ordered

    def selected_templates(
        self,
        include_nodes: list[WorkflowNodeId],
        *,
        include_dependencies: bool,
    ) -> list[WorkflowAppTemplate]:
        return [
            self.get(node_id)
            for node_id in self.expand_node_ids(
                include_nodes,
                include_dependencies=include_dependencies,
            )
        ]


class ViktorRestEntityClient:
    """Small REST client for entity reads, creation, and saved-param updates."""

    def __init__(
        self,
        *,
        token: str | None = None,
        api_base: str | None = None,
        connect_timeout: float = 5.0,
        read_timeout: float = 30.0,
    ) -> None:
        self.api_base = (api_base or self.normalize_api_base()).strip().rstrip("/")
        self.timeout = (connect_timeout, read_timeout)
        self.auth_headers = {"Authorization": f"Bearer {(token or get_required_token()).strip()}"}

    @staticmethod
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

    @property
    def ui_base(self) -> str:
        return self.api_base[:-4] if self.api_base.endswith("/api") else self.api_base

    def editor_url(self, *, workspace_id: int, entity_id: int) -> str:
        return f"{self.ui_base}/workspaces/{workspace_id}/app/editor/{entity_id}"

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

    def create_sibling_from_template(
        self,
        *,
        template: WorkflowAppTemplate,
        run_name: str,
    ) -> WorkflowRunEntity:
        sibling = self.get_entity(
            workspace_id=template.workspace_id,
            entity_id=template.sibling_entity_id,
        )
        parent = self.get_parent_entity(
            workspace_id=template.workspace_id,
            entity_id=template.sibling_entity_id,
        )
        entity_name = f"{run_name} - {template.app_name}"
        created = self._create_entity_with_fallback_type(
            workspace_id=template.workspace_id,
            entity_type=sibling.entity_type,
            fallback_entity_type=sibling.entity_type_name,
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
            url=self.editor_url(workspace_id=template.workspace_id, entity_id=created.id),
            method_name=template.method_name,
            result_key=template.result_key,
            storage_key=template.storage_key,
            icon=template.icon,
            icon_bg=template.icon_bg,
            depends_on=template.depends_on,
        )

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

    def _create_entity_with_fallback_type(
        self,
        *,
        workspace_id: int,
        entity_type: int | str,
        fallback_entity_type: str | None,
        name: str,
        parent_entity_id: int | None,
    ) -> RestEntityResponse:
        try:
            return self._create_entity(
                workspace_id=workspace_id,
                entity_type=entity_type,
                name=name,
                parent_entity_id=parent_entity_id,
            )
        except RuntimeError:
            if not fallback_entity_type:
                raise
            return self._create_entity(
                workspace_id=workspace_id,
                entity_type=fallback_entity_type,
                name=name,
                parent_entity_id=parent_entity_id,
            )

    def _create_entity(
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

    def _url(self, path: str) -> str:
        return f"{self.api_base}/{path.lstrip('/')}"


class WorkflowEntityStore:
    """Persists the active workflow run directory in VIKTOR entity storage."""

    def __init__(self, *, storage_key: str = WORKFLOW_ENTITY_DIRECTORY_KEY) -> None:
        self.storage_key = storage_key

    def save(self, directory: WorkflowEntityDirectory) -> None:
        vkt.Storage().set(
            self.storage_key,
            data=vkt.File.from_data(directory.model_dump_json(indent=2)),
            scope="entity",
        )

    def try_load(self) -> WorkflowEntityDirectory | None:
        try:
            stored_file = vkt.Storage().get(self.storage_key, scope="entity")
            raw = stored_file.getvalue_binary().decode("utf-8")
            return WorkflowEntityDirectory.model_validate_json(raw)
        except Exception:
            return None

    def load(self) -> WorkflowEntityDirectory:
        directory = self.try_load()
        if directory is None:
            raise FileNotFoundError(f"Missing VIKTOR Storage key '{self.storage_key}'.")
        return directory

    def delete(self) -> None:
        try:
            vkt.Storage().delete(self.storage_key, scope="entity")
        except Exception:
            pass


class WorkflowGraphPublisher:
    """Publishes the workflow graph/plan from a run directory."""

    def __init__(self, *, html_storage_key: str = WORKFLOW_HTML_STORAGE_KEY) -> None:
        self.html_storage_key = html_storage_key

    def publish(self, directory: WorkflowEntityDirectory) -> None:
        workflow = self._build_workflow(directory)
        state = build_canvas_state(directory.run_name, workflow)
        viewer = WorkflowViewer(lambda: state)
        save_canvas_state(state)
        vkt.Storage().set(
            self.html_storage_key,
            data=vkt.File.from_data(
                json.dumps({"workflow_name": directory.run_name, "html": viewer.write()})
            ),
            scope="entity",
        )

    @staticmethod
    def _build_workflow(directory: WorkflowEntityDirectory) -> Workflow:
        included = set(directory.entities)
        return Workflow(
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


class WorkflowEntityService:
    """Coordinates registry, REST entity creation, storage, and graph publishing."""

    def __init__(
        self,
        *,
        registry: WorkflowAppRegistry | None = None,
        store: WorkflowEntityStore | None = None,
        client: ViktorRestEntityClient | None = None,
        graph_publisher: WorkflowGraphPublisher | None = None,
    ) -> None:
        self.registry = registry or DEFAULT_WORKFLOW_REGISTRY
        self.store = store or WorkflowEntityStore()
        self.client = client
        self.graph_publisher = graph_publisher or WorkflowGraphPublisher()

    def create_directory(
        self,
        *,
        run_name: str | None,
        include_nodes: list[WorkflowNodeId],
        include_dependencies: bool,
        replace_existing: bool,
    ) -> WorkflowEntityDirectory:
        existing = self.store.try_load()
        if existing and not replace_existing:
            raise WorkflowAlreadyExistsError(existing)

        resolved_run_name = self._resolve_run_name(run_name)
        client = self.client or ViktorRestEntityClient()
        entities = {
            template.node_id: client.create_sibling_from_template(
                template=template,
                run_name=resolved_run_name,
            )
            for template in self.registry.selected_templates(
                list(dict.fromkeys(include_nodes)),
                include_dependencies=include_dependencies,
            )
        }
        directory = WorkflowEntityDirectory(
            run_name=resolved_run_name,
            created_at=datetime.now().isoformat(timespec="seconds"),
            entities=entities,
        )
        self.store.save(directory)
        self.graph_publisher.publish(directory)
        return directory

    def load_directory(self) -> WorkflowEntityDirectory:
        return self.store.load()

    def try_load_directory(self) -> WorkflowEntityDirectory | None:
        return self.store.try_load()

    def reset_directory(self) -> None:
        self.store.delete()

    def resolve_entity(self, node_id: WorkflowNodeId) -> WorkflowRunEntity:
        directory = self.load_directory()
        try:
            return directory.entities[node_id]
        except KeyError as exc:
            raise KeyError(
                f"Workflow run does not include node '{node_id}'. "
                "Create a new directory including this node."
            ) from exc

    def read_last_saved_params(self, target: WorkflowRunEntity) -> dict[str, Any]:
        entity = (self.client or ViktorRestEntityClient()).get_entity(
            workspace_id=target.workspace_id,
            entity_id=target.entity_id,
            properties=True,
            clean_params=True,
        )
        return entity.properties or {}

    def set_last_saved_params(
        self,
        target: WorkflowRunEntity,
        params: dict[str, Any],
        *,
        message: str,
    ) -> None:
        (self.client or ViktorRestEntityClient()).set_entity_params(
            workspace_id=target.workspace_id,
            entity_id=target.entity_id,
            params=params,
            message=message,
        )

    @staticmethod
    def deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
        merged = copy.deepcopy(base)
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = WorkflowEntityService.deep_merge(merged[key], value)
            else:
                merged[key] = copy.deepcopy(value)
        return merged

    @staticmethod
    def _resolve_run_name(value: str | None) -> str:
        return (value or default_run_name()).strip() or default_run_name()


DEFAULT_WORKFLOW_REGISTRY = WorkflowAppRegistry.wind_turbine_defaults()

# Kept for direct registry introspection and tests.
WORKFLOW_APP_REGISTRY: dict[WorkflowNodeId, WorkflowAppTemplate] = (
    DEFAULT_WORKFLOW_REGISTRY.as_dict()
)


def default_run_name() -> str:
    return f"Workflow Run - {datetime.now().strftime('%Y-%m-%d %H:%M')}"


def get_workflow_entity_service() -> WorkflowEntityService:
    return WorkflowEntityService()


def normalize_api_base() -> str:
    return ViktorRestEntityClient.normalize_api_base()


def save_entity_directory(directory: WorkflowEntityDirectory) -> None:
    WorkflowEntityStore().save(directory)


def try_load_entity_directory() -> WorkflowEntityDirectory | None:
    return WorkflowEntityStore().try_load()


def load_entity_directory() -> WorkflowEntityDirectory:
    return WorkflowEntityStore().load()


def delete_entity_directory() -> None:
    WorkflowEntityStore().delete()


def expand_node_ids(
    include_nodes: list[WorkflowNodeId],
    *,
    include_dependencies: bool,
) -> list[WorkflowNodeId]:
    return DEFAULT_WORKFLOW_REGISTRY.expand_node_ids(
        include_nodes,
        include_dependencies=include_dependencies,
    )


def create_empty_sibling_entity(
    *,
    client: ViktorRestEntityClient,
    template: WorkflowAppTemplate,
    run_name: str,
) -> WorkflowRunEntity:
    return client.create_sibling_from_template(template=template, run_name=run_name)


def save_workflow_graph_for_directory(directory: WorkflowEntityDirectory) -> None:
    WorkflowGraphPublisher().publish(directory)


def resolve_workflow_entity(node_id: WorkflowNodeId) -> WorkflowRunEntity:
    return get_workflow_entity_service().resolve_entity(node_id)


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
    return get_workflow_entity_service().read_last_saved_params(target)


def set_last_saved_params(
    target: WorkflowRunEntity,
    params: dict[str, Any],
    *,
    message: str,
) -> None:
    get_workflow_entity_service().set_last_saved_params(
        target,
        params,
        message=message,
    )


def deep_merge_params(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    return WorkflowEntityService.deep_merge(base, updates)


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

    try:
        directory = get_workflow_entity_service().create_directory(
            run_name=payload.run_name,
            include_nodes=payload.include_nodes,
            include_dependencies=payload.include_dependencies,
            replace_existing=payload.replace_existing,
        )
    except WorkflowAlreadyExistsError as exc:
        return tool_response(
            "workflow_exists",
            message=str(exc),
            run_name=exc.directory.run_name,
            directory_storage_key=WORKFLOW_ENTITY_DIRECTORY_KEY,
            retry_action={
                "tool": "get_workflow_entity_directory",
                "reason": "Inspect the existing run before replacing it.",
            },
        )
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
        directory = get_workflow_entity_service().load_directory()
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

    get_workflow_entity_service().reset_directory()
    return tool_response(
        "completed",
        message="Workflow entity directory cleared.",
        cleared_storage_key=WORKFLOW_ENTITY_DIRECTORY_KEY,
    )
