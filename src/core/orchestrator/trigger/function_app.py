import json
import logging
from dataclasses import dataclass
from pathlib import Path

import azure.functions as func
import yaml
from requests import request

app = func.FunctionApp()


@dataclass
class Schema:
    id: str
    name: str | None = None
    description: str | None = None
    runbook: str | None = None
    script: str | None = None

    def __post_init__(self):
        if isinstance(self.id, str):
            config_path = Path(__file__).parent / "config.yaml"
            logging.info(f"Loading config from {config_path}")
            if config_path.exists():
                with open(config_path) as f:
                    config = yaml.safe_load(f)
                    if self.id in config:
                        self.name = config[self.id].get("name", "")
                        self.description = config[self.id].get("description")
                        self.runbook = config[self.id].get("runbook")
                        self.script = config[self.id].get("script")
            else:
                raise FileNotFoundError("config.yml does not exist")
        else:
            raise ValueError("Schema ID cannot be empty")


def update():
    return "ok"


@app.route(route="Trigger", auth_level=func.AuthLevel.FUNCTION)
def trigger(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Request parameters: %s", req.params)

    schema = Schema(id=req.params.get("id", None))

    response = request(
        "GET", schema.runbook, headers={"script": f"{schema.script}"}
    )  # temp local test
    response_content = response.content
    logging.info("Response content: %s", response_content)

    logging.info("Triggering schema: %s", schema)

    return func.HttpResponse(
        json.dumps(
            {
                "status": response.status_code,
                "test": update(),
                "schema": {
                    "id": schema.id,
                    "name": schema.name,
                    "description": schema.description,
                    "runbook": schema.runbook,
                },
                "response": response.json(),
            },
            ensure_ascii=False,
        ),
        status_code=200,
        mimetype="application/json",
    )
