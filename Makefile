.PHONY: help build up down start stop restart logs logs-backend logs-db clean ps shell-backend shell-db migrate test

# Default target
.DEFAULT_GOAL := help

## help: Display this help message
help:
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║        Price Scraper Docker Management Commands             ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Available commands:"
	@echo ""
	@grep -E '^## ' Makefile | sed 's/## /  /' | sed 's/:/ -/'
	@echo ""

## build: Build all Docker images
build:
	@echo "Building Docker images..."
	docker compose build --no-cache
	@echo "✓ Build complete!"

## up: Start all services (build if needed)
up:
	@echo "Starting all services..."
	docker compose up -d
	@echo "✓ Services started!"
	@echo "Backend API: http://localhost:5000"
	@echo "Database: localhost:5432"
	@echo "Frontend: localhost:3000"

## down: Stop and remove all containers, networks
down:
	@echo "Stopping all services..."
	docker compose down
	@echo "✓ Services stopped!"

## start: Start existing containers without rebuilding
start:
	@echo "Starting services..."
	docker compose start
	@echo "✓ Services started!"

## stop: Stop running containers without removing them
stop:
	@echo "Stopping services..."
	docker compose stop
	@echo "✓ Services stopped!"

## restart: Restart all services
restart:
	@echo "Restarting all services..."
	docker compose restart
	@echo "✓ Services restarted!"

## rebuild: Rebuild and restart all services
rebuild:
	@echo "Rebuilding and restarting all services..."
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d
	@echo "✓ Rebuild complete!"

## logs: Show logs from all services
logs:
	docker-compose logs -f

## logs-backend: Show logs from backend service only
logs-backend:
	docker-compose logs -f backend

## logs-db: Show logs from database service only
logs-db:
	docker-compose logs -f db

## ps: List all running containers
ps:
	@docker-compose ps

## shell-backend: Open shell in backend container
shell-backend:
	@echo "Opening shell in backend container..."
	docker-compose exec backend sh

## shell-db: Open PostgreSQL shell in database container
shell-db:
	@echo "Opening PostgreSQL shell..."
	docker-compose exec db psql -U postgres -d price_scraper

## clean: Remove all containers, volumes, and networks
clean:
	@echo "⚠ This will remove all containers, volumes, and networks!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		echo "Cleaning up..."; \
		docker-compose down -v --remove-orphans; \
		docker system prune -f; \
		echo "✓ Cleanup complete!"; \
	else \
		echo "Cleanup cancelled."; \
	fi

## migrate: Run database migrations (placeholder)
migrate:
	@echo "Running database migrations..."
	docker-compose exec backend python -c "print('Migration placeholder - add your migration script here')"
	@echo "✓ Migrations complete!"

## test: Run tests
test:
	@echo "Running tests..."
	docker-compose exec backend python -m pytest
	@echo "✓ Tests complete!"

## dev: Start development environment with logs
dev:
	@echo "Starting development environment..."
	docker-compose up

## status: Show detailed status of all services
status:
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║                    Service Status                            ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"
	@echo ""
	@docker-compose ps
	@echo ""
	@echo "Service URLs:"
	@echo "  Backend API: http://localhost:5000"
	@echo "  Database:    localhost:5432"
	@echo "  Frontend:    localhost:3000"
