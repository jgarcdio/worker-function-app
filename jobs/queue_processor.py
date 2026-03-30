from jobs.orchestrators.message_orchestrator import process_message


async def process_queue_message(raw_body: str) -> None:
    await process_message(raw_body)
