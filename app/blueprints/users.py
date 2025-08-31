from flask import Blueprint, jsonify, request
from sqlalchemy import select, delete
from app.db import get_session
from app.models import User, Purchase, Resource, Platform

bp = Blueprint("users", __name__)


@bp.route("/<platform>/<external_user_id>", methods=["GET"])
async def get_user(platform, external_user_id):
    async with get_session() as session:
        # resolve platform name -> id
        res_pl = await session.execute(select(Platform).where(Platform.name == platform))
        pl = res_pl.scalar_one_or_none()
        if not pl:
            return (jsonify({"error": "platform not found"}), 404)

        result = await session.execute(
            select(User).where(User.platform_id == pl.id, User.external_user_id == external_user_id)
        )
        u = result.scalar_one_or_none()
        if not u:
            return (jsonify({"error": "not found"}), 404)

        result_p = await session.execute(select(Purchase).where(Purchase.user_id == u.id))
        purchases = result_p.scalars().all()
        resources = []
        for p in purchases:
            result_r = await session.execute(select(Resource).where(Resource.id == p.resource_id))
            r = result_r.scalar_one_or_none()
            if r:
                resources.append({"slug": r.slug, "verified_at": p.verified_at.isoformat()})
        return jsonify({
            "id": str(u.id),
            "username": u.username,
            "external_user_id": u.external_user_id,
            "discord_id": u.discord_id,
            "resources": resources,
        })


@bp.route("/<platform>/<external_user_id>", methods=["DELETE"])
async def delete_user(platform, external_user_id):
    async with get_session() as session:
        res_pl = await session.execute(select(Platform).where(Platform.name == platform))
        pl = res_pl.scalar_one_or_none()
        if not pl:
            return (jsonify({"error": "platform not found"}), 404)

        res_u = await session.execute(
            select(User).where(User.platform_id == pl.id, User.external_user_id == external_user_id)
        )
        u = res_u.scalar_one_or_none()
        if not u:
            return (jsonify({"error": "not found"}), 404)

        # delete dependent purchases then the user
        await session.execute(delete(Purchase).where(Purchase.user_id == u.id))
        await session.execute(delete(User).where(User.id == u.id))
        await session.commit()
        return jsonify({"deleted": True, "userId": str(u.id)})


@bp.route("/<platform>/<external_user_id>/discord", methods=["POST"])
async def set_discord(platform, external_user_id):
    payload = request.get_json() or {}
    discord_id = payload.get("discordId")
    if not discord_id:
        return (jsonify({"error": "missing discordId"}), 400)

    async with get_session() as session:
        res_pl = await session.execute(select(Platform).where(Platform.name == platform))
        pl = res_pl.scalar_one_or_none()
        if not pl:
            return (jsonify({"error": "platform not found"}), 404)

        res_u = await session.execute(
            select(User).where(User.platform_id == pl.id, User.external_user_id == external_user_id)
        )
        u = res_u.scalar_one_or_none()
        if not u:
            return (jsonify({"error": "not found"}), 404)

        # enforce uniqueness of discord_id per platform
        res_conflict = await session.execute(
            select(User).where(User.platform_id == pl.id, User.discord_id == discord_id, User.id != u.id)
        )
        if res_conflict.scalar_one_or_none():
            return (jsonify({"error": "discord id already in use for this platform"}), 409)

        u.discord_id = discord_id
        session.add(u)
        await session.commit()
        return jsonify({"updated": True, "userId": str(u.id), "discordId": u.discord_id})


@bp.route("/<platform>/<external_user_id>/discord", methods=["DELETE"])
async def unset_discord(platform, external_user_id):
    async with get_session() as session:
        res_pl = await session.execute(select(Platform).where(Platform.name == platform))
        pl = res_pl.scalar_one_or_none()
        if not pl:
            return (jsonify({"error": "platform not found"}), 404)

        res_u = await session.execute(
            select(User).where(User.platform_id == pl.id, User.external_user_id == external_user_id)
        )
        u = res_u.scalar_one_or_none()
        if not u:
            return (jsonify({"error": "not found"}), 404)

        u.discord_id = None
        session.add(u)
        await session.commit()
        return jsonify({"updated": True, "userId": str(u.id), "discordId": None})


@bp.route("/<platform>/discord/<discord_id>", methods=["GET"])
async def get_by_discord(platform, discord_id):
    async with get_session() as session:
        res_pl = await session.execute(select(Platform).where(Platform.name == platform))
        pl = res_pl.scalar_one_or_none()
        if not pl:
            return (jsonify({"error": "platform not found"}), 404)

        res_u = await session.execute(
            select(User).where(User.platform_id == pl.id, User.discord_id == discord_id)
        )
        u = res_u.scalar_one_or_none()
        if not u:
            return (jsonify({"error": "not found"}), 404)

        # include purchases/resources similar to get_user
        result_p = await session.execute(select(Purchase).where(Purchase.user_id == u.id))
        purchases = result_p.scalars().all()
        resources = []
        for p in purchases:
            result_r = await session.execute(select(Resource).where(Resource.id == p.resource_id))
            r = result_r.scalar_one_or_none()
            if r:
                resources.append({"slug": r.slug, "verified_at": p.verified_at.isoformat()})

        return jsonify({
            "id": str(u.id),
            "username": u.username,
            "external_user_id": u.external_user_id,
            "discord_id": u.discord_id,
            "resources": resources,
        })
