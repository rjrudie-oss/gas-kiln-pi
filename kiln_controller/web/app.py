"""Flask dashboard.

Deliberately monitoring-first. The only *control* it exposes is an emergency
stop, because stopping is always the safe direction. It never lets the browser
open the valve or raise the setpoint directly: firing is driven by the profile
in the config so an unattended or malicious web client cannot overheat the kiln.

The dashboard reads the controller's published state snapshot; it never talks to
the hardware directly, so a dashboard bug can never move the valve.
"""
from __future__ import annotations

import os
from typing import Optional

from flask import Flask, jsonify, render_template, request

from ..config import Config
from ..state import read_state


def create_app(cfg: Optional[Config] = None, state_path: str = "/run/kiln/state.json") -> Flask:
    cfg = cfg or Config.load()
    app = Flask(__name__)

    @app.route("/")
    def index():
        return render_template(
            "index.html",
            poll_ms=int(cfg.web.poll_interval_s * 1000),
            damper_enabled=cfg.damper.enabled,
        )

    @app.route("/api/state")
    def api_state():
        state = read_state(state_path)
        estop = os.path.exists(cfg.safety.estop_path)
        if state is None:
            return jsonify({"available": False, "estop": estop}), 200
        data = state.__dict__.copy()
        data["available"] = True
        data["estop"] = estop
        return jsonify(data)

    @app.route("/api/estop", methods=["POST"])
    def api_estop():
        """Engage or clear the software emergency stop."""
        engage = request.json.get("engage", True) if request.is_json else True
        path = cfg.safety.estop_path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if engage:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("engaged")
            return jsonify({"estop": True})
        if os.path.exists(path):
            os.remove(path)
        return jsonify({"estop": False})

    @app.route("/api/damper", methods=["POST"])
    def api_damper():
        """Set the requested chimney-damper position (0-100 %)."""
        if not cfg.damper.enabled:
            return jsonify({"error": "damper disabled"}), 400
        if not request.is_json:
            return jsonify({"error": "expected JSON"}), 400
        try:
            percent = float(request.json.get("percent"))
        except (TypeError, ValueError):
            return jsonify({"error": "invalid percent"}), 400
        percent = max(0.0, min(100.0, percent))
        path = cfg.damper.command_path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(str(percent))
        return jsonify({"damper_target": percent})

    return app


def main(argv: Optional[list] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Kiln web dashboard")
    parser.add_argument("-c", "--config", default=None)
    parser.add_argument("--state-path", default="/run/kiln/state.json")
    args = parser.parse_args(argv)
    cfg = Config.load(args.config)
    app = create_app(cfg, state_path=args.state_path)
    app.run(host=cfg.web.host, port=cfg.web.port)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
