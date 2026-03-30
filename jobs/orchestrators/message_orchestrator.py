import asyncio
import json
import logging
from typing import Any, Dict, Optional, Tuple

from infra.settings import ORCHESTRATION_MAX_PARALLEL_JOBS
from jobs.orchestrators.job_orchestrator import process_single_job
from services.mapping_service import call_mapping_api

logger = logging.getLogger(__name__)


def _parse_message(raw_body: str) -> Dict[str, Any]:
    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Mensaje inválido: JSON corrupto. detail={exc}") from exc

    required_fields = ("applicationName", "rawPath", "outDocsPath")
    missing = [field for field in required_fields if not body.get(field)]
    if missing:
        raise ValueError(f"Faltan campos requeridos en el mensaje: {', '.join(missing)}")

    return body


def _extract_mapping_context(mapping_result: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str], Optional[str]]:
    inventory_by_job = mapping_result.get("inventoryByJob") or {}
    vector_store_id = mapping_result.get("vectorStoreId")
    vector_store_name = mapping_result.get("vectorStoreName")

    if not inventory_by_job:
        raise RuntimeError("[WORKER] El mapping no retornó inventoryByJob")

    return inventory_by_job, vector_store_id, vector_store_name


async def process_message(raw_body: str) -> None:
    body = _parse_message(raw_body)

    run_id = body.get("runId")
    application_name = body["applicationName"]
    raw_path = body["rawPath"]
    out_docs = body["outDocsPath"]

    logger.info(
        "[WORKER] Procesando mensaje app=%s runId=%s rawPath=%s outDocs=%s",
        application_name,
        run_id,
        raw_path,
        out_docs,
    )

    mapping_result = call_mapping_api(application_name, raw_path)
    inventory_by_job, vector_store_id, vector_store_name = _extract_mapping_context(mapping_result)

    logger.info(
        "[WORKER] Mapping OK app=%s jobs=%s vectorStoreId=%s vectorStoreName=%s",
        application_name,
        len(inventory_by_job),
        vector_store_id,
        vector_store_name,
    )

    sem = asyncio.Semaphore(ORCHESTRATION_MAX_PARALLEL_JOBS)
    tasks = [
        process_single_job(
            application_name=application_name,
            run_id=run_id,
            job_name=job_name,
            out_docs=out_docs,
            job_inventory=job_inventory,
            vector_store_id=vector_store_id,
            vector_store_name=vector_store_name,
            sem=sem,
        )
        for job_name, job_inventory in inventory_by_job.items()
    ]

    results = await asyncio.gather(*tasks)
    failed_jobs = [r for r in results if r.get("status") == "FAILED"]

    if failed_jobs:
        logger.error("[WORKER] Jobs con error: %s", failed_jobs)
        raise RuntimeError(f"[WORKER] {len(failed_jobs)} job(s) fallaron")

    logger.info("[WORKER] Todos los jobs finalizaron correctamente. results=%s", results)
