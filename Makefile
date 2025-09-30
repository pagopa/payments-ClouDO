# Configurable variables
DOCKER ?= docker
VERSION ?= latest
REGISTRY ?=                          # e.g., ghcr.io/your-org or myregistry.azurecr.io
IMAGE_PREFIX ?= cloudo                  # prefix for image names, e.g., payments => payments-orchestrator, payments-worker
PLATFORM ?= linux/amd64

# App paths
ORCH_PATH := src/core/orchestrator
WORKER_PATH := src/core/worker

# Dockerfile paths
ORCH_DOCKERFILE := $(ORCH_PATH)/Dockerfile
WORKER_DOCKERFILE := $(WORKER_PATH)/Dockerfile

# Image tags (can be overridden if needed)
ORCH_IMAGE ?= $(strip $(REGISTRY))$(if $(strip $(REGISTRY)),/,)$(strip $(IMAGE_PREFIX))-orchestrator:$(VERSION)
WORKER_IMAGE ?= $(strip $(REGISTRY))$(if $(strip $(REGISTRY)),/,)$(strip $(IMAGE_PREFIX))-worker:$(VERSION)

# Common build args
COMMON_BUILD_ARGS := --build-arg APP_PATH

.PHONY: help
help:
	@echo "Available targets:"
	@echo "  make build                         - Build both images"
	@echo "  make build-orchestrator            - Build the orchestrator image"
	@echo "  make build-worker                  - Build the worker image"
	@echo "  make push                          - Push both images"
	@echo "  make push-orchestrator             - Push the orchestrator image"
	@echo "  make push-worker                   - Push the worker image"
	@echo "  make clean                         - Remove local images (matching tags only)"
	@echo "  make test-env-start                - Start local dev test environment"
	@echo "  make test-env-stop                 - Stop local dev test environment"
	@echo "  make test-env-restart              - Restart local dev test environment"
	@echo ""
	@echo "Overridable variables:"
	@echo "  VERSION=<tag>                      (default: latest)"
	@echo "  REGISTRY=<registry>                (e.g., ghcr.io/your-org, myregistry.azurecr.io)"
	@echo "  IMAGE_PREFIX=<prefix>              (default: app; e.g., payments)"
	@echo "  ORCH_IMAGE / WORKER_IMAGE          (full override of image names)"
	@echo ""
	@echo "Examples:"
	@echo "  make build VERSION=1.0.0 IMAGE_PREFIX=payments"
	@echo "  make push REGISTRY=ghcr.io/your-org IMAGE_PREFIX=payments VERSION=1.0.0"

.PHONY: build
build: build-orchestrator build-worker

.PHONY: build-orchestrator
build-orchestrator:
	$(DOCKER) buildx build \
	  --platform=$(PLATFORM) \
		-f $(ORCH_DOCKERFILE) \
		$(COMMON_BUILD_ARGS)=. \
		-t $(ORCH_IMAGE) \
		$(ORCH_PATH)

.PHONY: build-worker
build-worker:
	$(DOCKER) buildx build \
    --platform=$(PLATFORM) \
		-f $(WORKER_DOCKERFILE) \
		$(COMMON_BUILD_ARGS)=. \
		-t $(WORKER_IMAGE) \
		$(WORKER_PATH)


.PHONY: push
push: push-orchestrator push-worker

.PHONY: push-orchestrator
push-orchestrator:
	@if [ -z "$(REGISTRY)" ] && echo "$(ORCH_IMAGE)" | grep -q '^[^/]\+:'; then \
		echo "WARNING: no REGISTRY set. Push may fail."; \
	fi
	$(DOCKER) push $(ORCH_IMAGE)

.PHONY: push-worker
push-worker:
	@if [ -z "$(REGISTRY)" ] && echo "$(WORKER_IMAGE)" | grep -q '^[^/]\+:'; then \
		echo "WARNING: no REGISTRY set. Push may fail."; \
	fi
	$(DOCKER) push $(WORKER_IMAGE)

.PHONY: clean
clean:
	$(DOCKER) rmi $(ORCH_IMAGE) || true
	$(DOCKER) rmi $(WORKER_IMAGE) || true

.PHONY: dev
dev:
	@echo "Starting dev environment"
	$(DOCKER) compose up -d azurite
	bash src/tests/ingest_test_schema.sh localhost:7072
	@set -euo pipefail; \
	trap 'echo "Stopping dev processes..."; kill -9 -P $$; exit 0' INT TERM; \
	( cd $(ORCH_PATH) && FEATURE_DEV=true DEV_SCRIPT_PATH=src/runbooks/ exec func start ) & \
	( cd $(WORKER_PATH) && FEATURE_DEV=true DEV_SCRIPT_PATH=src/runbooks/ exec func start -p 7072 ) & \
	wait


.PHONY: test-env-start
test-env-start:
	docker-compose build && docker-compose up -d && sleep 2 && bash src/tests/ingest_test_schema.sh
	@echo "Test with -> http://localhost:7071/api/Trigger?id=test"

.PHONY: test-env-stop
test-env-stop:
	docker-compose down

.PHONY: test-env-restart
test-env-restart: test-env-stop test-env-start
