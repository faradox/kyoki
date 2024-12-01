.PHONY: all setup setup-dev build build-dev logs logs-dev shell shell-dev run run-dev stop clean help

all: help

uid := $(shell id -u)
gid := $(shell id -g)

PROJECT_NAME := kyoki
DOCKER_NETWORK_NAME ?= breathnet

setup: build
	@echo "Kyoki production setup complete!"

setup-dev: build-dev
	@echo "Kyoki development setup complete!"

build-dev:
	@echo "Building development image..."
	docker compose -p $(PROJECT_NAME) build --build-arg UID=$(uid) --build-arg GID=$(gid) kyoki-dev

build:
	@echo "Building production image..."
	docker compose -p $(PROJECT_NAME) build --build-arg UID=$(uid) --build-arg GID=$(gid) kyoki-prod

logs:
	@docker logs kyoki

logs-dev:
	@docker logs kyoki-dev

shell:
	@docker exec -it kyoki /bin/bash

shell-dev:
	@docker exec -it kyoki-dev /bin/bash

run-dev:
	@echo "Starting Kyoki in development mode..."
	$(MAKE) stop
	@if [ -z "$$(docker images -q kyoki-dev:latest)" ]; then \
		echo "Development image not found. Building..."; \
		$(MAKE) build-dev; \
	fi
	docker compose -p $(PROJECT_NAME) up kyoki-dev

run:
	@echo "Starting Kyoki in production mode..."
	$(MAKE) stop
	@if [ -z "$$(docker images -q kyoki:latest)" ]; then \
		echo "Production image not found. Building..."; \
		$(MAKE) build; \
	fi
	docker compose -p $(PROJECT_NAME) up -d kyoki-prod

stop:
	@echo "Stopping Kyoki..."
	@docker compose -p $(PROJECT_NAME) down 2>/dev/null || true
	@docker rm -f kyoki kyoki-dev 2>/dev/null || true

clean:
	@echo "Cleaning Kyoki containers and images..."
	$(MAKE) stop
	@docker image rm kyoki:latest kyoki-dev:latest 2>/dev/null || true

help:
	@echo '====================='
	@echo '    KYOKI - MAKEFILE  '
	@echo '====================='
	@echo ''
	@echo 'Setup Commands:'
	@echo '  setup               - Production setup (build)'
	@echo '  setup-dev           - Development setup (build-dev)'
	@echo ''
	@echo 'Build Commands:'
	@echo '  build               - Build production image'
	@echo '  build-dev           - Build development image'
	@echo ''
	@echo 'Run Commands:'
	@echo '  run                 - Run in production mode (detached)'
	@echo '  run-dev             - Run in development mode with hot-reload'
	@echo ''
	@echo 'Logging Commands:'
	@echo '  logs                - Show Kyoki logs'
	@echo '  logs-dev            - Show Kyoki dev logs'
	@echo ''
	@echo 'Shell Access:'
	@echo '  shell               - Access Kyoki container shell'
	@echo '  shell-dev           - Access Kyoki dev container shell'
	@echo ''
	@echo 'Maintenance Commands:'
	@echo '  stop                - Stop Kyoki containers'
	@echo '  clean               - Stop and remove images'
	@echo '====================='
