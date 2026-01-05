import azure.functions as func
import traceback

from logger.logging import configure_logging
from jobs.queue_processor import process_queue_message

logger = configure_logging()
app = func.FunctionApp()

@app.queue_trigger(
    arg_name="msg",
    queue_name="sa-queue-file-agent-cbl-doc",
    connection="QUEUE_CONN",
)
def worker_queue_trigger(msg: func.QueueMessage) -> None:
    try:
        raw_body = msg.get_body().decode("utf-8")
        process_queue_message(raw_body)
    except Exception as e:
        logger.error(f"[WORKER] ERROR: {e}\n{traceback.format_exc()}")
        raise
