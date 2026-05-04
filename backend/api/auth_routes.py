"""Auth routes: registration and login."""
from flask import Blueprint, request, jsonify

from database import db_connection
from auth import hash_password, verify_password, create_access_token
from protocol_models import UserRegisterRequest, UserLoginRequest, AuthResponse

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Invalid JSON"}), 400

    try:
        data = UserRegisterRequest(**body)
    except Exception as e:
        return jsonify({"error": str(e)}), 422

    with db_connection() as conn:
        # Find or create family
        family = conn.execute(
            "SELECT id FROM family WHERE name = ?", (data.family_name,)
        ).fetchone()

        if family:
            family_id = family["id"]
        else:
            cur = conn.execute(
                "INSERT INTO family (name) VALUES (?)", (data.family_name,)
            )
            family_id = cur.lastrowid

        # Check duplicate email
        existing = conn.execute(
            "SELECT id FROM user WHERE email = ?", (data.email,)
        ).fetchone()
        if existing:
            return jsonify({"error": "邮箱已注册"}), 409

        pw_hash = hash_password(data.password)
        cur = conn.execute(
            "INSERT INTO user (family_id, email, password_hash, display_name) VALUES (?,?,?,?)",
            (family_id, data.email, pw_hash, data.display_name),
        )
        user_id = cur.lastrowid
        conn.commit()

    token = create_access_token(user_id, family_id)
    resp = AuthResponse(
        access_token=token,
        user_id=user_id,
        family_id=family_id,
        display_name=data.display_name,
    )
    return jsonify(resp.model_dump()), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Invalid JSON"}), 400

    try:
        data = UserLoginRequest(**body)
    except Exception as e:
        return jsonify({"error": str(e)}), 422

    with db_connection() as conn:
        user = conn.execute(
            "SELECT id, family_id, password_hash, display_name FROM user WHERE email = ?",
            (data.email,),
        ).fetchone()

        if not user or not verify_password(data.password, user["password_hash"]):
            return jsonify({"error": "邮箱或密码错误"}), 401

    token = create_access_token(user["id"], user["family_id"])
    resp = AuthResponse(
        access_token=token,
        user_id=user["id"],
        family_id=user["family_id"],
        display_name=user["display_name"],
    )
    return jsonify(resp.model_dump()), 200
