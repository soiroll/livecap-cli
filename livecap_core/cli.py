"""Minimal CLI utilities for validating a LiveCap Core installation."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from .config.defaults import get_default_config
from .config.validator import ConfigValidator, ValidationError
from .i18n import I18nDiagnostics, diagnose as diagnose_i18n
from .resources import (
    get_ffmpeg_manager,
    get_model_manager,
    get_resource_locator,
)

__all__ = ["DiagnosticReport", "diagnose", "main"]


@dataclass
class DiagnosticReport:
    """Simple diagnostic payload returned by the CLI."""

    config_valid: bool
    config_errors: list[str]
    models_root: str
    cache_root: str
    ffmpeg_path: str | None
    resource_root: str | None
    i18n: I18nDiagnostics

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def _validate_config(config: Dict[str, Any]) -> tuple[bool, list[str]]:
    errors = ConfigValidator.validate(config)
    return (not errors, [f"{err.path}: {err.message}" for err in errors])


def _ensure_ffmpeg(ensure: bool) -> str | None:
    manager = get_ffmpeg_manager()
    if ensure:
        return str(manager.ensure_executable())
    try:
        return str(manager.resolve_executable())
    except Exception:
        return None


def diagnose(
    *,
    ensure_ffmpeg: bool = False,
    config: Optional[Dict[str, Any]] = None,
) -> DiagnosticReport:
    """Programmatic entry point mirroring the CLI behaviour."""
    config = config or get_default_config()
    valid, error_messages = _validate_config(config)

    model_manager = get_model_manager()
    resource_locator = get_resource_locator()

    try:
        resolved_root = str(resource_locator.resolve("."))
    except FileNotFoundError:
        resolved_root = None

    return DiagnosticReport(
        config_valid=valid,
        config_errors=error_messages,
        models_root=str(model_manager.models_root),
        cache_root=str(model_manager.cache_root),
        ffmpeg_path=_ensure_ffmpeg(ensure_ffmpeg),
        resource_root=resolved_root,
        i18n=diagnose_i18n(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="livecap-core",
        description="Inspect and validate a LiveCap Core installation.",
    )
    parser.add_argument(
        "--dump-config",
        action="store_true",
        help="Print the default configuration dictionary as JSON.",
    )
    parser.add_argument(
        "--ensure-ffmpeg",
        action="store_true",
        help="Attempt to download or locate an FFmpeg binary when not already available.",
    )
    parser.add_argument(
        "--as-json",
        action="store_true",
        help="Emit the diagnostic report as JSON for automation.",
    )
    args = parser.parse_args(argv)

    config = get_default_config()
    report = diagnose(ensure_ffmpeg=args.ensure_ffmpeg, config=config)

    if args.dump_config:
        print(json.dumps(config, ensure_ascii=False, indent=2))

    if args.as_json:
        print(report.to_json())
    else:
        print("LiveCap Core diagnostics:")
        print(f"  Config valid: {'yes' if report.config_valid else 'no'}")
        if report.config_errors:
            for message in report.config_errors:
                print(f"    - {message}")
        print(f"  Models root: {report.models_root}")
        print(f"  Cache root: {report.cache_root}")
        print(f"  FFmpeg path: {report.ffmpeg_path or 'not detected'}")
        translator = report.i18n.translator
        if translator.registered:
            extras = f" extras={','.join(translator.extras)}" if translator.extras else ""
            name = translator.name or "translator"
            print(f"  Translator: {name}{extras}")
        else:
            print("  Translator: not registered (fallback only)")
        if report.i18n.fallback_count:
            print(f"  i18n fallback keys: {report.i18n.fallback_count} registered")
        else:
            print("  i18n fallback keys: none registered")

    return 0 if report.config_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
