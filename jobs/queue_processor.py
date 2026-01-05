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
    logger.info(f"[WORKER] Mapping OK: vector_store_id={mapping_result.get('vector_store_id')}")

    payload = {
        "app": app_name,
        "outDocsPath": out_docs,
    }

    start_orchestrator(payload)
    logger.info("[WORKER] Orquestador disparado OK (fire-and-forget)")
