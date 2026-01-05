from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from infra.settings import AGENT_IA_ENDPOINT

def get_project_client() -> AIProjectClient:
    credential = DefaultAzureCredential()
    return AIProjectClient(
        credential=credential,
        endpoint=AGENT_IA_ENDPOINT,
    )
