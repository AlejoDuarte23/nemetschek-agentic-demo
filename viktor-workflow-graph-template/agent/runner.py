import asyncio
import queue
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import viktor as vkt
from agents import (
    Agent,
    ItemHelpers,
    MaxTurnsExceeded,
    Runner,
    set_default_openai_client,
    set_tracing_disabled,
)
from openai import AsyncOpenAI
from openai.types.responses import ResponseTextDeltaEvent

from agent.tools import TOOL_DISPLAY_NAMES, get_tools



PROMPT_PATH = Path(__file__).resolve().parent / "system_prompt.xml"
MAX_AGENT_TURNS = 20

event_loop: asyncio.AbstractEventLoop | None = None
event_loop_thread: threading.Thread | None = None


viktor_llm_client = AsyncOpenAI(
    base_url=vkt.ViktorOpenAI.get_base_url(version="v1"),
    api_key=vkt.ViktorOpenAI.get_api_key(),
)

set_default_openai_client(viktor_llm_client, use_for_tracing=False)
set_tracing_disabled(True)

@dataclass
class AgentContext:
    entity_id: int | None = None
    workspace_id: int | None = None


def load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def build_agent() -> Agent[AgentContext]:
    return Agent[AgentContext](
        name="VIKTOR Workflow Assistant",
        model="openai.gpt-oss-120b",
        instructions=load_system_prompt(),
        tools=get_tools(),
    )


def ensure_loop() -> asyncio.AbstractEventLoop:
    global event_loop, event_loop_thread
    if event_loop and event_loop.is_running():
        return event_loop
    event_loop = asyncio.new_event_loop()
    event_loop_thread = threading.Thread(
        target=event_loop.run_forever,
        name="agent-loop",
        daemon=True,
    )
    event_loop_thread.start()
    return event_loop


def extract_call_id(raw: Any) -> str | None:
    if isinstance(raw, dict):
        value = raw.get("call_id") or raw.get("id") or raw.get("tool_call_id")
        return str(value) if value else None
    for attr in ("call_id", "id", "tool_call_id"):
        value = getattr(raw, attr, None)
        if value:
            return str(value)
    return None


def extract_tool_name(raw: Any) -> str:
    if isinstance(raw, dict):
        if raw.get("name"):
            return str(raw["name"])
        fn = raw.get("function")
        if isinstance(fn, dict) and fn.get("name"):
            return str(fn["name"])
        if raw.get("tool_name"):
            return str(raw["tool_name"])
    for attr in ("name", "tool_name", "function_name"):
        value = getattr(raw, attr, None)
        if value:
            return str(value)
    fn = getattr(raw, "function", None)
    if fn is not None and getattr(fn, "name", None):
        return str(fn.name)
    return "tool"


def normalize_stream_text(text: str) -> str:
    return " ".join(text.split()).strip()


def workflow_agent_sync_stream(
    chat_history: list[dict[str, str]],
    *,
    context: AgentContext | None = None,
    on_done: Callable[[], None] | None = None,
    show_tool_progress: bool = True,
) -> Iterator[str]:
    output_queue: queue.Queue[object] = queue.Queue()
    sentinel = object()
    loop = ensure_loop()

    async def produce() -> None:
        call_id_to_name: dict[str, str] = {}
        pending_assistant_message: str | None = None
        streamed_text = ""
        try:
            result = Runner.run_streamed(
                build_agent(),
                input=chat_history,
                context=context or AgentContext(),
                max_turns=MAX_AGENT_TURNS,
            )

            async for event in result.stream_events():
                if event.type == "raw_response_event" and isinstance(
                    event.data,
                    ResponseTextDeltaEvent,
                ):
                    if event.data.delta:
                        streamed_text += event.data.delta
                        output_queue.put(event.data.delta)
                    continue

                if not show_tool_progress or event.type != "run_item_stream_event":
                    continue

                item = event.item
                raw = getattr(item, "raw_item", None)

                if (
                    event.name == "message_output_created"
                    and getattr(item, "type", None) == "message_output_item"
                ):
                    text = ItemHelpers.text_message_output(item).strip()
                    if text and normalize_stream_text(text) != normalize_stream_text(
                        streamed_text
                    ):
                        pending_assistant_message = text
                    else:
                        pending_assistant_message = None
                    streamed_text = ""
                    continue

                if event.name == "tool_called":
                    if pending_assistant_message:
                        output_queue.put(f"\n\n{pending_assistant_message}\n\n")
                        pending_assistant_message = None
                    call_id = extract_call_id(raw)
                    tool_name = extract_tool_name(raw)
                    if call_id:
                        call_id_to_name[call_id] = tool_name
                    display_name = TOOL_DISPLAY_NAMES.get(tool_name, tool_name)
                    output_queue.put(f"\n\n> Running **{display_name}**\n")
                    continue

                if event.name == "tool_output":
                    call_id = extract_call_id(raw)
                    tool_name = call_id_to_name.get(call_id or "", "tool")
                    display_name = TOOL_DISPLAY_NAMES.get(tool_name, tool_name)
                    output_queue.put(f"\n> Done **{display_name}**\n\n")
                    continue

        except MaxTurnsExceeded:
            output_queue.put(
                "\n\nThe agent exceeded the allowed number of turns. "
                "Try a smaller request or split the workflow into fewer tool calls.\n"
            )
        except Exception as exc:
            output_queue.put(f"\n\n{type(exc).__name__}: {exc}\n")
        finally:
            if pending_assistant_message:
                output_queue.put(f"\n\n{pending_assistant_message}\n\n")
            output_queue.put(sentinel)

    asyncio.run_coroutine_threadsafe(produce(), loop)

    def stream_generator() -> Iterator[str]:
        while True:
            item = output_queue.get()
            if item is sentinel:
                break
            yield item  # type: ignore[misc]
        if on_done:
            on_done()

    return stream_generator()
