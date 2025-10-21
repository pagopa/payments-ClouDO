# ClouDO - Centralized runbook automation for manual or event-driven execution

<p align="center">
  <img src="docs/images/cloudo_logo.png" width="500" alt="Architecture Diagram"/>
</p>

## Overview
ClouDO centralizes the definition, execution, and governance of operational runbooks. It supports both manual invocation and event-driven triggers, enabling consistent, repeatable responses to incidents, maintenance tasks, and routine operations.

## Architecture Overview
At a high level, the system comprises:
- API/Controller: Validates requests, authorizes actors, and dispatches runs.
- Orchestrator: Resolves dependencies and manages run lifecycle.
- Executors: Perform steps (scripts, HTTP calls, cloud operations, etc.).
- Event Ingestion: Webhooks/queue listeners for event-driven runs.
- State & Storage: Metadata, run history, artifacts, and secret references.
- UI: Discovery, execution, approvals, and observability.

Centralized runbook automation for manual or event-driven execution.

## Getting Started

### Installation
- Clone the repository.
- Install Python dependencies as documented in the project (e.g., using pip).
- Configure environment variables and credentials as needed.

### Test environment

To set up test environment with pre-compiled schemas (test, test-2, test-3) you need `docker-compose` installed
on your machine. Then run on root folder `make test-env-start` to set up environment and test
on http://localhost:7071/api/Trigger.

```bash
curl http://localhost:7071/api/Trigger?id=test
```

To exec the test the runbook and try the workflow, use → http://localhost:7071/api/logs to see result and process status.

### Configuration

### How to write a runbook
