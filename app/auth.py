from flask import request, g, jsonify, current_app
from datetime import datetime, timezone
from sqlalchemy import select
from app.db import get_session
from app.models import APIKey
from utils.api_key import verify_api_key


async def require_api_key():
    # Allow health checks and OPTIONS through
    if request.path == "/health" or request.method == "OPTIONS":
        return

    # If DB is marked unavailable by app guard, avoid querying DB
    if not current_app.config.get("DB_AVAILABLE", True):
        return jsonify({
            "error": "service_unavailable",
            "message": "Database is unavailable. Please try again later.",
            "detail": "auth_db_down",
        }), 503

    provided = request.headers.get("X-API-Key")
    if not provided:
        return jsonify({"error": "missing api key"}), 401

    kid = request.headers.get("X-API-Key-Id")

    async with get_session() as session:
        if kid:
            result = await session.execute(
                select(APIKey).where(APIKey.id == kid, APIKey.active.is_(True))
            )
            row = result.scalar_one_or_none()
            if row and verify_api_key(provided, row.hash):
                row.last_used_at = datetime.now(timezone.utc)
                session.add(row)
                await session.commit()
                g.api_key_id = row.id
                return
            return jsonify({"error": "unauthorized"}), 401

        # No kid provided: iterate active keys (small number expected)
        result = await session.execute(select(APIKey).where(APIKey.active.is_(True)))
        rows = result.scalars().all()
        for row in rows:
            try:
                if verify_api_key(provided, row.hash):
                    row.last_used_at = datetime.now(timezone.utc)
                    session.add(row)
                    await session.commit()
                    g.api_key_id = row.id
                    return
            except Exception:
                continue

        return jsonify({"error": "unauthorized"}), 401
