import os


AGENT_IA_ENDPOINT = os.environ["AGENT_IA_ENDPOINT"].rstrip("/")

AGENT_FUNCTIONAL_ID = os.environ["AGENT_FUNCTIONAL_ID"]
AGENT_TECHNICAL_ID = os.environ["AGENT_TECHNICAL_ID"]
AGENT_PARAGRAPHS_ID = os.environ["AGENT_PARAGRAPHS_ID"]

POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "5"))
POLL_TIMEOUT = int(os.environ.get("POLL_TIMEOUT", "900"))
MAPPING_API_URL = os.environ["API_URL"].rstrip("/")
MAPPING_API_TIMEOUT = int(os.environ.get("API_TIMEOUT", "900"))
ORCHESTRATION_MAX_PARALLEL_JOBS = int(
    os.environ.get(
        "ORCHESTRATION_MAX_PARALLEL_JOBS",
        os.environ.get("ORCHESTRATOR_MAX_PARALLEL_JOBS", "5"),
    )
)
AGENT_RETRY_COUNT = int(os.environ.get("AGENT_RETRY_COUNT", "1"))

ENABLE_FUNCTIONAL_AGENT = os.environ.get("ENABLE_FUNCTIONAL_AGENT", "true").lower() == "true"
ENABLE_TECHNICAL_AGENT = os.environ.get("ENABLE_TECHNICAL_AGENT", "true").lower() == "true"
ENABLE_PARAGRAPHS_AGENT = os.environ.get("ENABLE_PARAGRAPHS_AGENT", "true").lower() == "true"
