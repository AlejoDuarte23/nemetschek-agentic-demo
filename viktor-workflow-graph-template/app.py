import viktor as vkt
from dotenv import load_dotenv

from agent.runner import AgentContext, workflow_agent_sync_stream
from workflow_graph.state import delete_canvas_state, load_canvas_state
from workflow_graph.viewer import WorkflowViewer


load_dotenv()


class Parametrization(vkt.Parametrization):
    title = vkt.Text(""" # Workflow Graph Agent
Build a workflow graph, run VIKTOR-backed tools, and keep intermediate results in entity storage."""
    )
    chat = vkt.Chat("", method="call_llm")


class Controller(vkt.Controller):
    parametrization = Parametrization

    def call_llm(self, params, entity_id=None, workspace_id=None, **kwargs):
        if not params.chat:
            return None

        messages = params.chat.get_messages()
        chat_history = [
            {"role": message["role"], "content": message["content"]}
            for message in messages
        ]
        stream = workflow_agent_sync_stream(
            chat_history,
            context=AgentContext(entity_id=entity_id, workspace_id=workspace_id),
            show_tool_progress=True,
        )
        return vkt.ChatResult(params.chat, stream)

    @vkt.WebView("Workflow Graph", width=100)
    def workflow_view(self, params, **kwargs):
        if not params.chat:
            delete_canvas_state()

        canvas_state = load_canvas_state()
        if canvas_state:
            return vkt.WebResult(html=WorkflowViewer(lambda: canvas_state).write())

        html = (
            "<!doctype html><html><head><style>"
            "body{margin:0;background:#fff;}"
            "</style></head><body></body></html>"
        )
        return vkt.WebResult(html=html)
