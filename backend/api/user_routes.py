"""User settings routes: API key management."""
from flask import Blueprint, request, jsonify, g

from database import db_connection
from protocol_models import UserLLMKeyRequest, UserLLMKeyStatusResponse
from api.device_routes import require_auth

user_bp = Blueprint("user", __name__, url_prefix="/api/user")


@user_bp.route("/llm-key", methods=["PUT"])
@require_auth
def set_llm_key():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "请求体不能为空"}), 400

    try:
        data = UserLLMKeyRequest(**body)
    except Exception as e:
        return jsonify({"error": str(e)}), 422

    with db_connection() as conn:
        conn.execute(
            "UPDATE user SET llm_api_key = ? WHERE id = ?",
            (data.api_key, g.user_id),
        )
        conn.commit()

    return jsonify({"ok": True}), 200


@user_bp.route("/llm-key", methods=["DELETE"])
@require_auth
def delete_llm_key():
    with db_connection() as conn:
        conn.execute(
            "UPDATE user SET llm_api_key = '' WHERE id = ?",
            (g.user_id,),
        )
        conn.commit()

    return jsonify({"ok": True}), 200


@user_bp.route("/llm-key/status", methods=["GET"])
@require_auth
def get_llm_key_status():
    with db_connection() as conn:
        user = conn.execute(
            "SELECT llm_api_key FROM user WHERE id = ?",
            (g.user_id,),
        ).fetchone()

    configured = bool(user and user["llm_api_key"])
    return jsonify(UserLLMKeyStatusResponse(configured=configured).model_dump()), 200
