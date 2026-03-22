.PHONY: dev prod down logs clean

# Development — hot reload
dev:
	docker-compose -f docker-compose.dev.yml up --build

# Production
prod:
	docker-compose up --build -d

# Stop all
down:
	docker-compose down

# View logs
logs:
	docker-compose logs -f

# Backend logs only
logs-backend:
	docker-compose logs -f backend

# Clean everything including volumes
clean:
	docker-compose down -v
	docker system prune -f

# Rebuild just backend
rebuild-backend:
	docker-compose up --build -d backend

# Open psql
psql:
	docker exec -it banking_postgres psql -U banking_user -d banking_agent

# Open redis CLI
redis:
	docker exec -it banking_redis redis-cli

# Run database migrations
migrate:
	docker exec banking_backend python -c "import asyncio; from db.database import init_db; asyncio.run(init_db())"