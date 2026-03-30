import asyncio
import logging
from typing import Any, Dict, List, Optional

from infra.settings import (
    AGENT_FUNCTIONAL_ID,
    AGENT_PARAGRAPHS_ID,
    AGENT_RETRY_COUNT,
    AGENT_TECHNICAL_ID,
    ENABLE_FUNCTIONAL_AGENT,
    ENABLE_PARAGRAPHS_AGENT,
    ENABLE_TECHNICAL_AGENT,
)
from jobs.builders.agent_payloads import (
    build_job_agent_payload,
    build_job_out_docs_path,
    build_paragraphs_payload,
)
from jobs.models.processing_result import JobProcessingResult
from jobs.runners.agent_executor import run_agent_with_retry

logger = logging.getLogger(__name__)


async def _run_functional_agent(
    application_name: str,
    run_id: str,
    job_name: str,
    job_out_docs_path: str,
    job_inventory: Dict[str, Any],
    vector_store_id: Optional[str],
) -> None:
    payload = build_job_agent_payload(
        application_name=application_name,
        run_id=run_id,
        job_name=job_name,
        job_out_docs_path=job_out_docs_path,
        job_inventory=job_inventory,
        vector_store_id=vector_store_id,
    )
    await run_agent_with_retry(
        agent_label="FunctionalDocAgent",
        agent_id=AGENT_FUNCTIONAL_ID,
        payload=payload,
        vector_store_id=vector_store_id,
        retry_count=AGENT_RETRY_COUNT,
    )


async def _run_technical_agent(
    application_name: str,
    run_id: str,
    job_name: str,
    job_out_docs_path: str,
    job_inventory: Dict[str, Any],
    vector_store_id: Optional[str],
) -> None:
    payload = build_job_agent_payload(
        application_name=application_name,
        run_id=run_id,
        job_name=job_name,
        job_out_docs_path=job_out_docs_path,
        job_inventory=job_inventory,
        vector_store_id=vector_store_id,
    )
    await run_agent_with_retry(
        agent_label="TechnicalDocAgent",
        agent_id=AGENT_TECHNICAL_ID,
        payload=payload,
        vector_store_id=vector_store_id,
        retry_count=AGENT_RETRY_COUNT,
    )


async def _run_paragraphs_per_pgm(
    application_name: str,
    run_id: str,
    job_name: str,
    job_out_docs_path: str,
    job_inventory: Dict[str, Any],
    vector_store_id: Optional[str],
) -> List[Dict[str, Any]]:
    pgms = job_inventory.get("pgms") or []
    job_id = job_inventory.get("jobId")

    if not pgms:
        logger.info(
            "[WORKER] job=%s no tiene pgms[]. Se omite DiagramParagraphsAgent.",
            job_name,
        )
        return []

    results: List[Dict[str, Any]] = []

    for pgm in pgms:
        logger.info(
            "[WORKER] Ejecutando DiagramParagraphsAgent job=%s pgm=%s",
            job_name,
            pgm,
        )
        payload = build_paragraphs_payload(
            application_name=application_name,
            run_id=run_id,
            job_name=job_name,
            job_id=job_id,
            job_out_docs_path=job_out_docs_path,
            pgm=pgm,
            vector_store_id=vector_store_id,
        )
        result = await run_agent_with_retry(
            agent_label="DiagramParagraphsAgent",
            agent_id=AGENT_PARAGRAPHS_ID,
            payload=payload,
            vector_store_id=vector_store_id,
            retry_count=AGENT_RETRY_COUNT,
        )
        results.append({"pgm": pgm, "status": result.get("status")})

    return results


async def process_single_job(
    application_name: str,
    run_id: str,
    job_name: str,
    out_docs: str,
    job_inventory: Dict[str, Any],
    vector_store_id: Optional[str],
    vector_store_name: Optional[str],
    sem: asyncio.Semaphore,
) -> Dict[str, Any]:
    del vector_store_name
    async with sem:
        logger.info("[WORKER] Iniciando procesamiento job=%s", job_name)
        job_out_docs_path = build_job_out_docs_path(out_docs, job_name)

        try:
            if ENABLE_FUNCTIONAL_AGENT:
                await _run_functional_agent(
                    application_name=application_name,
                    run_id=run_id,
                    job_name=job_name,
                    job_out_docs_path=job_out_docs_path,
                    job_inventory=job_inventory,
                    vector_store_id=vector_store_id,
                )
            else:
                logger.info("[WORKER] FunctionalDocAgent deshabilitado job=%s", job_name)

            if ENABLE_TECHNICAL_AGENT:
                await _run_technical_agent(
                    application_name=application_name,
                    run_id=run_id,
                    job_name=job_name,
                    job_out_docs_path=job_out_docs_path,
                    job_inventory=job_inventory,
                    vector_store_id=vector_store_id,
                )
            else:
                logger.info("[WORKER] TechnicalDocAgent deshabilitado job=%s", job_name)

            paragraph_results: List[Dict[str, Any]] = []
            if ENABLE_PARAGRAPHS_AGENT:
                paragraph_results = await _run_paragraphs_per_pgm(
                    application_name=application_name,
                    run_id=run_id,
                    job_name=job_name,
                    job_out_docs_path=job_out_docs_path,
                    job_inventory=job_inventory,
                    vector_store_id=vector_store_id,
                )
            else:
                logger.info("[WORKER] DiagramParagraphsAgent deshabilitado job=%s", job_name)

            logger.info("[WORKER] Job %s procesado correctamente", job_name)
            return JobProcessingResult(
                job_name=job_name,
                status="SUCCESS",
                paragraphs=paragraph_results,
            ).to_dict()
        except Exception as exc:
            logger.exception("[WORKER] Error procesando job=%s: %s", job_name, exc)
            return JobProcessingResult(
                job_name=job_name,
                status="FAILED",
                error=str(exc),
            ).to_dict()
