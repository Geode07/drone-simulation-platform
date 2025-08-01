#routes.py
import os
from flask import request, jsonify, send_from_directory, abort

def try_index_paths(possible_dirs, strict=False, context="unknown"):
    for i, dist_dir in enumerate(possible_dirs):
        index_path = os.path.join(dist_dir, "index.html")
        print(f"[{context.upper()} DEBUG] Attempt {i+1}: Checking {index_path}")
        if os.path.exists(index_path):
            print(f"[{context.upper()} DEBUG] Found index.html at: {index_path}")
            return send_from_directory(dist_dir, "index.html")
        else:
            print(f"[{context.upper()} ERROR] index.html not found at {index_path}")
    
    if strict:
        raise FileNotFoundError(f"[{context.upper()}] index.html not found in any known path")

    return jsonify({
        "error": "index.html not found in any known location",
        "tried": possible_dirs,
        "context": context
    }), 500


def register_routes(app):
    # Serve favicon cleanly to avoid 500s
    @app.route("/favicon.ico")
    def favicon():
        return "", 204

    # Main entrypoint
    @app.route("/")
    def index():
        possible_dirs = [
            os.path.join(app.root_path, "static", "frontend", "dist"),
            os.path.abspath(os.path.join(app.root_path, "..", "static", "frontend", "dist")),
            "/app/static/frontend/dist",
        ]
        return try_index_paths(possible_dirs, context="/")

    # Static JS/CSS assets
    @app.route("/assets/<path:filename>")
    def assets(filename):
        possible_dirs = [
            os.path.join(app.root_path, "static", "frontend", "dist"),               # vite build with assets flattened
            os.path.join(app.root_path, "static", "frontend", "dist", "assets"),     # vite default (nested assets)
            os.path.abspath(os.path.join(app.root_path, "..", "static", "frontend", "dist")),
            os.path.abspath(os.path.join(app.root_path, "..", "static", "frontend", "dist", "assets")),
            "/app/static/frontend/dist",
            "/app/static/frontend/dist/assets",
        ]

        for i, dist_dir in enumerate(possible_dirs):
            full_path = os.path.join(dist_dir, filename)
            print(f"[DEBUG] Attempt {i+1}: checking for asset at {full_path}")
            if os.path.exists(full_path):
                print(f"[DEBUG] Found asset: {full_path}")
                return send_from_directory(dist_dir, filename)

        print(f"[ERROR] Asset {filename} not found in any known paths.")
        return jsonify({"error": f"Asset '{filename}' not found"}), 404

    # Catch-all fallback
    @app.errorhandler(404)
    def not_found(e):
        print(f"[404 HANDLER] Path not found: {request.path}")
        if request.path.startswith(("/api/", "/static/", "/assets/")):
            return jsonify({"error": "Not found", "path": request.path}), 404

        possible_dirs = [
            os.path.join(app.root_path, "static", "frontend", "dist"),
            os.path.abspath(os.path.join(app.root_path, "..", "static", "frontend", "dist")),
            "/app/static/frontend/dist",
        ]
        return try_index_paths(possible_dirs, context="404")
