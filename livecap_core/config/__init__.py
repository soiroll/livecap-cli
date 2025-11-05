"""Core configuration helpers exposed for non-GUI consumers."""

from .defaults import DEFAULT_CONFIG, get_default_config, merge_config
from .validator import ConfigValidator, ValidationError

__all__ = [
    "DEFAULT_CONFIG",
    "get_default_config",
    "merge_config",
    "ConfigValidator",
    "ValidationError",
]
