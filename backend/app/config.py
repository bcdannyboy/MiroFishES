"""
Configuration management.
Loads settings from the repository root `.env` file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load the `.env` file from the repository root.
# Path: MiroFishES/.env (relative to backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # If the root `.env` file is missing, fall back to the environment.
    load_dotenv(override=True)


@dataclass(frozen=True)
class TaskModelRoute:
    """Resolved model route for one task lane."""

    task: str
    model: str
    api_key: str | None
    base_url: str


class Config:
    """Flask configuration."""
    
    # Flask settings.
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # JSON settings. Disable ASCII escaping so non-ASCII text is returned
    # directly instead of as \uXXXX sequences.
    JSON_AS_ASCII = False
    
    # LLM settings using the OpenAI-compatible API shape.
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', LLM_API_KEY)
    OPENAI_BASE_URL = os.environ.get('OPENAI_BASE_URL', LLM_BASE_URL)
    OPENAI_DEFAULT_MODEL = os.environ.get('OPENAI_DEFAULT_MODEL', LLM_MODEL_NAME)
    OPENAI_REASONING_MODEL = os.environ.get(
        'OPENAI_REASONING_MODEL',
        OPENAI_DEFAULT_MODEL,
    )
    OPENAI_REPORT_MODEL = os.environ.get(
        'OPENAI_REPORT_MODEL',
        OPENAI_DEFAULT_MODEL,
    )
    OPENAI_EMBEDDING_MODEL = os.environ.get(
        'OPENAI_EMBEDDING_MODEL',
        'text-embedding-3-small',
    )
    LOCAL_EMBEDDING_API_KEY = os.environ.get(
        'LOCAL_EMBEDDING_API_KEY',
        OPENAI_API_KEY,
    )
    LOCAL_EMBEDDING_BASE_URL = os.environ.get(
        'LOCAL_EMBEDDING_BASE_URL',
        OPENAI_BASE_URL,
    )
    LOCAL_EMBEDDING_MODEL = os.environ.get(
        'LOCAL_EMBEDDING_MODEL',
        OPENAI_EMBEDDING_MODEL,
    )
    LOCAL_EMBEDDING_DIMENSIONS = os.environ.get('LOCAL_EMBEDDING_DIMENSIONS')
    
    # Zep settings.
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')
    
    # File upload settings.
    MAX_UPLOAD_SIZE_MB = int(os.environ.get('MAX_UPLOAD_SIZE_MB', '100'))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    
    # Text processing settings.
    DEFAULT_CHUNK_SIZE = 500  # Default chunk size.
    DEFAULT_CHUNK_OVERLAP = 50  # Default overlap size.
    
    # OASIS simulation settings.
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    FORECAST_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/forecasts')
    PROBABILISTIC_PREPARE_ENABLED = (
        os.environ.get('PROBABILISTIC_PREPARE_ENABLED', 'false').lower() == 'true'
    )
    PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED = (
        os.environ.get(
            'PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED',
            os.environ.get('ENSEMBLE_RUNTIME_ENABLED', 'false'),
        ).lower() == 'true'
    )
    PROBABILISTIC_REPORT_ENABLED = (
        os.environ.get('PROBABILISTIC_REPORT_ENABLED', 'false').lower() == 'true'
    )
    PROBABILISTIC_INTERACTION_ENABLED = (
        os.environ.get('PROBABILISTIC_INTERACTION_ENABLED', 'false').lower() == 'true'
    )
    CALIBRATED_PROBABILITY_ENABLED = (
        os.environ.get('CALIBRATED_PROBABILITY_ENABLED', 'false').lower() == 'true'
    )
    CALIBRATION_MIN_CASE_COUNT = int(os.environ.get('CALIBRATION_MIN_CASE_COUNT', '10'))
    CALIBRATION_MIN_POSITIVE_CASE_COUNT = int(
        os.environ.get('CALIBRATION_MIN_POSITIVE_CASE_COUNT', '3')
    )
    CALIBRATION_MIN_NEGATIVE_CASE_COUNT = int(
        os.environ.get('CALIBRATION_MIN_NEGATIVE_CASE_COUNT', '3')
    )
    CALIBRATION_MIN_SUPPORTED_BIN_COUNT = int(
        os.environ.get('CALIBRATION_MIN_SUPPORTED_BIN_COUNT', '2')
    )
    CALIBRATION_BIN_COUNT = int(os.environ.get('CALIBRATION_BIN_COUNT', '5'))
    CALIBRATION_LOG_SCORE_EPSILON = float(
        os.environ.get('CALIBRATION_LOG_SCORE_EPSILON', '1e-6')
    )
    # Keep the legacy name as a compatibility alias until all callers migrate.
    ENSEMBLE_RUNTIME_ENABLED = PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED
    
    # OASIS platform action settings.
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Report Agent settings.
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))

    @classmethod
    def get_openai_api_key(cls) -> str | None:
        """Resolve the preferred API key with legacy compatibility fallbacks."""
        return os.environ.get('OPENAI_API_KEY', os.environ.get('LLM_API_KEY', cls.OPENAI_API_KEY))

    @classmethod
    def get_openai_base_url(cls) -> str:
        """Resolve the preferred OpenAI-compatible base URL."""
        return os.environ.get(
            'OPENAI_BASE_URL',
            os.environ.get('LLM_BASE_URL', cls.OPENAI_BASE_URL),
        )

    @classmethod
    def get_default_model_name(cls) -> str:
        """Resolve the fast/default model name."""
        legacy_default = os.environ.get('LLM_MODEL_NAME', cls.OPENAI_DEFAULT_MODEL)
        return os.environ.get('OPENAI_DEFAULT_MODEL', legacy_default)

    @classmethod
    def get_reasoning_model_name(cls) -> str:
        """Resolve the reasoning/extraction model name."""
        return os.environ.get('OPENAI_REASONING_MODEL', cls.get_default_model_name())

    @classmethod
    def get_report_model_name(cls) -> str:
        """Resolve the report-friendly model name."""
        return os.environ.get('OPENAI_REPORT_MODEL', cls.get_default_model_name())

    @classmethod
    def get_embedding_model_name(cls) -> str:
        """Resolve the embedding model name."""
        return os.environ.get(
            'LOCAL_EMBEDDING_MODEL',
            os.environ.get(
                'OPENAI_EMBEDDING_MODEL',
                cls.OPENAI_EMBEDDING_MODEL,
            ),
        )

    @classmethod
    def get_embedding_api_key(cls) -> str | None:
        """Resolve the embedding API key."""
        return os.environ.get(
            'LOCAL_EMBEDDING_API_KEY',
            os.environ.get(
                'EMBEDDING_API_KEY',
                cls.get_openai_api_key(),
            ),
        )

    @classmethod
    def get_embedding_base_url(cls) -> str:
        """Resolve the embedding API base URL."""
        return os.environ.get(
            'LOCAL_EMBEDDING_BASE_URL',
            os.environ.get(
                'EMBEDDING_BASE_URL',
                cls.get_openai_base_url(),
            ),
        )

    @classmethod
    def get_embedding_dimensions(cls) -> int | None:
        """Resolve optional embedding dimensions override."""
        raw_value = os.environ.get('LOCAL_EMBEDDING_DIMENSIONS', cls.LOCAL_EMBEDDING_DIMENSIONS)
        if raw_value in (None, ''):
            return None
        return int(raw_value)

    @classmethod
    def get_forecast_data_dir(cls) -> str:
        """Resolve the forecast artifact root."""
        return os.environ.get('FORECAST_DATA_DIR', cls.FORECAST_DATA_DIR)

    @classmethod
    def get_local_evidence_index_path(cls) -> str:
        """Resolve the local evidence index storage path."""
        return os.environ.get(
            'LOCAL_EVIDENCE_INDEX_PATH',
            os.path.join(cls.get_forecast_data_dir(), 'local_evidence_index.sqlite3'),
        )

    @classmethod
    def get_task_model_routes(cls) -> dict[str, TaskModelRoute]:
        """Resolve task-scoped model routing for later forecasting phases."""
        api_key = cls.get_openai_api_key()
        base_url = cls.get_openai_base_url()
        default_model = cls.get_default_model_name()
        return {
            'default': TaskModelRoute(
                task='default',
                model=default_model,
                api_key=api_key,
                base_url=base_url,
            ),
            'reasoning': TaskModelRoute(
                task='reasoning',
                model=cls.get_reasoning_model_name(),
                api_key=api_key,
                base_url=base_url,
            ),
            'report': TaskModelRoute(
                task='report',
                model=cls.get_report_model_name(),
                api_key=api_key,
                base_url=base_url,
            ),
            'embedding': TaskModelRoute(
                task='embedding',
                model=cls.get_embedding_model_name(),
                api_key=cls.get_embedding_api_key(),
                base_url=cls.get_embedding_base_url(),
            ),
        }
    
    @classmethod
    def validate(cls):
        """Validate required settings."""
        errors = []
        if not cls.get_openai_api_key():
            errors.append("LLM_API_KEY or OPENAI_API_KEY is not configured")
        if not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY is not configured")
        return errors
