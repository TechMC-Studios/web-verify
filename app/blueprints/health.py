from flask import Blueprint, jsonify

bp = Blueprint("health", __name__)


@bp.route("/health", methods=["GET"])
async def health():
    return jsonify({"status": "ok"})
