import json
import logging

from services.mapping_service import call_mapping_api
from services.orchestrator_service import start_orchestrator

logger = logging.getLogger(__name__)

def process_queue_message(raw_body: str) -> None:
    body = json.loads(raw_body)

    app_name = body["app"]
    raw_path = body["rawPath"]
    out_docs = body["outDocsPath"]

    logger.info(f"[WORKER] Procesando app={app_name}")

    mapping_result = call_mapping_api(app_name, raw_path)
    jobs = mapping_result.get("jobs", [])

    logger.info(f"[WORKER] Mapping OK: {jobs}")

    if not jobs:
        logger.warning(f"[WORKER] No se detectaron JOBs para app={app_name}. No se dispara orquestación.")
        return

    for job_name in jobs:
        payload = { "app": app_name,"outDocsPath": out_docs,"job": job_name }
        logger.info(f"[WORKER] Disparando Orchestrator para job={job_name}")

        start_orchestrator(payload)

    logger.info(f"[WORKER] Orquestador disparado OK para {len(jobs)} jobs")
