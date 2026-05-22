# Code Template

```python
from agent.runner import AgentContext, workflow_agent_sync_stream


class Parametrization(vkt.Parametrization):
    title = vkt.Text("# Workflow Graph Agent")
    chat = vkt.Chat("", method="call_llm")


class Controller(vkt.Controller):
    parametrization = Parametrization

    def call_llm(self, params, entity_id=None, workspace_id=None, **kwargs):
        messages = params.chat.get_messages()
        chat_history = [
            {"role": message["role"], "content": message["content"]}
            for message in messages
        ]
        stream = workflow_agent_sync_stream(
            chat_history,
            context=AgentContext(entity_id=entity_id, workspace_id=workspace_id),
        )
        return vkt.ChatResult(params.chat, stream)

    @vkt.WebView("Workflow Graph", width=100)
    def workflow_view(self, params, **kwargs):
        state = load_canvas_state()
        if state:
            return vkt.WebResult(html=WorkflowViewer(lambda: state).write())
        return vkt.WebResult(html="<!doctype html><html><body></body></html>")
```

```xml
<system>
  <role>You help users run VIKTOR-backed engineering workflows.</role>
  <workflow_rules>
    <rule>Create the graph first with compose_workflow_graph when no graph exists.</rule>
    <rule>Use run_reaction_loads when the user asks for reaction-load results.</rule>
    <rule>Use run_footing_design after run_reaction_loads when the user asks for footing dimensions.</rule>
  </workflow_rules>
  <storage_rules>
    <rule>Use vkt.Storage with scope="entity" for handoffs.</rule>
  </storage_rules>
</system>
```

```python
payload = ReactionLoadsParams(inputs=ReactionLoadsInputs())
result = await run_reaction_loads_func(context, payload.model_dump_json())

footing_result = await run_footing_design_func(context, '{"pad_thickness": 0.6}')
```
