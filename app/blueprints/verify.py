from flask import Blueprint, request, jsonify
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.db import get_session
from app.models import User, Purchase, Resource, Platform

bp = Blueprint("verify", __name__)


async def _get_platform_id(session, name):
    result = await session.execute(select(Platform).where(Platform.name == name))
    p = result.scalar_one_or_none()
    return p.id if p else None


@bp.route("/spigot", methods=["POST"])
async def verify_spigot():
    data = request.get_json() or {}
    required = ("spigotUserId", "spigotUsername", "resourceSlug")
    if not all(k in data for k in required):
        return (jsonify({"error": "missing fields"}), 400)

    async with get_session() as session:
        platform_id = await _get_platform_id(session, "spigot")
        if platform_id is None:
            return (jsonify({"error": "platform not configured"}), 500)

        # upsert user
        result_u = await session.execute(
            select(User).where(User.platform_id == platform_id, User.external_user_id == str(data["spigotUserId"]))
        )
        u = result_u.scalar_one_or_none()
        if not u:
            u = User(platform_id=platform_id, external_user_id=str(data["spigotUserId"]), username=data["spigotUsername"])
            session.add(u)
            await session.commit()

        # find resource
        result_r = await session.execute(select(Resource).where(Resource.slug == data["resourceSlug"]))
        r = result_r.scalar_one_or_none()
        if not r:
            return (jsonify({"error": "resource not found"}), 404)

        # avoid duplicate purchase for same user/resource/platform
        exists_q = await session.execute(
            select(Purchase).where(
                Purchase.user_id == u.id,
                Purchase.resource_id == r.id,
                Purchase.platform_id == platform_id,
            )
        )
        if exists_q.scalar_one_or_none():
            return (
                jsonify({"verified": True, "duplicate": True, "userId": str(u.id), "resourceId": str(r.id)}),
                409,
            )

        # create purchase
        p = Purchase(user_id=u.id, resource_id=r.id, platform_id=platform_id)
        session.add(p)
        await session.commit()

        return jsonify({"verified": True, "userId": str(u.id), "resourceId": str(r.id)})


@bp.route("/polymart", methods=["POST"])
async def verify_polymart():
    data = request.get_json() or {}
    required = ("polymartUserId", "polymartUsername", "resourceSlug")
    if not all(k in data for k in required):
        return (jsonify({"error": "missing fields"}), 400)

    async with get_session() as session:
        platform_id = await _get_platform_id(session, "polymart")
        if platform_id is None:
            return (jsonify({"error": "platform not configured"}), 500)

        result_u = await session.execute(
            select(User).where(User.platform_id == platform_id, User.external_user_id == str(data["polymartUserId"]))
        )
        u = result_u.scalar_one_or_none()
        if not u:
            u = User(platform_id=platform_id, external_user_id=str(data["polymartUserId"]), username=data["polymartUsername"])
            session.add(u)
            await session.commit()

        result_r = await session.execute(select(Resource).where(Resource.slug == data["resourceSlug"]))
        r = result_r.scalar_one_or_none()
        if not r:
            return (jsonify({"error": "resource not found"}), 404)

        # avoid duplicate purchase for same user/resource/platform
        exists_q = await session.execute(
            select(Purchase).where(
                Purchase.user_id == u.id,
                Purchase.resource_id == r.id,
                Purchase.platform_id == platform_id,
            )
        )
        if exists_q.scalar_one_or_none():
            return (
                jsonify({"verified": True, "duplicate": True, "userId": str(u.id), "resourceId": str(r.id)}),
                409,
            )

        p = Purchase(user_id=u.id, resource_id=r.id, platform_id=platform_id)
        session.add(p)
        await session.commit()

        return jsonify({"verified": True, "userId": str(u.id), "resourceId": str(r.id)})
