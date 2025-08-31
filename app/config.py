import os
import secrets
from pathlib import Path

try:
    # optional dependency
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


def configure_app(app):
    # Load .env into environment when available
    env_path = Path(app.root_path).parent / ".env"
    if load_dotenv and env_path.exists():
        load_dotenv(env_path)

    # Set configuration from environment with sensible defaults
    # SECRET_KEY: if not provided, generate a secure random one at startup
    env_secret = os.environ.get("SECRET_KEY")
    if env_secret:
        app.config.setdefault("SECRET_KEY", env_secret)
    else:
        # Generate once per process; suitable for containerized deployments where env isn't provided
        generated = secrets.token_urlsafe(48)
        app.config.setdefault("SECRET_KEY", generated)
        # Optional: expose to process env for libraries that read os.environ directly
        os.environ.setdefault("SECRET_KEY", generated)
    # DATABASE_URL must be provided (e.g., postgresql://...)
    if "DATABASE_URL" in os.environ:
        app.config.setdefault("DATABASE_URL", os.environ["DATABASE_URL"])