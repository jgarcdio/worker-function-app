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

    app_name = body["app"]
    raw_path = body["rawPath"]
    out_docs = body["outDocsPath"]

    logger.info(f"[WORKER] Procesando app={app_name}")

    mapping_result = call_mapping_api(app_name, raw_path)

    inventory_by_job = mapping_result.get("inventoryByJob", {}) or {}
    jobs = list(inventory_by_job.keys())

    logger.info(f"[WORKER] Mapping OK: jobs={jobs}")

    if not inventory_by_job:
        logger.warning(f"[WORKER] inventoryByJob vacío para app={app_name}. No se dispara orquestación.")
        return

    max_parallel = max(1, int(ORCHESTRATOR_MAX_PARALLEL_JOBS))
    sem = asyncio.Semaphore(max_parallel)

    logger.info(
        f"[WORKER] Disparando Orchestrator para {len(jobs)} jobs "
        f"(max_parallel={max_parallel})"
    )

    tasks = []
    for job_name in jobs:
        job_inventory = inventory_by_job.get(job_name, {})

        payload = {
            "app": app_name,
            "jobName": job_name,
            "outDocsPath": f"{out_docs}",
            "inventory": job_inventory,
        }

        logger.info(f"[WORKER] Encolando disparo Orchestrator para job={job_name}")
        tasks.append(asyncio.create_task(_start_orchestrator_async(payload, sem)))

    await asyncio.gather(*tasks)

    logger.info(f"[WORKER] Orquestador disparado OK para {len(jobs)} jobs")
