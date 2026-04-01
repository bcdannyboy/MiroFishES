"""
MiroFishES backend Flask application factory.
"""

import importlib
import os
import warnings

# Suppress multiprocessing resource_tracker warnings from third-party libraries
# such as transformers. This must run before other imports.
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.exceptions import RequestEntityTooLarge

from .config import Config
from .utils.logger import setup_logger, get_logger


def create_app(config_class=Config):
    """Create the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    def _format_upload_limit(max_bytes):
        if not max_bytes:
            return "configured size limit"
        if max_bytes >= 1024 * 1024:
            megabytes = max_bytes / (1024 * 1024)
            if float(megabytes).is_integer():
                return f"{int(megabytes)} MB"
            return f"{megabytes:.1f} MB"
        if max_bytes >= 1024:
            kilobytes = max_bytes / 1024
            if float(kilobytes).is_integer():
                return f"{int(kilobytes)} KB"
            return f"{kilobytes:.1f} KB"
        return f"{max_bytes} bytes"
    
    # Keep JSON output unescaped so non-ASCII text is returned directly instead
    # of as \uXXXX sequences. Flask >= 2.3 uses app.json.ensure_ascii; older
    # versions rely on JSON_AS_ASCII.
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # Configure logging.
    logger = setup_logger('mirofish')
    
    # Only log startup from the reloader child process to avoid duplicate output
    # in debug mode.
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 50)
        logger.info("MiroFishES backend starting...")
        logger.info("=" * 50)
    
    # Enable CORS.
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Register simulation cleanup so all child processes terminate when the
    # server shuts down.
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("Registered simulation process cleanup")
    
    # Request logging middleware.
    @app.before_request
    def log_request():
        logger = get_logger('mirofish.request')
        logger.debug(f"Request: {request.method} {request.path}")
        if request.content_type and 'json' in request.content_type:
            logger.debug(f"Request body: {request.get_json(silent=True)}")
    
    @app.after_request
    def log_response(response):
        logger = get_logger('mirofish.request')
        logger.debug(f"Response: {response.status_code}")
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_entity_too_large(_error):
        max_bytes = app.config.get('MAX_CONTENT_LENGTH')
        return jsonify({
            "success": False,
            "error": (
                f"Upload exceeds the {_format_upload_limit(max_bytes)} limit. "
                "Remove some files or split the upload into smaller batches."
            ),
            "max_upload_bytes": max_bytes,
        }), 413
    
    # Prefer route-module blueprints when available, but fall back to the
    # package-level stubs used by the backend test harness.
    from . import api as api_package

    graph_module = importlib.import_module(".api.graph", __name__)
    simulation_module = importlib.import_module(".api.simulation", __name__)
    report_module = importlib.import_module(".api.report", __name__)
    forecast_module = importlib.import_module(".api.forecast", __name__)

    graph_bp = getattr(graph_module, "graph_bp", api_package.graph_bp)
    simulation_bp = getattr(simulation_module, "simulation_bp", api_package.simulation_bp)
    report_bp = getattr(report_module, "report_bp", api_package.report_bp)
    forecast_bp = getattr(forecast_module, "forecast_bp", api_package.forecast_bp)
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    app.register_blueprint(forecast_bp, url_prefix='/api/forecast')
    
    # Health check.
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'MiroFishES Backend'}
    
    if should_log_startup:
        logger.info("MiroFishES backend startup complete")
    
    return app
