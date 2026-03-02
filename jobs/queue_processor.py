import json
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

from services.mapping_service import call_mapping_api
from services.orchestrator_service import start_orchestrator
from infra.settings import ORCHESTRATOR_MAX_PARALLEL_JOBS

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=ORCHESTRATOR_MAX_PARALLEL_JOBS)


async def _start_orchestrator_async(payload: dict, sem: asyncio.Semaphore) -> None:
    """Wrapper async para ejecutar start_orchestrator (sync) con límite de concurrencia."""
    async with sem:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(_executor, start_orchestrator, payload)


async def process_queue_message(raw_body: str) -> None:
    body = json.loads(raw_body)

    run_id = body.get("runId")
    application_name = body["applicationName"]
    raw_path = body["rawPath"]
    out_docs = body["outDocsPath"]

    logger.info(f"[WORKER] Procesando app={application_name} runId={run_id}")

    mapping_result = call_mapping_api(application_name, raw_path)

    inventory_by_job = mapping_result.get("inventoryByJob", {}) or {}
    vector_store_id = mapping_result.get("vectorStoreId")
    vector_store_name = mapping_result.get("vectorStoreName")
    jobs = list(inventory_by_job.keys())

    logger.info(f"[WORKER] Mapping OK: jobs={jobs}")

    if not inventory_by_job:
        logger.warning(
            f"[WORKER] inventoryByJob vacío para app={application_name}. "
            "No se dispara orquestación."
        )
        return

    if not vector_store_id:
        logger.warning(
            f"[WORKER] vectorStoreId vacío para app={application_name}. "
            "Los agentes podrían ejecutarse sin acceso a File Search / Vector Store."
        )

    max_parallel = max(1, int(ORCHESTRATOR_MAX_PARALLEL_JOBS))
    sem = asyncio.Semaphore(max_parallel)

    logger.info(
        f"[WORKER] Disparando Orchestrator para {len(jobs)} jobs "
        f"(max_parallel={max_parallel})"
    )

    tasks = []
    for job_name in jobs:
        job_inventory = inventory_by_job.get(job_name, {}) or {}

        payload = {
            "applicationName": application_name,
            "runId": run_id,
            "jobName": job_name,
            "outDocsPath": f"{out_docs}",
            "inventory": job_inventory,
            "vectorStoreId": vector_store_id,
            "vectorStoreName": vector_store_name
        }

        logger.info(
            f"[WORKER] Encolando disparo Orchestrator para job={job_name} "
            f"vectorStoreId={vector_store_id}"
        )
        tasks.append(asyncio.create_task(_start_orchestrator_async(payload, sem)))

    await asyncio.gather(*tasks)

    logger.info(f"[WORKER] Orquestador disparado OK para {len(jobs)} jobs")