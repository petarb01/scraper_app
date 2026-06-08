# Docker Documentation

Complete guide to the Docker setup, configuration, and usage.

## Overview

The application runs in three Docker containers orchestrated with Docker Compose:
- **Database** (PostgreSQL 15)
- **Backend** (Flask API)
- **Frontend** (React + Vite)

## Docker Compose Configuration

### Services

```yaml
services:
  db:
    image: postgres:15-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: price_scraper
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: strongpassword
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/schema.sql:/docker-entrypoint-initdb.d/schema.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    ports:
      - "5000:5000"
    environment:
      DB_HOST: db
      DB_PORT: 5432
      DB_NAME: price_scraper
      DB_USER: postgres
      DB_PASSWORD: strongpassword
      FLASK_ENV: development
      FLASK_DEBUG: 1
    volumes:
      - ./backend:/app
    depends_on:
      db:
        condition: service_healthy

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    environment:
      VITE_API_URL: http://localhost:5000/api
      CHOKIDAR_USEPOLLING: true
    volumes:
      - ./frontend:/app
      - /app/node_modules
    depends_on:
      - backend

volumes:
  postgres_data:
```

## Container Details

### Database Container

**Image:** `postgres:15-alpine`
**Port:** 5432
**Volume:** `postgres_data` (persistent storage)

**Features:**
- Automatic schema initialization from `schema.sql`
- Health checks for dependency management
- Data persistence across container restarts

**Dockerfile:** Uses official PostgreSQL image (no custom Dockerfile needed)

### Backend Container

**Base Image:** `python:3.11-slim`
**Port:** 5000
**Working Directory:** `/app`

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["flask", "run", "--host=0.0.0.0", "--port=5000", "--reload"]
```

**Features:**
- Hot reload enabled (`--reload` flag)
- Volume mount for live code updates
- Connects to database via Docker network

### Frontend Container

**Base Image:** `node:20-alpine`
**Port:** 5173
**Working Directory:** `/app`

**Dockerfile:**
```dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

**Features:**
- Vite dev server with hot reload
- File change polling enabled (`CHOKIDAR_USEPOLLING`)
- node_modules volume for faster rebuilds

## Networking

### Docker Network

**Network Name:** `price_scraper_network` (default bridge network)

**Container Communication:**
- Containers communicate using service names
- Backend connects to database as `db:5432`
- Frontend calls backend at `http://backend:5000`

**Host Access:**
- Frontend: `http://localhost:5173`
- Backend: `http://localhost:5000`
- Database: `localhost:5432`

## Volumes

### Named Volume: `postgres_data`

**Purpose:** Persistent PostgreSQL data storage

**Location:** Managed by Docker (typically `/var/lib/docker/volumes/`)

**Persistence:**
- ✅ Data survives `docker-compose down`
- ✅ Data survives container recreation
- ❌ Data deleted with `docker-compose down -v`

**Backup:**
```bash
# Backup volume
docker run --rm -v postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz /data

# Restore volume
docker run --rm -v postgres_data:/data -v $(pwd):/backup alpine tar xzf /backup/postgres_backup.tar.gz -C /
```

### Bind Mounts

**Backend:**
```yaml
volumes:
  - ./backend:/app  # Live code updates
```

**Frontend:**
```yaml
volumes:
  - ./frontend:/app           # Live code updates
  - /app/node_modules         # Prevent overwriting node_modules
```

## Hot Reload

### Backend Hot Reload

**How it works:**
1. Flask runs with `--reload` flag
2. Watchdog monitors file changes
3. Server automatically restarts on changes

**Files watched:**
- `backend/**/*.py`
- `backend/requirements.txt` (requires manual restart)

**Testing:**
```bash
# Make a change to backend/app.py
echo "# test change" >> backend/app.py

# Watch logs to see restart
make logs-backend
```

### Frontend Hot Reload

**How it works:**
1. Vite dev server with HMR (Hot Module Replacement)
2. File polling enabled for Docker compatibility
3. Browser auto-reloads on changes

**Files watched:**
- `frontend/src/**/*`
- `frontend/index.html`
- `frontend/package.json` (requires rebuild)

**Testing:**
```bash
# Make a change to a React component
echo "// test change" >> frontend/src/App.jsx

# Browser auto-reloads
```

## Environment Variables

### Database Container

```yaml
environment:
  POSTGRES_DB: price_scraper
  POSTGRES_USER: postgres
  POSTGRES_PASSWORD: strongpassword
```

### Backend Container

```yaml
environment:
  DB_HOST: db              # Database service name
  DB_PORT: 5432            # Internal port
  DB_NAME: price_scraper
  DB_USER: postgres
  DB_PASSWORD: strongpassword
  FLASK_ENV: development
  FLASK_DEBUG: 1
```

### Frontend Container

```yaml
environment:
  VITE_API_URL: http://localhost:5000/api
  CHOKIDAR_USEPOLLING: true  # Enable file watching in Docker
```

## Common Commands

### Starting Services

```bash
# Start all services (detached)
docker-compose up -d

# Start with logs
docker-compose up

# Start specific service
docker-compose up -d backend

# Rebuild and start
docker-compose up -d --build
```

### Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (DATA LOSS!)
docker-compose down -v

# Stop specific service
docker-compose stop backend
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f db

# Last 100 lines
docker-compose logs --tail=100
```

### Service Status

```bash
# Check running containers
docker-compose ps

# Check service health
docker-compose ps

# Detailed container info
docker inspect price_scraper_db
```

### Shell Access

```bash
# Backend shell
docker-compose exec backend /bin/bash

# Frontend shell
docker-compose exec frontend /bin/sh

# Database shell
docker-compose exec db psql -U postgres -d price_scraper

# Root shell
docker-compose exec -u root backend /bin/bash
```

### Rebuilding

```bash
# Rebuild all
docker-compose build

# Rebuild specific service
docker-compose build backend

# Rebuild with no cache
docker-compose build --no-cache

# Rebuild and restart
docker-compose up -d --build
```

## Development Workflow

### Making Backend Changes

1. Edit Python files in `backend/`
2. Flask automatically restarts
3. Check logs: `make logs-backend`
4. Test endpoint: `curl http://localhost:5000/api/...`

**Install new package:**
```bash
# 1. Add to backend/requirements.txt
echo "requests==2.31.0" >> backend/requirements.txt

# 2. Rebuild container
docker-compose up -d --build backend
```

### Making Frontend Changes

1. Edit React files in `frontend/src/`
2. Browser automatically reloads
3. Check logs: `make logs-frontend`

**Install new package:**
```bash
# 1. Enter container
docker-compose exec frontend /bin/sh

# 2. Install package
npm install axios

# 3. Exit and rebuild
exit
docker-compose up -d --build frontend
```

### Database Changes

1. Edit `database/schema.sql`
2. Recreate database:
```bash
# WARNING: This deletes all data
docker-compose down -v
docker-compose up -d

# Then re-import data
python3 database/migrate_json_to_db.py
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs <service>

# Check docker daemon
sudo systemctl status docker

# Restart docker
sudo systemctl restart docker
```

### Port Already in Use

```bash
# Find process using port
sudo lsof -ti:5432

# Kill process
sudo kill -9 <PID>

# Or change port in docker-compose.yml
```

### Hot Reload Not Working

**Backend:**
```bash
# Check if --reload flag is present
docker-compose exec backend ps aux | grep flask

# Restart service
docker-compose restart backend
```

**Frontend:**
```bash
# Check if CHOKIDAR_USEPOLLING is set
docker-compose exec frontend env | grep CHOKIDAR

# Rebuild with no cache
docker-compose up -d --build --no-cache frontend
```

### Database Connection Refused

```bash
# Check if database is healthy
docker-compose ps

# Wait for health check
docker-compose logs db | grep "ready to accept connections"

# Verify connection from backend
docker-compose exec backend psql -h db -U postgres -d price_scraper
```

### Out of Disk Space

```bash
# Check Docker disk usage
docker system df

# Clean up
docker system prune -a --volumes

# Remove unused images
docker image prune -a

# Remove dangling volumes
docker volume prune
```

### Container Keeps Restarting

```bash
# Check exit code
docker inspect price_scraper_backend | grep ExitCode

# View full logs
docker-compose logs --tail=1000 backend

# Check health status
docker inspect price_scraper_db | grep Health -A 10
```

## Production Considerations

### Production Dockerfile (Backend)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

# Use Gunicorn instead of Flask dev server
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

### Production Dockerfile (Frontend)

```dockerfile
# Build stage
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### Production docker-compose.yml

```yaml
services:
  db:
    # ... same as development
    restart: always

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    # Remove volume mounts
    restart: always

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
    # Remove volume mounts
    restart: always
```

### Security Best Practices

1. **Don't expose database port** in production
2. **Use secrets** instead of plain text passwords
3. **Run as non-root** user inside containers
4. **Scan images** for vulnerabilities
5. **Use specific tags** instead of `latest`

```yaml
secrets:
  db_password:
    file: ./secrets/db_password.txt

services:
  db:
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets:
      - db_password
```

## Monitoring

### Health Checks

```bash
# Check all health statuses
docker-compose ps

# Detailed health check
docker inspect price_scraper_db | grep Health -A 20
```

### Resource Usage

```bash
# Real-time stats
docker stats

# Specific container
docker stats price_scraper_backend

# One-time snapshot
docker stats --no-stream
```

### Logs Management

```bash
# Limit log size in docker-compose.yml
services:
  backend:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

## Makefile Integration

See [Makefile](../Makefile) for convenient commands:

```makefile
.PHONY: up down restart logs ps shell-db

up:
	docker-compose up -d

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

ps:
	docker-compose ps

shell-db:
	docker-compose exec db psql -U postgres -d price_scraper
```

---

**For more information, see [README.md](../README.md)**
