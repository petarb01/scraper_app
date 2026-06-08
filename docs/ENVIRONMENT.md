# Environment Variables

Complete reference for all environment variables used in the project.

## Configuration File

**File:** `.env` (root directory)
**Template:** `.env.example`

**Setup:**
```bash
cp .env.example .env
# Edit .env with your values
```

**Important:** Never commit `.env` to git! It's in `.gitignore`.

## Database Configuration

### `DB_HOST`
**Description:** PostgreSQL database hostname

**Values:**
- `localhost` - When connecting from host machine
- `db` - When connecting from Docker containers

**Default:** `localhost`

**Example:**
```bash
# From host machine
DB_HOST=localhost

# From Docker backend
DB_HOST=db
```

### `DB_PORT`
**Description:** PostgreSQL port number

**Values:** `5432` (standard PostgreSQL port)

**Default:** `5432`

**Example:**
```bash
DB_PORT=5432
```

### `DB_NAME`
**Description:** Database name

**Values:** `price_scraper`

**Default:** `price_scraper`

**Example:**
```bash
DB_NAME=price_scraper
```

### `DB_USER`
**Description:** Database username

**Values:**
- `postgres` - Default superuser
- `scraper_app` - Application-specific user

**Default:** `scraper_app`

**Example:**
```bash
DB_USER=postgres
```

### `DB_PASSWORD`
**Description:** Database password

**Security:** Keep this secret! Never commit to git.

**Default:** (none)

**Example:**
```bash
DB_PASSWORD=strongpassword123
```

### `DB_MIN_CONN`
**Description:** Minimum connections in connection pool

**Values:** Integer (1-100)

**Default:** `2`

**Example:**
```bash
DB_MIN_CONN=2
```

### `DB_MAX_CONN`
**Description:** Maximum connections in connection pool

**Values:** Integer (1-100)

**Default:** `10`

**Example:**
```bash
DB_MAX_CONN=10
```

## Feature Flags

### `USE_DATABASE`
**Description:** Enable database writes for scrapers

**Values:**
- `1` - Enable (write to both JSON and database)
- `0` - Disable (write to JSON only)

**Default:** `0`

**Example:**
```bash
# Enable database writes
USE_DATABASE=1

# Disable database writes
USE_DATABASE=0
```

## Flask Configuration

### `FLASK_ENV`
**Description:** Flask environment mode

**Values:**
- `development` - Development mode (debug, auto-reload)
- `production` - Production mode

**Default:** `development`

**Example:**
```bash
FLASK_ENV=development
```

### `FLASK_DEBUG`
**Description:** Enable Flask debug mode

**Values:**
- `1` - Enable debug mode
- `0` - Disable debug mode

**Default:** `1` (development), `0` (production)

**Example:**
```bash
FLASK_DEBUG=1
```

### `FLASK_APP`
**Description:** Flask application entry point

**Values:** Path to Flask app (e.g., `app.py`, `backend/app.py`)

**Default:** `app.py`

**Example:**
```bash
FLASK_APP=backend/app.py
```

## Frontend Configuration

### `VITE_API_URL`
**Description:** Backend API URL for frontend

**Values:** Full URL with protocol

**Default:** `http://localhost:5000/api`

**Example:**
```bash
# Development
VITE_API_URL=http://localhost:5000/api

# Production
VITE_API_URL=https://api.yoursite.com/api
```

### `CHOKIDAR_USEPOLLING`
**Description:** Enable file watching polling for Vite (needed for Docker)

**Values:**
- `true` - Enable polling (Docker)
- `false` - Disable polling (native)

**Default:** `false`

**Example:**
```bash
# For Docker
CHOKIDAR_USEPOLLING=true

# For native development
CHOKIDAR_USEPOLLING=false
```

## Docker Environment

### Container-Specific Variables

Variables set in `docker-compose.yml` for container communication:

**Backend:**
```yaml
environment:
  DB_HOST: db              # Container name
  DB_PORT: 5432
  FLASK_ENV: development
  FLASK_DEBUG: 1
```

**Frontend:**
```yaml
environment:
  VITE_API_URL: http://localhost:5000/api
  CHOKIDAR_USEPOLLING: true
```

**Database:**
```yaml
environment:
  POSTGRES_DB: price_scraper
  POSTGRES_USER: postgres
  POSTGRES_PASSWORD: strongpassword
```

## Complete .env Example

### Development (Docker)

```bash
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=price_scraper
DB_USER=postgres
DB_PASSWORD=strongpassword

# Connection Pool
DB_MIN_CONN=2
DB_MAX_CONN=10

# Feature Flags
USE_DATABASE=1

# Flask (set in docker-compose.yml)
# FLASK_ENV=development
# FLASK_DEBUG=1

# Frontend (set in docker-compose.yml)
# VITE_API_URL=http://localhost:5000/api
# CHOKIDAR_USEPOLLING=true
```

### Production

```bash
# Database Configuration
DB_HOST=db.production.com
DB_PORT=5432
DB_NAME=price_scraper_prod
DB_USER=app_user
DB_PASSWORD=super_secure_password_here_ABC123!

# Connection Pool
DB_MIN_CONN=5
DB_MAX_CONN=20

# Feature Flags
USE_DATABASE=1

# Flask
FLASK_ENV=production
FLASK_DEBUG=0

# Frontend
VITE_API_URL=https://api.yoursite.com/api
CHOKIDAR_USEPOLLING=false
```

## Using Environment Variables

### In Python

```python
import os

# Simple access
db_host = os.getenv('DB_HOST', 'localhost')

# With type conversion
db_port = int(os.getenv('DB_PORT', '5432'))
use_database = os.getenv('USE_DATABASE', '0') == '1'

# From DatabaseConfig
from database.db_utils import DatabaseConfig

config = DatabaseConfig()
print(config.host)      # Uses DB_HOST
print(config.port)      # Uses DB_PORT
print(config.database)  # Uses DB_NAME
```

### In Shell Scripts

```bash
#!/bin/bash

# Load from .env file
set -a
source .env
set +a

# Use variables
echo "Connecting to $DB_HOST:$DB_PORT"
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME
```

### In Docker Compose

```yaml
services:
  backend:
    environment:
      - DB_HOST=${DB_HOST:-db}
      - DB_PORT=${DB_PORT:-5432}
```

### In React/Vite

```javascript
// Must be prefixed with VITE_
const apiUrl = import.meta.env.VITE_API_URL;

console.log('API URL:', apiUrl);
```

## Environment-Specific Configurations

### Local Development

```bash
DB_HOST=localhost
DB_PORT=5432
USE_DATABASE=1
FLASK_DEBUG=1
```

### Docker Development

```bash
DB_HOST=localhost  # For host scripts
DB_PORT=5432
USE_DATABASE=1
```

Note: Docker containers use `DB_HOST=db` (set in docker-compose.yml)

### CI/CD Testing

```bash
DB_HOST=test-db
DB_NAME=price_scraper_test
DB_USER=test_user
DB_PASSWORD=test_password
USE_DATABASE=1
FLASK_ENV=testing
```

### Production

```bash
DB_HOST=production-db.internal
DB_NAME=price_scraper_prod
DB_USER=app_user
DB_PASSWORD=<from-secrets-manager>
USE_DATABASE=1
FLASK_ENV=production
FLASK_DEBUG=0
```

## Security Best Practices

### 1. Never Commit .env

```bash
# Ensure .env is in .gitignore
echo ".env" >> .gitignore

# Provide example instead
cp .env .env.example
# Remove sensitive values from .env.example
```

### 2. Use Secrets Management

**Production:**
- AWS Secrets Manager
- HashiCorp Vault
- Docker Secrets
- Kubernetes Secrets

**Example with Docker Secrets:**
```yaml
secrets:
  db_password:
    external: true

services:
  backend:
    environment:
      DB_PASSWORD_FILE: /run/secrets/db_password
    secrets:
      - db_password
```

### 3. Rotate Passwords Regularly

```bash
# Generate strong password
openssl rand -base64 32

# Update in .env
DB_PASSWORD=new_secure_password_here

# Update in database
ALTER USER postgres PASSWORD 'new_secure_password_here';
```

### 4. Use Different Credentials per Environment

```bash
# Development
DB_USER=dev_user
DB_PASSWORD=dev_password

# Staging
DB_USER=staging_user
DB_PASSWORD=staging_password

# Production
DB_USER=prod_user
DB_PASSWORD=very_secure_prod_password
```

## Troubleshooting

### Environment Variables Not Loaded

```bash
# Check if .env exists
ls -la .env

# Load manually
export $(cat .env | grep -v '^#' | xargs)

# Verify
echo $DB_HOST
echo $DB_PORT
```

### Wrong Values Used

```bash
# Check current environment
env | grep DB_

# Python check
python3 -c "import os; print('DB_HOST:', os.getenv('DB_HOST'))"

# Clear and reload
unset DB_HOST DB_PORT DB_NAME
export $(cat .env | grep -v '^#' | xargs)
```

### Docker Not Using .env

```bash
# docker-compose automatically loads .env
# Verify with:
docker-compose config

# Force rebuild to pick up changes
docker-compose down
docker-compose up -d --build
```

## Validation

### Check All Required Variables

```python
# scripts/check_env.py
import os
import sys

REQUIRED_VARS = [
    'DB_HOST',
    'DB_PORT',
    'DB_NAME',
    'DB_USER',
    'DB_PASSWORD',
]

missing = []
for var in REQUIRED_VARS:
    if not os.getenv(var):
        missing.append(var)

if missing:
    print("Missing required environment variables:")
    for var in missing:
        print(f"  - {var}")
    sys.exit(1)

print("✓ All required environment variables are set")
```

Run validation:
```bash
python3 scripts/check_env.py
```

---

**For more information, see [README.md](../README.md)**
