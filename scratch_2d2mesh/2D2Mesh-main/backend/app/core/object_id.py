"""Pydantic-compatible ObjectId type bridging MongoDB and the API layer."""
from __future__ import annotations

from typing import Any

from bson import ObjectId
from pydantic_core import core_schema


class PyObjectId(str):
    """A bson ObjectId that serializes cleanly through Pydantic."""

    @classmethod
    def __get_pydantic_core_schema__(cls, _source: Any, _handler: Any) -> core_schema.CoreSchema:

        return core_schema.no_info_plain_validator_function(
            cls.validate,
            serialization=core_schema.plain_serializer_function_ser_schema(lambda v: str(v)),
        )

    @classmethod
    def validate(cls, value: Any) -> "PyObjectId":
        if isinstance(value, ObjectId):
            return cls(str(value))
        if isinstance(value, str) and ObjectId.is_valid(value):
            return cls(value)
        raise ValueError("Invalid ObjectId")

    @classmethod
    def from_str(cls, value: str) -> "PyObjectId":
        if not ObjectId.is_valid(value):
            raise ValueError(f"'{value}' is not a valid ObjectId")
        return cls(value)


def to_object_id(value: str | ObjectId) -> ObjectId:
    if isinstance(value, ObjectId):
        return value
    if not ObjectId.is_valid(value):
        raise ValueError(f"'{value}' is not a valid ObjectId")
    return ObjectId(value)


def make_object_id() -> PyObjectId:
    """Generate a fresh, valid ObjectId wrapper for `default_factory` defaults."""
    return PyObjectId(str(ObjectId()))
