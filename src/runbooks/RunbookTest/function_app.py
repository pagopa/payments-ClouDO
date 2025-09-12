import json
import logging
import time

import azure.functions as func

app = func.FunctionApp()


@app.route(route="RunbookTest", auth_level=func.AuthLevel.FUNCTION)
@app.queue_output(
    arg_name="out_msg", queue_name="runbooktest-work", connection="AzureWebJobsStorage"
)
def RunbookTest(req: func.HttpRequest, out_msg: func.Out[str]) -> func.HttpResponse:
    logging.info("RunbookTest params: %s", req.params)

    payload = {
        "requestedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "query": dict(req.params),
        "method": req.method,
        "clientIp": req.headers.get("X-Forwarded-For")
        or req.headers.get("X-Client-IP"),
        "script": req.headers.get("script"),
    }

    out_msg.set(json.dumps(payload, ensure_ascii=False))

    body = json.dumps(
        {"status": "accepted", "message": "processing scheduled"}, ensure_ascii=False
    )
    return func.HttpResponse(body, status_code=202, mimetype="application/json")


@app.queue_trigger(
    arg_name="msg", queue_name="runbooktest-work", connection="AzureWebJobsStorage"
)
def process_runbooktest(msg: func.QueueMessage) -> None:
    payload = json.loads(msg.get_body().decode("utf-8"))
    logging.info("asinc started: %s", payload)

    time.sleep(5)

    logging.info("asinc complete: %s", payload.get("requestedAt"))
