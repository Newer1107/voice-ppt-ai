.PHONY: up down build logs migrate test shell-backend shell-frontend psql redis-cli clean

up:
	docker compose -f docker-compose.yml up -d

down:
	docker compose -f docker-compose.yml down

build:
	docker compose -f docker-compose.yml build

logs:
	docker compose -f docker-compose.yml logs -f

migrate:
	docker compose exec backend alembic upgrade head

test:
	docker compose exec backend pytest -v

shell-backend:
	docker compose exec backend /bin/bash

shell-frontend:
	docker compose exec frontend /bin/sh

psql:
	docker compose exec postgres psql -U app_user -d lecture_narrator

redis-cli:
	docker compose exec redis redis-cli -a ${REDIS_PASSWORD:-devpassword}

clean:
	docker compose -f docker-compose.yml down -v
