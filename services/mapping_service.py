from infra.http_client import get_http_session
from infra.settings import MAPPING_API_URL, MAPPING_API_TIMEOUT

def call_mapping_api(application_name: str, raw_path: str) -> dict:
    payload = {"applicationName": application_name, "rawPath": raw_path}
    response = get_http_session().post(
        MAPPING_API_URL,
        json=payload,
        timeout=MAPPING_API_TIMEOUT,
    )

    if response.status_code < 200 or response.status_code >= 300:
        raise RuntimeError(f"[MAPPING] HTTP {response.status_code}: {response.text}")

    return response.json() if response.content else {}
