import logging
import time

import azure.functions as func

app = func.FunctionApp()


@app.route(route="receiver", auth_level=func.AuthLevel.FUNCTION)
def receiver(req: func.HttpRequest) -> func.HttpResponse:
    logging.info(req.params)
    time.sleep(5)

    return func.HttpResponse(
        "triggered in 5 seconds.",
        status_code=200,
    )
