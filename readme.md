## Install dependencies

```bash
pip install -r requirements.txt
```

## Run bot

```bash
python main.py
```

## Environment variables

The environment variables are loaded from the `.env` file. You can create a `.env` file by copying the `.env.example` file.

```
cp .env.example .env
```

### Generate .env via CLI (recommended)

You can also generate `.env` using the project manager:

```bash
# From web/
python manage.py init-env

# Overwrite existing .env
python manage.py init-env --force

# Set DATABASE_URL at generation time
python manage.py init-env --database-url "postgresql://user:pass@localhost:5432/dbname"
```

This command will:
- Create `.env` from `.env.example` if present or a minimal template otherwise.
- Inject a secure, random `SECRET_KEY`.
- Optionally set `DATABASE_URL`.

## API Key Management (manage.py)

This project includes a small CLI to manage API keys. Run commands from the `web/` directory:

```bash
# Create a new API key (prints id and the plaintext key once)
python manage.py create --name "ops" --scopes read write --length 48

# List existing API keys
python manage.py list
python manage.py list --json

# Activate / Deactivate a key
python manage.py activate <id>
python manage.py deactivate <id>

# Delete a key
python manage.py delete <id>
```

Notes:
- The CLI loads environment variables from `.env` if present (e.g., `DATABASE_URL`).
- The API server creates the first API key automatically on first boot if none exist and prints it to the console.

## Database Management (manage.py)

Use the CLI to manage the database:

```bash
# Drop and recreate all tables (DANGEROUS)
python manage.py db-reset --yes-i-am-sure

# Export all data to JSON
python manage.py db-export --output data/export.json

# Import data from JSON (optionally wipe first)
python manage.py db-import --input data/export.json
python manage.py db-import --input data/export.json --wipe

# Test database connectivity
python manage.py db-test
```

Notes:
- `db-reset` is destructive; it drops all tables and recreates them.
- `db-export` includes all tables (platforms, resources, links, users, purchases, api_keys). API keys are exported without plaintext.
- `db-import` upserts by primary key. Use `--wipe` to start from a clean database.