import json
from typing import Any, Dict

from azure.ai.agents.models import MessageRole
from infra.ai_project_client import get_project_client
from infra.settings import AGENT_ORCHESTRATOR_ID


def _safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    except Exception:
        return str(obj)


def _build_tool_resources(vector_store_id: str | None) -> Dict[str, Any] | None:
    """
    Construye tool_resources para File Search (Vector Store) por thread/run.
    Estructura esperada por Foundry:
      tool_resources: { "file_search": { "vector_store_ids": ["..."] } }
    """
    if not vector_store_id:
        return None
    return {
        "file_search": {
            "vector_store_ids": [vector_store_id]
        }
    }


def start_orchestrator(payload: Dict[str, Any]) -> None:
    """
    Dispara el OrchestratorAgent y retorna inmediatamente.

    IMPORTANTE:
    - No toca el agente global (NO update_agent).
    - Adjunta el vector store al THREAD para aislar ejecuciones concurrentes.
    """
    project = get_project_client()

    vector_store_id = payload.get("vectorStoreId")
    tool_resources = _build_tool_resources(vector_store_id)

    try:
        if tool_resources:
            thread = project.agents.threads.create(tool_resources=tool_resources)
        else:
            thread = project.agents.threads.create()
    except TypeError:
        thread = project.agents.threads.create()
        if tool_resources:
            try:
                project.agents.threads.update(thread_id=thread.id, tool_resources=tool_resources)
            except Exception:
                pass

    thread_id = thread.id

    content = _safe_json(payload)

    project.agents.messages.create(
        thread_id=thread_id,
        role=MessageRole.USER,
        content=content,
    )

    try:
        project.agents.runs.create(
            thread_id=thread_id,
            agent_id=AGENT_ORCHESTRATOR_ID,
        )
    except TypeError:
        project.agents.runs.create(thread_id=thread_id, agent_id=AGENT_ORCHESTRATOR_ID)

    return