from typing import Any, Dict, Optional


def build_job_out_docs_path(out_docs: str, job_name: str) -> str:
    return f"{out_docs.rstrip('/')}/{job_name}/"


def build_job_agent_payload(
    application_name: str,
    run_id: str,
    job_name: str,
    job_out_docs_path: str,
    job_inventory: Dict[str, Any],
    vector_store_id: Optional[str],
) -> Dict[str, Any]:
    return {
        "applicationName": application_name,
        "runId": run_id,
        "jobName": job_name,
        "outDocsPath": job_out_docs_path,
        "inventory": job_inventory,
        "vectorStoreId": vector_store_id,
    }


def build_paragraphs_payload(
    application_name: str,
    run_id: str,
    job_name: str,
    job_id: Optional[str],
    job_out_docs_path: str,
    pgm: str,
    vector_store_id: Optional[str],
) -> Dict[str, Any]:
    return {
        "applicationName": application_name,
        "runId": run_id,
        "jobName": job_name,
        "jobId": job_id,
        "outDocsPath": job_out_docs_path,
        "pgm": pgm,
        "vectorStoreId": vector_store_id,
    }
