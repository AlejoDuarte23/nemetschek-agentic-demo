from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.tools.viktor_tools.responses import (
    execution_error_response,
    tool_response,
    validation_error_response,
)


class ListSkillFilesArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReadSkillFileArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relative_path: str = Field(
        default="SKILL.md",
        description="Path relative to the optimization skill folder.",
    )


class SkillTools:
    """Tools for listing and reading files from one local skill folder."""

    def __init__(
        self,
        skills_root: Path,
        skill_name: str,
        max_chars: int = 30_000,
        allowed_suffixes: set[str] | None = None,
    ) -> None:
        self.skills_root = Path(skills_root)
        self.skill_name = skill_name
        self.max_chars = max_chars
        self.allowed_suffixes = allowed_suffixes or {".md", ".json", ".txt", ".py"}

    @property
    def root(self) -> Path:
        return self.skills_root / self.skill_name

    @property
    def tool_names(self) -> set[str]:
        return {"list_skill_files", "read_skill_file"}

    def tool_schemas(self) -> list[dict[str, Any]]:
        """Responses API function tool schemas for this skill folder."""
        return [
            {
                "type": "function",
                "name": "list_skill_files",
                "description": (
                    "Discover available documentation files about app features, "
                    "workflows, and engineering concepts."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "read_skill_file",
                "description": (
                    "Read documentation about app features, configuration options, "
                    "workflows, or engineering concepts."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "relative_path": {
                            "type": "string",
                            "description": (
                                "Path relative to the skill folder, for example "
                                "SKILL.md or examples.md."
                            ),
                        }
                    },
                    "required": ["relative_path"],
                    "additionalProperties": False,
                },
            },
        ]

    def execute(self, name: str, args: dict[str, Any] | None = None) -> str:
        """Execute a skill tool and return a JSON string for function_call_output."""
        args = args or {}
        try:
            if name == "list_skill_files":
                return self.list_skill_files()
            if name == "read_skill_file":
                return self.read_skill_file(
                    relative_path=str(args.get("relative_path") or "SKILL.md")
                )
            return tool_response(
                "error",
                message=f"Unknown skill tool: {name}",
            )
        except Exception as exc:
            return tool_response(
                "error",
                message=str(exc),
            )

    def list_skill_files(self) -> str:
        root = self.root

        if not root.exists():
            return tool_response(
                "error",
                message=f"Missing skill folder: {root}",
            )

        files: list[str] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in self.allowed_suffixes:
                continue
            relative_path = path.relative_to(root)
            if any(part.startswith(".") for part in relative_path.parts):
                continue
            files.append(str(relative_path).replace("\\", "/"))

        return tool_response(
            "ok",
            skill=self.skill_name,
            files=files,
        )

    def read_skill_file(self, relative_path: str) -> str:
        path = self.safe_skill_path(relative_path)
        content = path.read_text(encoding="utf-8", errors="replace")

        return tool_response(
            "ok",
            skill=self.skill_name,
            relative_path=relative_path,
            content=content[: self.max_chars],
            truncated=len(content) > self.max_chars,
        )

    def safe_skill_path(self, relative_path: str) -> Path:
        root = self.root.resolve()
        path = (root / relative_path).resolve()
        if root not in (path, *path.parents):
            raise ValueError(f"Skill path escapes the skill folder: {relative_path}")
        if not path.is_file():
            raise FileNotFoundError(f"Skill file not found: {relative_path}")
        if path.suffix.lower() not in self.allowed_suffixes:
            raise ValueError(f"Skill file suffix is not allowed: {relative_path}")
        return path


def get_optimization_skill_tools() -> SkillTools:
    skills_root = Path(__file__).resolve().parents[1] / "skills"
    return SkillTools(skills_root=skills_root, skill_name="optimization")


async def list_skill_files_func(context: Any, args: str) -> str:
    try:
        ListSkillFilesArgs.model_validate_json(args or "{}")
        return get_optimization_skill_tools().list_skill_files()
    except ValidationError as exc:
        return validation_error_response(
            tool="list_skill_files",
            message="Invalid skill listing arguments.",
            error=exc,
            retry_tool="list_skill_files",
        )
    except Exception as exc:
        return execution_error_response(
            tool="list_skill_files",
            message="Could not list local skill files.",
            error=exc,
        )


async def read_skill_file_func(context: Any, args: str) -> str:
    try:
        payload = ReadSkillFileArgs.model_validate_json(args or "{}")
        return get_optimization_skill_tools().read_skill_file(payload.relative_path)
    except ValidationError as exc:
        return validation_error_response(
            tool="read_skill_file",
            message="Invalid skill read arguments.",
            error=exc,
            retry_tool="read_skill_file",
        )
    except Exception as exc:
        return execution_error_response(
            tool="read_skill_file",
            message="Could not read local skill file.",
            error=exc,
        )
