import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

from infra.settings import (
    AGENT_FUNCTIONAL_ID,
    AGENT_PARAGRAPHS_ID,
    AGENT_RETRY_COUNT,
    AGENT_TECHNICAL_ID,
    ORCHESTRATION_MAX_PARALLEL_JOBS,
)
from services.agent_runner_service import invoke_agent, wait_for_run_completion
from services.mapping_service import call_mapping_api

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=ORCHESTRATION_MAX_PARALLEL_JOBS)


async def _run_sync(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, lambda: func(*args, **kwargs))


async def _invoke_and_wait(
    agent_label: str,
    agent_id: str,
    payload: Dict[str, Any],
    vector_store_id: Optional[str],
) -> Dict[str, Any]:
    launch = await _run_sync(invoke_agent, agent_id, payload, vector_store_id)

    run_id = launch.get("runId")
    thread_id = launch.get("threadId")

    result = await _run_sync(wait_for_run_completion, thread_id, run_id)

    logger.info(
        "[WORKER] %s finalizó job=%s status=%s threadId=%s runId=%s",
        agent_label,
        payload.get("jobName"),
        result.get("status"),
        thread_id,
        run_id,
    )

    if result.get("status") != "completed":
        logger.error(
            "[WORKER] %s falló job=%s status=%s threadId=%s runId=%s last_error=%s incomplete_details=%s required_action=%s",
            agent_label,
            payload.get("jobName"),
            result.get("status"),
            thread_id,
            run_id,
            result.get("last_error"),
            result.get("incomplete_details"),
            result.get("required_action"),
        )

    return result


async def _run_agent_with_retry(
    agent_label: str,
    agent_id: str,
    payload: Dict[str, Any],
    vector_store_id: Optional[str],
) -> Dict[str, Any]:
    attempts = AGENT_RETRY_COUNT + 1
    last_result = None

    for attempt in range(1, attempts + 1):
        logger.info(
            "[WORKER] Ejecutando %s job=%s intento=%s/%s",
            agent_label,
            payload.get("jobName"),
            attempt,
            attempts,
        )

        last_result = await _invoke_and_wait(
            agent_label,
            agent_id,
            payload,
            vector_store_id,
        )

        if last_result.get("status") == "completed":
            return last_result

        if attempt < attempts:
            logger.warning(
                "[WORKER] %s falló job=%s status=%s. Reintentando...",
                agent_label,
                payload.get("jobName"),
                last_result.get("status"),
            )

    raise RuntimeError(
        f"{agent_label} falló para job={payload.get('jobName')} "
        f"status={last_result.get('status')} "
        f"last_error={last_result.get('last_error')} "
        f"incomplete_details={last_result.get('incomplete_details')} "
        f"required_action={last_result.get('required_action')}"
    )


async def _process_single_job(
    application_name: str,
    run_id: str,
    job_name: str,
    out_docs: str,
    job_inventory: Dict[str, Any],
    vector_store_id: Optional[str],
    vector_store_name: Optional[str],
    sem: asyncio.Semaphore,
) -> Dict[str, Any]:
    async with sem:
        job_out_docs_path = f"{out_docs.rstrip('/')}/{job_name}/"

        logger.info(
            "[WORKER] Iniciando orquestación directa job=%s vectorStoreId=%s vectorStoreName=%s",
            job_name,
            vector_store_id,
            vector_store_name,
        )

        try:
            functional_payload = {
                "applicationName": application_name,
                "runId": run_id,
                "jobName": job_name,
                "outDocsPath": job_out_docs_path,
                "inventory": job_inventory,
                "vectorStoreId": vector_store_id,
            }
            await _run_agent_with_retry(
                "FunctionalDocAgent",
                AGENT_FUNCTIONAL_ID,
                functional_payload,
                vector_store_id,
            )

            technical_payload = {
                "applicationName": application_name,
                "runId": run_id,
                "jobName": job_name,
                "outDocsPath": job_out_docs_path,
                "inventory": job_inventory,
                "vectorStoreId": vector_store_id,
            }
            await _run_agent_with_retry(
                "TechnicalDocAgent",
                AGENT_TECHNICAL_ID,
                technical_payload,
                vector_store_id,
            )

            pgms = job_inventory.get("pgms") or []
            if pgms:
                paragraphs_payload = {
                    "applicationName": application_name,
                    "runId": run_id,
                    "jobName": job_name,
                    "jobId": job_inventory.get("jobId"),
                    "outDocsPath": job_out_docs_path,
                    "pgms": pgms,
                    "vectorStoreId": vector_store_id,
                }
                await _run_agent_with_retry(
                    "DiagramParagraphsAgent",
                    AGENT_PARAGRAPHS_ID,
                    paragraphs_payload,
                    vector_store_id,
                )
            else:
                logger.info(
                    "[WORKER] job=%s no tiene pgms[]. Se omite DiagramParagraphsAgent.",
                    job_name,
                )

            logger.info("[WORKER] Job=%s completado correctamente.", job_name)

            return {
                "jobName": job_name,
                "status": "SUCCESS",
            }

        except Exception as e:
            logger.exception("[WORKER] ERROR procesando job=%s", job_name)
            return {
                "jobName": job_name,
                "status": "FAILED",
                "error": str(e),
            }


async def process_queue_message(raw_body: str) -> None:
    body = json.loads(raw_body)

    run_id = body.get("runId")
    application_name = body["applicationName"]
    raw_path = body["rawPath"]
    out_docs = body["outDocsPath"]

    logger.info("[WORKER] Procesando app=%s runId=%s", application_name, run_id)

    mapping_result = call_mapping_api(application_name, raw_path)

    inventory_by_job = mapping_result.get("inventoryByJob", {}) or {}
    vector_store_id = mapping_result.get("vectorStoreId")
    vector_store_name = mapping_result.get("vectorStoreName")
    jobs = list(inventory_by_job.keys())

    logger.info("[WORKER] Mapping OK: jobs=%s", jobs)

    if not inventory_by_job:
        logger.warning(
            "[WORKER] inventoryByJob vacío para app=%s. No se dispara procesamiento.",
            application_name,
        )
        return

    if not vector_store_id:
        logger.warning(
            "[WORKER] vectorStoreId vacío para app=%s. Los subagentes podrían ejecutarse sin File Search.",
            application_name,
        )

    max_parallel = max(1, int(ORCHESTRATION_MAX_PARALLEL_JOBS))
    sem = asyncio.Semaphore(max_parallel)

    logger.info(
        "[WORKER] Disparando procesamiento directo para %s jobs (max_parallel=%s)",
        len(jobs),
        max_parallel,
    )

    tasks = []
    for job_name in jobs:
        job_inventory = inventory_by_job.get(job_name, {}) or {}
        tasks.append(
            asyncio.create_task(
                _process_single_job(
                    application_name=application_name,
                    run_id=run_id,
                    job_name=job_name,
                    out_docs=out_docs,
                    job_inventory=job_inventory,
                    vector_store_id=vector_store_id,
                    vector_store_name=vector_store_name,
                    sem=sem,
                )
            )
        )

    results = await asyncio.gather(*tasks, return_exceptions=False)

    success_jobs = [r["jobName"] for r in results if r.get("status") == "SUCCESS"]
    failed_jobs = [r for r in results if r.get("status") == "FAILED"]

    logger.info(
        "[WORKER] Procesamiento completado app=%s runId=%s success=%s failed=%s",
        application_name,
        run_id,
        success_jobs,
        [f["jobName"] for f in failed_jobs],
    )

    if failed_jobs:
        logger.error(
            "[WORKER] Jobs fallidos app=%s runId=%s details=%s",
            application_name,
            run_id,
            failed_jobs,
        )