"""Flask example with drogue rate limiting."""

from flask import Flask, jsonify

from drogue.adapters.flask import DrogueLimiter
from drogue.core.config import DrogueConfig

app = Flask(__name__)

config = DrogueConfig(
    ban_enabled=True,
    ban_threshold=5,
    ddos_enabled=True,
    circuit_breaker_enabled=True,
)

limiter = DrogueLimiter(
    app,
    config=config,
    default_limits=["100/minute"],
)


@app.route("/")
@limiter.limit("10/minute")
def root():
    return jsonify({"message": "Hello, World!"})


@app.route("/expensive")
@limiter.limit("3/minute")
def expensive_endpoint():
    """Simulate an expensive operation."""
    return jsonify({"result": "computed"})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
