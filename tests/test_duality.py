import abc
from typing import Annotated, Literal, get_args

import pytest
from pydantic import BaseModel, ConfigDict, Extra, Field, ValidationError

from pydantic_duality import DualBaseModel, DualBaseModelMeta, _resolve_annotation


def test_new(schemas):
    assert schemas["H"](h="h").h == "h"


def test_union(schemas):
    class UnionSchema(schemas["Base"]):
        model: schemas["G"] | schemas["H"]

    g = UnionSchema(model=dict(g="g")).model
    h = UnionSchema.__request__(model=dict(h="h")).model
    assert g.g == "g"
    assert h.h == "h"


def test_base_model():
    class Request(BaseModel, extra=Extra.forbid):
        r: str

    class BaseModelSchema(DualBaseModel):
        model: Request

    assert BaseModelSchema(model=dict(r="r")).model.r == "r"
    with pytest.raises(ValidationError):
        BaseModelSchema.__response__(model=dict(r="r", extra="extra"))

    BaseModelSchema.__response__(model=dict(r="r"), extra="extra")


def test_annotationless_class():
    class Nothing(DualBaseModel):
        pass

    Nothing()
    with pytest.raises(ValidationError):
        Nothing.__request__(extra="extra")
    with pytest.raises(ValidationError):
        Nothing(extra="extra")


def test_dir():
    class Schema(DualBaseModel):
        s: str

    assert "parse_obj" in dir(Schema)
    assert "update_forward_refs" in dir(Schema)


def test_lack_of_base_class():
    with pytest.raises(
        TypeError,
        match="ModelDuplicatorMeta's instances must be created with a DualBaseModel base class or a BaseModel base class.",
    ):

        class Schema(metaclass=DualBaseModelMeta):
            pass


def test_invalid_base_class():
    with pytest.raises(
        TypeError,
        match="ModelDuplicatorMeta's instances must be created with a DualBaseModel base class or a BaseModel base class.",
    ):

        class Schema(abc.ABC, metaclass=DualBaseModelMeta):
            pass


def test_lack_of_config_in_base_class():
    with pytest.raises(
        TypeError,
        match="The first instance of DualBaseModelMeta must pass a __config__ argument into the __new__ method.",
    ):

        class Schema(
            BaseModel,
            metaclass=DualBaseModelMeta,
            request_suffix="Request",
            response_suffix="Response",
            patch_request_suffix="PatchRequest",
        ):
            ...


@pytest.mark.parametrize("config", ["123", object, None])
def test_wrong_config_type_in_base_class(config: str | object | None):
    with pytest.raises(
        TypeError,
        match="The __config__ argument must be a dict.",
    ):

        class Schema(
            BaseModel,
            metaclass=DualBaseModelMeta,
            __config__=config,
            request_suffix="Request",
            response_suffix="Response",
            patch_request_suffix="PatchRequest",
        ):
            ...


def test_issubclass_basemodel(schemas):
    assert issubclass(schemas["A"], BaseModel)
    assert issubclass(schemas["A"].__request__, BaseModel)
    assert issubclass(schemas["A"].__response__, BaseModel)


def test_issubclass_inner_models():
    class SubSchema(DualBaseModel):
        pass

    assert issubclass(SubSchema.__request__, SubSchema)
    assert not issubclass(SubSchema.__response__, SubSchema)
    assert not issubclass(SubSchema, SubSchema.__response__)
    # assert not issubclass(SubSchema, SubSchema.__request__)  # See test_issubclass_weird_issubclass_error for more details
    assert not issubclass(SubSchema.__response__, SubSchema.__request__)
    assert not issubclass(SubSchema.__request__, SubSchema.__response__)


@pytest.mark.xfail(
    reason="Either I did something incorrectly or there's a bug in pydantic/pytest/CPython. Feels like caching"
)
def test_issubclass_weird_issubclass_error():
    class SubSchema(DualBaseModel):
        pass

    # It fails in this order
    assert issubclass(SubSchema.__request__, SubSchema)
    assert not issubclass(SubSchema, SubSchema.__request__)  # fails here


@pytest.mark.xfail(
    reason="Either I did something incorrectly or there's a bug in pydantic/pytest/CPython. Feels like caching"
)
def test_issubclass_weird_issubclass_error2():
    class SubSchema(DualBaseModel):
        pass

    assert not issubclass(SubSchema, SubSchema.__request__)
    assert issubclass(SubSchema.__request__, SubSchema)  # fails here


def test_ignore_forbid_attrs(schemas):
    assert (
        schemas[
            "A"
        ].__request__.__response__.__response__.__request__.__response__.__request__.model_config[
            "extra"
        ]
        == Extra.forbid
    )
    assert (
        schemas[
            "A"
        ].__request__.__response__.__response__.__request__.__response__.__patch_request__.model_config[
            "extra"
        ]
        == Extra.forbid
    )
    assert (
        schemas[
            "A"
        ].__request__.__response__.__response__.__request__.__response__.__response__.model_config[
            "extra"
        ]
        == Extra.ignore
    )


def test_setattr():
    class Schema(DualBaseModel):
        s: str

    Schema.__name__ = "Hewwo"
    assert Schema.__request__.__name__ == "Hewwo"


def test_resolving(schemas):
    _resolve_annotation(
        Annotated[schemas["A"] | schemas["B"], Field(discriminator="object_type")],
        "__request__",
    )


def test_response_model_creation(schemas):
    schemas["A"].__response__.parse_obj(
        {
            "hello": "world",
            "darkness": {
                "my": "...",
                "old": [{"friend": "s", "extra": "s", "grand": "d", "e": "e"}],
            },
        }
    )


def test_patch_request_model_creation(schemas):
    schemas["A"].__patch_request__.parse_obj(
        {
            "darkness": {
                "old": [{}],
            },
        }
    )


def test_default_model_creation_with_extra__should_use_request_and_fail(schemas):
    with pytest.raises(ValidationError):
        schemas["A"].parse_obj(
            {
                "hello": "world",
                "darkness": {
                    "my": "...",
                    "old": [{"friend": "s", "extra": "s", "grand": "d", "e": "e"}],
                },
            }
        )


def test_annotated_model_creation_with_discriminator():
    class ChildSchema1(DualBaseModel):
        object_type: Literal[1]
        obj: str

    class ChildSchema2(DualBaseModel):
        object_type: Literal[2]
        obj: str

    class Schema(DualBaseModel):
        child: Annotated[
            ChildSchema1 | ChildSchema2, Field(discriminator="object_type")
        ]

    for object_type in (1, 2):
        child_schema = Schema.parse_obj(
            {"child": {"object_type": object_type, "obj": str(object_type)}}
        )
        child_req_schema = Schema.__request__.parse_obj(
            {"child": {"object_type": object_type, "obj": str(object_type)}}
        )
        child_resp_schema = Schema.__response__.parse_obj(
            {"child": {"object_type": object_type, "obj": str(object_type)}}
        )

        assert (
            type(child_schema.child)
            is locals()[f"ChildSchema{object_type}"].__request__
        )
        assert (
            type(child_req_schema.child)
            is locals()[f"ChildSchema{object_type}"].__request__
        )
        assert (
            type(child_resp_schema.child)
            is locals()[f"ChildSchema{object_type}"].__response__
        )
        with pytest.raises(ValidationError):
            Schema.parse_obj(
                {
                    "child": {
                        "object_type": object_type,
                        "obj": object_type,
                        "extra": "extra",
                    }
                }
            )
        with pytest.raises(ValidationError):
            Schema.__request__.parse_obj(
                {
                    "child": {
                        "object_type": object_type,
                        "obj": object_type,
                        "extra": "extra",
                    }
                }
            )
        # TODO: Add matches clause to all validation errors
        with pytest.raises(ValidationError):
            Schema.__patch_request__.parse_obj(
                {
                    "child": {
                        "object_type": object_type,
                        "extra": "extra",
                    }
                }
            )
        Schema.__patch_request__.parse_obj({"child": {"object_type": object_type}})
        Schema.__response__.parse_obj(
            {
                "child": {
                    "object_type": object_type,
                    "obj": str(object_type),
                    "extra": "extra",
                }
            }
        )


@pytest.mark.parametrize(
    "field_type", [Annotated[int, "Hello"], Annotated[int, "Hello", "Darkness"]]
)
def test_annotated_model_creation_with_regular_metadata(field_type):
    class Schema(DualBaseModel):
        field: field_type

    assert get_args(Schema.__annotations__["field"]) == get_args(field_type)
    assert get_args(Schema.__request__.__annotations__["field"]) == get_args(field_type)
    assert get_args(Schema.__response__.__annotations__["field"]) == get_args(
        field_type
    )


def test_eq():
    class Schema(DualBaseModel):
        field: int

    class Schema2(DualBaseModel):
        field: int

    assert Schema.__request__ == Schema
    assert Schema == Schema.__request__
    assert Schema.__response__ != Schema
    assert Schema.__request__ != Schema.__response__

    assert Schema != Schema2


def test_hash():
    class Schema(DualBaseModel):
        field: int

    assert hash(Schema.__request__) == hash(Schema)


def test_set_items():
    class Schema(DualBaseModel):
        field: int

    assert {Schema, Schema.__request__} == {Schema}
    assert {Schema, Schema.__request__, Schema.__response__} == {
        Schema.__request__,
        Schema.__response__,
    }


def test_fastapi_weird_lack_of_qualname():
    # No error should be raised even though neither __annotations__ nor __qualname__ are present
    type(DualBaseModel)("SomeModel", (DualBaseModel,), {})


def test_config_defined_in_model():
    """We check that the config is possible to define and that it overrides the default config"""

    class Schema(DualBaseModel):
        field: int

        model_config = ConfigDict(extra=Extra.ignore)

    assert Schema.__request__.model_config["extra"] == Extra.ignore
    assert Schema.__response__.model_config["extra"] == Extra.ignore
    assert Schema.__patch_request__.model_config["extra"] == Extra.ignore

    Schema(field=1, extra=2)


def test_config_defined_in_kwargs():
    """We check that the config is possible to define and that it overrides the default config"""

    class Schema(DualBaseModel, extra=Extra.ignore):
        field: int

    assert Schema.__request__.model_config["extra"] == Extra.forbid
    assert Schema.__response__.model_config["extra"] == Extra.ignore
    assert Schema.__patch_request__.model_config["extra"] == Extra.forbid

    Schema(field=1, extra=2)
    Schema.__request__(field=1, extra=2)
