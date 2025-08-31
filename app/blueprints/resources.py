from flask import Blueprint, jsonify
from sqlalchemy import select
from app.models import Resource
from app.db import get_session

bp = Blueprint("resources", __name__)


@bp.route("/", methods=["GET"])
async def list_resources():
    async with get_session() as session:
        result = await session.execute(select(Resource))
        rows = result.scalars().all()
        return jsonify([{"slug": r.slug, "name": r.name} for r in rows])


@bp.route("/<slug>", methods=["GET"])
async def get_resource(slug):
    async with get_session() as session:
        result = await session.execute(select(Resource).where(Resource.slug == slug))
        r = result.scalar_one_or_none()
        if not r:
            return (jsonify({"error": "not found"}), 404)
        return jsonify({"slug": r.slug, "name": r.name})
