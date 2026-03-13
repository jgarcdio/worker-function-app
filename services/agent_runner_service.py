import json
import logging
import time
from typing import Any, Dict, Optional

from azure.ai.agents.models import (
    FileSearchTool,
    FileSearchToolDefinition,
    MessageRole,
)

from infra.ai_project_client import get_project_client
from infra.settings import POLL_INTERVAL, POLL_TIMEOUT

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {"completed", "failed", "cancelled", "expired"}
SUCCESS_STATUSES = {"completed"}


def _safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    except Exception:
        return str(obj)


def _build_tool_resources(vector_store_id: Optional[str]):
    if not vector_store_id:
        return None
    return FileSearchTool(vector_store_ids=[vector_store_id]).resources


def _ensure_file_search_on_agent(project, agent_id: str) -> None:
    """
    Asegura que el agente tenga habilitada la tool File Search,
    pero SIN fijar vector_store_id en el agente.
    """
    try:
        agent = project.agents.get_agent(agent_id=agent_id)

        existing_tools = list(getattr(agent, "tools", []) or [])

        has_file_search = False
        for t in existing_tools:
            t_type = getattr(t, "type", None)
            if (t_type and str(t_type).lower() == "file_search") or \
               (t.__class__.__name__ == "FileSearchToolDefinition"):
                has_file_search = True
                break

        if has_file_search:
            logger.info("[AGENT] agent_id=%s ya tiene File Search habilitado", agent_id)
            return

        existing_tools.append(FileSearchToolDefinition())

        project.agents.update_agent(
            agent_id=agent_id,
            tools=existing_tools,
        )

        logger.info("[AGENT] File Search habilitado correctamente en agent_id=%s", agent_id)

    except Exception as exc:
        logger.exception(
            "[AGENT] No se pudo habilitar File Search en agent_id=%s: %s",
            agent_id,
            exc,
        )
        raise


def _create_thread(project, tool_resources=None):
    try:
        if tool_resources:
            return project.agents.threads.create(tool_resources=tool_resources)
        return project.agents.threads.create()
    except TypeError:
        thread = project.agents.threads.create()

        if tool_resources:
            try:
                project.agents.threads.update(
                    thread_id=thread.id,
                    tool_resources=tool_resources,
                )
            except Exception as exc:
                logger.warning(
                    "[AGENT] No se pudo actualizar tool_resources del thread %s: %s",
                    thread.id,
                    exc,
                )

        return thread


def _get_run(project, thread_id: str, run_id: str):
    runs_client = project.agents.runs

    if hasattr(runs_client, "get"):
        return runs_client.get(thread_id=thread_id, run_id=run_id)

    if hasattr(runs_client, "retrieve"):
        return runs_client.retrieve(thread_id=thread_id, run_id=run_id)

    raise AttributeError("El SDK no expone runs.get ni runs.retrieve")


def _extract_run_data(thread_id: str, run_id: str, run: Any) -> Dict[str, Any]:
    if isinstance(run, dict):
        get_value = run.get
    else:
        get_value = lambda k, d=None: getattr(run, k, d)

    return {
        "threadId": thread_id,
        "runId": run_id,
        "status": get_value("status"),
        "last_error": get_value("last_error"),
        "incomplete_details": get_value("incomplete_details"),
        "required_action": get_value("required_action"),
        "raw": run,
    }


def wait_for_run_completion(
    thread_id: str,
    run_id: str,
    timeout_seconds: int = POLL_TIMEOUT,
) -> Dict[str, Any]:
    project = get_project_client()
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        run = _get_run(project, thread_id, run_id)
        result = _extract_run_data(thread_id, run_id, run)

        if result["status"] in TERMINAL_STATUSES:
            return result

        time.sleep(POLL_INTERVAL)

    return {
        "threadId": thread_id,
        "runId": run_id,
        "status": "timeout",
        "last_error": None,
        "incomplete_details": None,
        "required_action": None,
        "raw": None,
    }


def invoke_agent(
    agent_id: str,
    payload: Dict[str, Any],
    vector_store_id: Optional[str],
) -> Dict[str, Any]:
    project = get_project_client()

    # 1) Asegurar que el agente tenga File Search habilitado
    _ensure_file_search_on_agent(project, agent_id)

    # 2) Adjuntar el vector dinámico SOLO al thread
    tool_resources = _build_tool_resources(vector_store_id)
    thread = _create_thread(project, tool_resources)
    thread_id = thread.id

    logger.info(
        "[AGENT] Thread creado thread_id=%s vectorStoreId=%s tool_resources=%s",
        thread_id,
        vector_store_id,
        _safe_json(getattr(thread, "tool_resources", None)),
    )

    # 3) Crear mensaje del usuario
    project.agents.messages.create(
        thread_id=thread_id,
        role=MessageRole.USER,
        content=_safe_json(payload),
    )

    # 4) Lanzar run
    run = project.agents.runs.create(
        thread_id=thread_id,
        agent_id=agent_id,
    )

    run_id = getattr(run, "id", None) or (run.get("id") if isinstance(run, dict) else None)
    result = _extract_run_data(thread_id, run_id, run)

    logger.info(
        "[AGENT] Lanzado agent_id=%s thread_id=%s run_id=%s status=%s vectorStoreId=%s",
        agent_id,
        thread_id,
        run_id,
        result["status"],
        vector_store_id,
    )

    return result