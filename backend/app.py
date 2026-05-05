"""ScreenPlan Backend - Flask Application.
Entry point for the OpenWrt router server.

Usage:
    python run.py
    gunicorn -w 2 -b 0.0.0.0:5051 app:app
    SCREENPLAN_DATA_DIR=/mnt/usb/screenplan python run.py
"""
import os
from pathlib import Path

from flask import Flask, send_from_directory

from config import VERSION
from database import init_db
from api import auth_bp, device_bp, usage_bp, schedule_bp, health_bp, friend_bp, user_bp


def create_app() -> Flask:
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)

    app = Flask(__name__, static_folder=str(static_dir), static_url_path="/static")

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(device_bp)
    app.register_blueprint(usage_bp)
    app.register_blueprint(schedule_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(friend_bp)
    app.register_blueprint(user_bp)

    # CORS - allow LAN access from any device
    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS, PUT"
        return response

    @app.before_request
    def handle_options():
        from flask import request
        if request.method == "OPTIONS":
            return app.make_default_options_response()

    # SPA route: serve index.html for the root and any non-API path
    @app.route("/")
    @app.route("/<path:path>")
    def serve_spa(path="index.html"):
        if path.startswith("api/") or path.startswith("static/"):
            from flask import abort
            abort(404)
        index_path = static_dir / "index.html"
        if index_path.exists() and (path == "" or path == "index.html" or "." not in path):
            return send_from_directory(str(static_dir), "index.html")
        file_path = static_dir / path
        if file_path.exists():
            return send_from_directory(str(static_dir), path)
        return send_from_directory(str(static_dir), "index.html")

    return app


# Initialize DB on import
init_db()

app = create_app()

if __name__ == "__main__":
    from config import SERVER_HOST, SERVER_PORT, DEBUG
    print(f"ScreenPlan Backend v{VERSION}")
    print(f"Listening on {SERVER_HOST}:{SERVER_PORT}")
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=DEBUG)
