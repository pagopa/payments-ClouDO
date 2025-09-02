import logging

import azure.functions as func

app = func.FunctionApp()


@app.route(route="inbound", auth_level=func.AuthLevel.FUNCTION)
def inbound(req: func.HttpRequest) -> func.HttpResponse:
    logging.info(req.params)
    name = req.params.get("name")
    if not name:
        try:
            req_body = req.get_json()
            logging.info(req_body)
        except ValueError:
            pass
        else:
            name = req_body.get("name")

    if name:
        return func.HttpResponse(
            f"Hello, {name}. This HTTP triggered function executed successfully."
        )
    else:
        return func.HttpResponse(
            "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
            status_code=200,
        )
