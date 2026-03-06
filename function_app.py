import azure.functions as func
import traceback

from logger.logging import configure_logging
from jobs.queue_processor import process_queue_message

logger = configure_logging()
app = func.FunctionApp()

@app.event_hub_message_trigger(
    arg_name="event",
    event_hub_name="%EVENTHUB_NAME%",
    connection="EVENTHUB_CONN",
    consumer_group="%EVENTHUB_CONSUMER_GROUP%",
)
async def worker_eventhub_trigger(event: func.EventHubEvent) -> None:
    try:
        raw_body = event.get_body().decode("utf-8")
        await process_queue_message(raw_body)
    except Exception as e:
        logger.error(f"[WORKER] ERROR: {e}\n{traceback.format_exc()}")
        raise
