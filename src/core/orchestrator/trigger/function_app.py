import logging

import azure.functions as func
from requests import request

app = func.FunctionApp()


@app.route(route="Trigger", auth_level=func.AuthLevel.FUNCTION)
def trigger(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Request parameters: %s", req.params)

    response = request("GET", "http://localhost:8080/api/inbound")  # temp local test
    response_content = response.content
    logging.info("Response content: %s", response_content)

    return func.HttpResponse(
        "Triggered!!",
        status_code=200,
    )
