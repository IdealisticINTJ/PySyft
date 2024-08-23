# stdlib
import base64
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
import json
from typing import Any
from typing import Generic
from typing import TypeVar
from typing import Union
from typing import get_args
from typing import get_origin

# third party
import pydantic

# syft absolute
import syft as sy

# relative
from ..server.credentials import SyftSigningKey
from ..server.credentials import SyftVerifyKey
from ..types.datetime import DateTime
from ..types.syft_object import BaseDateTime
from ..types.syft_object_registry import SyftObjectRegistry
from ..types.uid import LineageID
from ..types.uid import UID

T = TypeVar("T")

JSON_CANONICAL_NAME_FIELD = "__canonical_name__"
JSON_VERSION_FIELD = "__version__"
JSON_DATA_FIELD = "data"


Json = str | int | float | bool | None | list["Json"] | dict[str, "Json"]


@dataclass
class JSONSerde(Generic[T]):
    # TODO add json schema
    klass: type[T]
    serialize_fn: Callable[[T], Json] | None = None
    deserialize_fn: Callable[[Json], T] | None = None

    def serialize(self, obj: T) -> Json:
        if self.serialize_fn is None:
            return obj  # type: ignore
        else:
            return self.serialize_fn(obj)

    def deserialize(self, obj: Json) -> T:
        if self.deserialize_fn is None:
            return obj  # type: ignore
        return self.deserialize_fn(obj)


JSON_SERDE_REGISTRY: dict[type[T], JSONSerde[T]] = {}


def register_json_serde(
    type_: type[T],
    serialize: Callable[[T], Json] | None = None,
    deserialize: Callable[[Json], T] | None = None,
) -> None:
    if type_ in JSON_SERDE_REGISTRY:
        raise ValueError(f"Type {type_} is already registered")

    JSON_SERDE_REGISTRY[(type_)] = JSONSerde(
        klass=type_,
        serialize_fn=serialize,
        deserialize_fn=deserialize,
    )


# Standard JSON primitives
register_json_serde(int)
register_json_serde(str)
register_json_serde(bool)
register_json_serde(float)
register_json_serde(type(None))
register_json_serde(pydantic.EmailStr)

# Syft primitives
register_json_serde(UID, lambda uid: uid.no_dash, lambda s: UID(s))
register_json_serde(LineageID, lambda uid: uid.no_dash, lambda s: LineageID(s))
register_json_serde(
    DateTime, lambda dt: dt.utc_timestamp, lambda f: DateTime(utc_timestamp=f)
)
register_json_serde(
    BaseDateTime, lambda dt: dt.utc_timestamp, lambda f: BaseDateTime(utc_timestamp=f)
)
register_json_serde(SyftVerifyKey, lambda key: str(key), SyftVerifyKey.from_string)
register_json_serde(SyftSigningKey, lambda key: str(key), SyftSigningKey.from_string)


def _validate_json(value: T) -> T:
    # Throws TypeError if value is not JSON-serializable
    json.dumps(value)
    return value


def _is_optional_annotation(annotation: Any) -> Any:
    return annotation | None == annotation


def _get_nonoptional_annotation(annotation: Any) -> Any:
    """Return the type anntation with None type removed, if it is present.

    Args:
        annotation (Any): type annotation

    Returns:
        Any: type annotation without None type
    """
    if _is_optional_annotation(annotation):
        args = get_args(annotation)
        return Union[tuple(arg for arg in args if arg is not type(None))]  # noqa
    return annotation


def _annotation_issubclass(annotation: Any, cls: type) -> bool:
    # issubclass throws TypeError if annotation is not a valid type (eg Union)
    try:
        return issubclass(annotation, cls)
    except TypeError:
        return False


def _serialize_pydantic_to_json(obj: pydantic.BaseModel) -> dict[str, Json]:
    canonical_name, version = SyftObjectRegistry.get_canonical_name_version(obj)
    result: dict[str, Json] = {
        JSON_CANONICAL_NAME_FIELD: canonical_name,
        JSON_VERSION_FIELD: version,
    }

    for key, type_ in obj.model_fields.items():
        result[key] = serialize_json(getattr(obj, key), type_.annotation)

    result = _serialize_searchable_attrs(obj, result)

    return result


def get_property_return_type(obj: Any, attr_name: str) -> Any:
    """
    Get the return type annotation of a @property.
    """
    cls = type(obj)
    attr = getattr(cls, attr_name, None)

    if isinstance(attr, property):
        return attr.fget.__annotations__.get("return", None)

    return None


def _serialize_searchable_attrs(
    obj: pydantic.BaseModel, obj_dict: dict[str, Json], raise_errors: bool = True
) -> dict[str, Json]:
    """
    Add searchable attrs to the serialized object dict, if they are not already present.
    Needed for adding non-field attributes (like @property)

    Args:
        obj (pydantic.BaseModel): Object to serialize.
        obj_dict (dict[str, Json]): Serialized object dict. Should contain the object's fields.
        raise_errors (bool, optional): Raise errors if an attribute cannot be accessed.
            If False, the attribute will be skipped. Defaults to True.

    Raises:
        Exception: Any exception raised when accessing an attribute.

    Returns:
        dict[str, Json]: Serialized object dict including searchable attributes.
    """
    searchable_attrs: list[str] = getattr(obj, "__attr_searchable__", [])
    for attr in searchable_attrs:
        if attr not in obj_dict:
            try:
                value = getattr(obj, attr)
            except Exception as e:
                if raise_errors:
                    raise e
                else:
                    continue
            property_annotation = get_property_return_type(obj, attr)
            obj_dict[attr] = serialize_json(
                value, validate=False, annotation=property_annotation
            )

    return obj_dict


def _deserialize_pydantic_from_json(
    obj_dict: dict[str, Json],
) -> pydantic.BaseModel:
    try:
        canonical_name = obj_dict[JSON_CANONICAL_NAME_FIELD]
        version = obj_dict[JSON_VERSION_FIELD]
        obj_type = SyftObjectRegistry.get_serde_class(canonical_name, version)

        result = {}
        for key, type_ in obj_type.model_fields.items():
            result[key] = deserialize_json(obj_dict[key], type_.annotation)

        return obj_type.model_validate(result)
    except Exception as e:
        print(json.dumps(obj_dict, indent=2))
        raise ValueError(f"Failed to deserialize Pydantic model: {e}")


def _is_serializable_iterable(annotation: Any) -> bool:
    # we can only serialize typed iterables without Union/Any
    # NOTE optional is allowed

    # 1. check if it is an iterable
    if get_origin(annotation) not in {list, tuple, set, frozenset}:
        return False

    # 2. check if iterable annotation is serializable
    args = get_args(annotation)
    if len(args) != 1:
        return False

    inner_type = _get_nonoptional_annotation(args[0])
    return inner_type in JSON_SERDE_REGISTRY or _annotation_issubclass(
        inner_type, pydantic.BaseModel
    )


def _serialize_iterable_to_json(value: Any, annotation: Any) -> Json:
    # No need to validate in recursive calls
    return [serialize_json(v, validate=False) for v in value]


def _deserialize_iterable_from_json(value: Json, annotation: Any) -> Any:
    if not isinstance(value, list):
        raise ValueError(f"Cannot deserialize {type(value)} to {annotation}")

    annotation = _get_nonoptional_annotation(annotation)

    if not _is_serializable_iterable(annotation):
        raise ValueError(f"Cannot deserialize {annotation} from JSON")

    inner_type = _get_nonoptional_annotation(get_args(annotation)[0])
    return [deserialize_json(v, inner_type) for v in value]


def _is_serializable_mapping(annotation: Any) -> bool:
    """
    Mapping is serializable if:
    - it is a dict
    - the key type is str
    - the value type is serializable and not a Union
    """
    if get_origin(annotation) != dict:
        return False

    args = get_args(annotation)
    if len(args) != 2:
        return False

    key_type, value_type = args
    # JSON only allows string keys
    if not isinstance(key_type, str):
        return False

    # check if value type is serializable
    value_type = _get_nonoptional_annotation(value_type)
    return value_type in JSON_SERDE_REGISTRY or _annotation_issubclass(
        value_type, pydantic.BaseModel
    )


def _serialize_mapping_to_json(value: Any, annotation: Any) -> Json:
    _, value_type = get_args(annotation)
    # No need to validate in recursive calls
    return {k: serialize_json(v, value_type, validate=False) for k, v in value.items()}


def _deserialize_mapping_from_json(value: Json, annotation: Any) -> Any:
    if not isinstance(value, dict):
        raise ValueError(f"Cannot deserialize {type(value)} to {annotation}")

    annotation = _get_nonoptional_annotation(annotation)

    if not _is_serializable_mapping(annotation):
        raise ValueError(f"Cannot deserialize {annotation} from JSON")

    _, value_type = get_args(annotation)
    return {k: deserialize_json(v, value_type) for k, v in value.items()}


def _serialize_to_json_bytes(obj: Any) -> str:
    obj_bytes = sy.serialize(obj, to_bytes=True)
    return base64.b64encode(obj_bytes).decode("utf-8")


def _deserialize_from_json_bytes(obj: str) -> Any:
    obj_bytes = base64.b64decode(obj)
    return sy.deserialize(obj_bytes, from_bytes=True)


def serialize_json(value: Any, annotation: Any = None, validate: bool = True) -> Json:
    """
    Serialize a value to a JSON-serializable object, using the schema defined by the
    provided annotation.

    Serialization is always done according to the annotation, as the same annotation
    is used for deserialization. If the annotation is not provided or is ambiguous,
    the JSON serialization will fall back to serializing bytes. Examples:
    - int, `list[int]` are strictly typed
    - `str | int`, `list`, `list[str | int]`, `list[Any]` are ambiguous and serialized to bytes
    - Optional types (like int | None) are serialized to the not-None type

    The function chooses the appropriate serialization method in the following order:
    1. Method registered in `JSON_SERDE_REGISTRY` for the annotation type.
    2. Pydantic model serialization, including all `SyftObjects`.
    3. Iterable serialization, if the annotation is a strict iterable (e.g., `list[int]`).
    4. Mapping serialization, if the annotation is a strictly typed mapping with string keys.
    5. Serialize the object to bytes and encode it as base64.

    Args:
        value (Any): Value to serialize.
        annotation (Any, optional): Type annotation for the value. Defaults to None.

    Returns:
        Json: JSON-serializable object.
    """
    if annotation is None:
        annotation = type(value)

    if value is None:
        return None

    # Remove None type from annotation if it is present.
    annotation = _get_nonoptional_annotation(annotation)

    if annotation in JSON_SERDE_REGISTRY:
        result = JSON_SERDE_REGISTRY[annotation].serialize(value)
    elif _annotation_issubclass(annotation, pydantic.BaseModel):
        result = _serialize_pydantic_to_json(value)
    elif _annotation_issubclass(annotation, Enum):
        result = value.name

    # JSON recursive types
    # only strictly annotated iterables and mappings are supported
    # example: list[int] is supported, but not list[int | str]
    elif _is_serializable_iterable(annotation):
        result = _serialize_iterable_to_json(value, annotation)
    elif _is_serializable_mapping(annotation):
        result = _serialize_mapping_to_json(value, annotation)
    else:
        result = _serialize_to_json_bytes(value)

    if validate:
        _validate_json(result)

    return result


def deserialize_json(value: Json, annotation: Any = None) -> Any:
    """Deserialize a JSON-serializable object to a value, using the schema defined by the
    provided annotation. Inverse of `serialize_json`.

    Args:
        value (Json): JSON-serializable object.
        annotation (Any): Type annotation for the value.

    Returns:
        Any: Deserialized value.
    """
    if (
        isinstance(value, dict)
        and JSON_CANONICAL_NAME_FIELD in value
        and JSON_VERSION_FIELD in value
    ):
        return _deserialize_pydantic_from_json(value)

    if value is None:
        return None

    # Remove None type from annotation if it is present.
    annotation = _get_nonoptional_annotation(annotation)

    if annotation in JSON_SERDE_REGISTRY:
        return JSON_SERDE_REGISTRY[annotation].deserialize(value)
    elif _annotation_issubclass(annotation, pydantic.BaseModel):
        return _deserialize_pydantic_from_json(value)
    elif _annotation_issubclass(annotation, Enum):
        return annotation[value]
    elif isinstance(value, list):
        return _deserialize_iterable_from_json(value, annotation)
    elif isinstance(value, dict):
        return _deserialize_mapping_from_json(value, annotation)
    elif isinstance(value, str):
        return _deserialize_from_json_bytes(value)
    else:
        raise ValueError(f"Cannot deserialize {value} to {annotation}")
