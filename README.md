# ClouDO - Centralized runbook automation for manual or event-driven execution

<p align="center">
  <img src="docs/images/cloudo_logo.png" width="500" style="border-radius: 80%;" alt="Architecture Diagram"/>
</p>
## Overview
ClouDO centralizes the definition, execution, and governance of operational runbooks. It supports both manual invocation and event-driven triggers, enabling consistent, repeatable responses to incidents, maintenance tasks, and routine operations.

## Key Features
- Centralized runbook catalog with versioning
- Manual and event-driven execution modes
- Parameterized runs with input validation
- Idempotent and retry-safe task orchestration
- Fine-grained RBAC and approval workflows
- Audit trails, run logs, and artifact retention
- Pluggable executors (local, remote, HTTP, queue-based)
- Webhooks and scheduler for automated triggers
- Notifications (e.g., email, chat, webhooks)
- Extensible via hooks and custom integrations

## Architecture Overview
At a high level, the system comprises:
- API/Controller: Validates requests, authorizes actors, and dispatches runs.
- Orchestrator: Resolves dependencies, handles retries, and manages run lifecycle.
- Executors: Perform steps (scripts, HTTP calls, cloud operations, etc.).
- Event Ingestion: Webhooks/queue listeners for event-driven runs.
- State & Storage: Metadata, run history, artifacts, and secrets references.
- UI/CLI: Discovery, execution, approvals, and observability.

Centralized runbook automation for manual or event-driven execution.

## Getting Started

### Installation
- Clone the repository.
- Install Python dependencies as documented in the project (e.g., using pip).
- Configure environment variables and credentials as needed.

### Configuration
