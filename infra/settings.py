import os

AGENT_IA_ENDPOINT = os.environ["AGENT_IA_ENDPOINT"].rstrip("/")
AGENT_ORCHESTRATOR_ID = os.environ["AGENT_ORCHESTRATOR_ID"]

POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "5"))
POLL_TIMEOUT  = int(os.environ.get("POLL_TIMEOUT", "900"))

MAPPING_API_URL = os.environ["API_URL"].rstrip("/")
MAPPING_API_TIMEOUT = int(os.environ.get("API_TIMEOUT", "900"))
