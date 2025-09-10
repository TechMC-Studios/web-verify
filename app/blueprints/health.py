from flask import Blueprint, jsonify
from sqlalchemy import text
from ..db import get_engine

bp = Blueprint("health", __name__)


@bp.route("/health", methods=["GET"])
async def health():
    """Return overall service health.

    Performs a lightweight DB connectivity check. If the database is not
    reachable or the query fails, return 503 to signal the service is not
    healthy.
    """
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return jsonify({"status": "ok"})
    except Exception as e:
        # Hide internal error details from clients; just report unhealthy
        return jsonify({
            "status": "unhealthy",
            "checks": {
                "database": "down"
            }
        }), 503
