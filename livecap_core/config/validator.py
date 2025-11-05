"""Lightweight configuration validation utilities for the core layer."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC, MutableMapping as MutableMappingABC, Sequence as SequenceABC
from dataclasses import dataclass
try:
    from types import UnionType
except ImportError:  # pragma: no cover - Python < 3.10
    UnionType = None  # type: ignore[assignment]
from typing import Any, Dict, List, Mapping, Union, get_args, get_origin, Literal, ForwardRef
try:  # Python 3.11+
    from typing import _eval_type  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    _eval_type = None  # type: ignore

from . import schema as schema_module
from .schema import CoreConfig


@dataclass(frozen=True)
class ValidationError:
    """Represents a single configuration validation failure."""

    path: str
    message: str


class ConfigValidator:
    """Validate minimal requirements for running the core layer."""

    _ROOT_SCHEMA = CoreConfig

    @classmethod
    def validate(cls, config: Mapping[str, Any]) -> List[ValidationError]:
        """Validate a configuration dictionary and return a list of errors."""
        if not isinstance(config, MappingABC):
            return [
                ValidationError(
                    path="<root>",
                    message="Expected a mapping for the configuration root",
                )
            ]
        return cls._validate_typed_dict(config, cls._ROOT_SCHEMA, path="")

    @classmethod
    def validate_or_raise(cls, config: Mapping[str, Any]) -> None:
        """Validate the configuration and raise ValueError on failure."""
        errors = cls.validate(config)
        if errors:
            details = "\n".join(f"- {err.path}: {err.message}" for err in errors)
            raise ValueError(f"Configuration validation failed:\n{details}")

    # Internal helpers -----------------------------------------------------

    @classmethod
    def _validate_typed_dict(
        cls,
        value: Mapping[str, Any],
        schema: type[dict],
        path: str,
    ) -> List[ValidationError]:
        errors: List[ValidationError] = []

        if not isinstance(value, MappingABC):
            errors.append(
                ValidationError(
                    path=path or "<root>",
                    message=f"Expected mapping compatible with {schema.__name__}",
                )
            )
            return errors

        annotations = cls._collect_annotations(schema)
        required_keys = getattr(schema, "__required_keys__", frozenset())

        for key in sorted(required_keys):
            if key not in value:
                errors.append(
                    ValidationError(
                        path=cls._join(path, key),
                        message="Required key is missing",
                    )
                )

        for key in sorted(value.keys()):
            annotation = annotations.get(key)
            if annotation is None:
                errors.append(
                    ValidationError(
                        path=cls._join(path, key),
                        message=f"Unexpected key for {schema.__name__}",
                    )
                )
                continue
            sub_value = value[key]
            errors.extend(
                cls._validate_annotation(
                    sub_value,
                    annotation,
                    path=cls._join(path, key),
                )
            )

        return errors

    @classmethod
    def _validate_annotation(cls, value: Any, annotation: Any, path: str) -> List[ValidationError]:
        if annotation is Any:
            return []

        if not cls._matches_type(value, annotation):
            expected = cls._describe_annotation(annotation)
            actual = type(value).__name__
            return [
                ValidationError(
                    path=path or "<root>",
                    message=f"Expected {expected}, got {actual}",
                )
            ]

        return cls._descend(value, annotation, path)

    @classmethod
    def _descend(cls, value: Any, annotation: Any, path: str) -> List[ValidationError]:
        if isinstance(annotation, ForwardRef):
            resolved = cls._resolve_forward_ref(annotation)
            if resolved is None:
                return []
            annotation = resolved

        origin = get_origin(annotation)

        if cls._is_union(annotation):
            for option in get_args(annotation):
                if cls._matches_type(value, option):
                    return cls._descend(value, option, path)
            return []

        if cls._is_typed_dict(annotation):
            return cls._validate_typed_dict(value, annotation, path)

        if origin is Literal:
            return []

        if origin in cls._SEQUENCE_ORIGINS:
            type_args = get_args(annotation)
            if not type_args:
                return []
            element_annotation = type_args[0]
            errors: List[ValidationError] = []
            for index, item in enumerate(value):
                element_path = f"{path}[{index}]"
                errors.extend(cls._validate_annotation(item, element_annotation, element_path))
            return errors

        if origin in cls._MAPPING_ORIGINS:
            key_annotation, value_annotation = cls._mapping_args(annotation)
            errors: List[ValidationError] = []

            if key_annotation is not Any:
                for key in value.keys():
                    if not cls._matches_type(key, key_annotation):
                        expected = cls._describe_annotation(key_annotation)
                        errors.append(
                            ValidationError(
                                path=path or "<root>",
                                message=f"Invalid key '{key}' (expected {expected})",
                            )
                        )

            if value_annotation is not Any:
                for key, item in value.items():
                    item_path = cls._join(path, str(key))
                    errors.extend(cls._validate_annotation(item, value_annotation, item_path))

            return errors

        return []

    @classmethod
    def _matches_type(cls, value: Any, annotation: Any) -> bool:
        if annotation is Any:
            return True

        if isinstance(annotation, ForwardRef):
            resolved = cls._resolve_forward_ref(annotation)
            if resolved is not None:
                return cls._matches_type(value, resolved)

        if annotation is type(None):
            return value is None

        if cls._is_union(annotation):
            return any(cls._matches_type(value, option) for option in get_args(annotation))

        if cls._is_typed_dict(annotation):
            return isinstance(value, MappingABC)

        origin = get_origin(annotation)

        if origin is Literal:
            return value in get_args(annotation)

        if origin in cls._SEQUENCE_ORIGINS:
            return isinstance(value, SequenceABC) and not isinstance(value, (str, bytes, bytearray))

        if origin in cls._MAPPING_ORIGINS:
            return isinstance(value, MappingABC)

        if isinstance(annotation, type):
            if annotation is float:
                return isinstance(value, (int, float)) and not isinstance(value, bool)
            if annotation is int:
                return isinstance(value, int) and not isinstance(value, bool)
            return isinstance(value, annotation)

        return True

    @staticmethod
    def _resolve_forward_ref(ref: ForwardRef) -> Any | None:
        if _eval_type is None:
            return None
        try:
            return _eval_type(ref, vars(schema_module), vars(schema_module))
        except Exception:
            return None

    @staticmethod
    def _collect_annotations(schema: type[dict]) -> Dict[str, Any]:
        annotations: Dict[str, Any] = {}
        for base in reversed(schema.__mro__):
            annotations.update(getattr(base, "__annotations__", {}))
        return annotations

    @staticmethod
    def _join(path: str, key: str) -> str:
        return key if not path else f"{path}.{key}"

    @classmethod
    def _is_typed_dict(cls, annotation: Any) -> bool:
        return isinstance(annotation, type) and issubclass(annotation, dict) and hasattr(annotation, "__required_keys__")

    @classmethod
    def _is_union(cls, annotation: Any) -> bool:
        origin = get_origin(annotation)
        if origin is None:
            return False
        if origin is Union:
            return True
        return UnionType is not None and origin is UnionType

    @classmethod
    def _mapping_args(cls, annotation: Any) -> tuple[Any, Any]:
        args = get_args(annotation)
        if len(args) == 2:
            return args[0], args[1]
        return Any, Any

    @classmethod
    def _describe_annotation(cls, annotation: Any) -> str:
        if annotation is Any:
            return "any type"
        if isinstance(annotation, ForwardRef):
            resolved = cls._resolve_forward_ref(annotation)
            if resolved is not None:
                return cls._describe_annotation(resolved)
            return f"ForwardRef({annotation.__forward_arg__})"
        if cls._is_union(annotation):
            options = " | ".join(cls._describe_annotation(opt) for opt in get_args(annotation))
            return f"({options})"
        if cls._is_typed_dict(annotation):
            return f"{annotation.__name__} structure"
        origin = get_origin(annotation)
        if origin is Literal:
            values = ", ".join(repr(arg) for arg in get_args(annotation))
            return f"literal ({values})"
        if origin in cls._SEQUENCE_ORIGINS:
            args = get_args(annotation)
            if args:
                return f"sequence of {cls._describe_annotation(args[0])}"
            return "sequence"
        if origin in cls._MAPPING_ORIGINS:
            key_ann, value_ann = cls._mapping_args(annotation)
            return f"mapping[{cls._describe_annotation(key_ann)} -> {cls._describe_annotation(value_ann)}]"
        if isinstance(annotation, type):
            return annotation.__name__
        return str(annotation)

    _SEQUENCE_ORIGINS = {
        list,
        tuple,
        SequenceABC,
    }

    _MAPPING_ORIGINS = {
        dict,
        MappingABC,
        MutableMappingABC,
    }
