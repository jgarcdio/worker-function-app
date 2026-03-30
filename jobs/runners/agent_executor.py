import logging
from typing import Any, Dict, Optional

from jobs.runners.async_runner import run_sync
from services.agent_runner_service import invoke_agent, wait_for_run_completion

logger = logging.getLogger(__name__)


async def invoke_and_wait_agent(
    agent_label: str,
    agent_id: str,
    payload: Dict[str, Any],
    vector_store_id: Optional[str],
) -> Dict[str, Any]:
    launch = await run_sync(invoke_agent, agent_id, payload, vector_store_id)

    run_id = launch.get("runId")
    thread_id = launch.get("threadId")
    result = await run_sync(wait_for_run_completion, thread_id, run_id)

    logger.info(
        "[WORKER] %s finalizó job=%s pgm=%s status=%s threadId=%s runId=%s",
        agent_label,
        payload.get("jobName"),
        payload.get("pgm"),
        result.get("status"),
        thread_id,
        run_id,
    )

    if result.get("status") != "completed":
        logger.error(
            "[WORKER] %s falló job=%s pgm=%s status=%s threadId=%s runId=%s last_error=%s incomplete_details=%s required_action=%s",
            agent_label,
            payload.get("jobName"),
            payload.get("pgm"),
            result.get("status"),
            thread_id,
            run_id,
            result.get("last_error"),
            result.get("incomplete_details"),
            result.get("required_action"),
        )

    return result


async def run_agent_with_retry(
    agent_label: str,
    agent_id: str,
    payload: Dict[str, Any],
    vector_store_id: Optional[str],
    retry_count: int,
) -> Dict[str, Any]:
    attempts = retry_count + 1
    last_result: Optional[Dict[str, Any]] = None

    for attempt in range(1, attempts + 1):
        logger.info(
            "[WORKER] Ejecutando %s job=%s pgm=%s intento=%s/%s",
            agent_label,
            payload.get("jobName"),
            payload.get("pgm"),
            attempt,
            attempts,
        )

        last_result = await invoke_and_wait_agent(
            agent_label=agent_label,
            agent_id=agent_id,
            payload=payload,
            vector_store_id=vector_store_id,
        )

        if last_result.get("status") == "completed":
            return last_result

        if attempt < attempts:
            logger.warning(
                "[WORKER] %s falló job=%s pgm=%s status=%s. Reintentando...",
                agent_label,
                payload.get("jobName"),
                payload.get("pgm"),
                last_result.get("status"),
            )

    raise RuntimeError(
        f"{agent_label} falló para job={payload.get('jobName')} "
        f"pgm={payload.get('pgm')} "
        f"status={last_result.get('status') if last_result else None} "
        f"last_error={last_result.get('last_error') if last_result else None} "
        f"incomplete_details={last_result.get('incomplete_details') if last_result else None} "
        f"required_action={last_result.get('required_action') if last_result else None}"
    )
