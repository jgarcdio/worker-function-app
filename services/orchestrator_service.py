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


def start_orchestrator(payload: Dict[str, Any]) -> None:
    """
    Dispara el OrchestratorAgent y retorna inmediatamente.

    IMPORTANTE:
    - No guarda run_id/thread_id porque tu tracking lo hace StatusTool desde subagentes.
    - Si la creación del run falla (quota/deployment/auth), lanzará excepción
      para que el worker lo registre/reintente/mande a poison.
    """
    project = get_project_client()

    # 1) Crear thread
    thread = project.agents.threads.create()
    thread_id = thread.id

    # 2) Mensaje inicial
    # Recomendación: NO mandes JSON gigante si no es necesario.
    # Ideal: manda solo app + vector_store_id + rutas, y que el agente consulte el vector.

    content = _safe_json(payload)

    project.agents.messages.create(
        thread_id=thread_id,
        role=MessageRole.USER,
        content=content,
    )

    # 3) Crear run (NO esperamos)
    project.agents.runs.create(
        thread_id=thread_id,
        agent_id=AGENT_ORCHESTRATOR_ID,
    )

    # Fire-and-forget: aquí termina.
    return
