import abc
from typing import Annotated, Literal

import pytest
from pydantic import BaseConfig, BaseModel, Extra, Field, ValidationError

from pydantic_duality import ConfigMixin, ModelDuplicatorMeta, _resolve_annotation


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

    class BaseModelSchema(ConfigMixin):
        model: Request

    assert BaseModelSchema(model=dict(r="r")).model.r == "r"
    with pytest.raises(ValidationError):
        BaseModelSchema.__response__(model=dict(r="r", extra="extra"))

    BaseModelSchema.__response__(model=dict(r="r"), extra="extra")


def test_annotationless_class():
    class Nothing(ConfigMixin):
        pass

    Nothing()
    with pytest.raises(ValidationError):
        Nothing.__request__(extra="extra")
    with pytest.raises(ValidationError):
        Nothing(extra="extra")


def test_dir():
    class Schema(ConfigMixin):
        s: str

    assert "parse_obj" in dir(Schema)
    assert "update_forward_refs" in dir(Schema)


def test_lack_of_config_for_base_class():
    with pytest.raises(TypeError):

        class Schema(BaseModel, metaclass=ModelDuplicatorMeta):
            pass


def test_lack_of_base_class():
    with pytest.raises(TypeError):

        class Schema(metaclass=ModelDuplicatorMeta):
            pass


def test_invalid_base_class():
    with pytest.raises(TypeError):

        class Schema(abc.ABC, metaclass=ModelDuplicatorMeta):
            pass


def test_issubclass(schemas):
    assert issubclass(schemas["A"], BaseModel)
    assert issubclass(schemas["A"].__request__, BaseModel)
    assert issubclass(schemas["A"].__response__, BaseModel)


def test_ignore_forbid_attrs(schemas):
    assert (
        schemas["A"].__request__.__response__.__response__.__request__.__request__.__request__.Config.extra
        == Extra.forbid
    )
    assert (
        schemas["A"].__request__.__response__.__response__.__request__.__request__.__response__.Config.extra
        == Extra.ignore
    )


def test_resolving(schemas):
    _resolve_annotation(Annotated[schemas["A"] | schemas["B"], Field(discriminator="object_type")], "__request__")


def test_model_creation(schemas):
    print(
        schemas["A"].__response__.parse_obj(
            {
                "hello": "world",
                "darkness": {"my": "...", "old": [{"friend": "s", "extra": "s", "grand": "d", "e": "e"}]},
            }
        )
    )
    with pytest.raises(ValidationError):
        schemas["A"].parse_obj(
            {
                "hello": "world",
                "darkness": {"my": "...", "old": [{"friend": "s", "extra": "s", "grand": "d", "e": "e"}]},
            }
        )


def test_annotated_model_creation_with_discriminator():
    class ChildSchema1(ConfigMixin):
        object_type: Literal[1]
        obj: str

    class ChildSchema2(ConfigMixin):
        object_type: Literal[2]
        obj: str

    class Schema(ConfigMixin):
        child: Annotated[ChildSchema1 | ChildSchema2, Field(discriminator="object_type")]

    for object_type in (1, 2):
        child_schema = Schema.parse_obj({"child": {"object_type": object_type, "obj": object_type}})
        child_req_schema = Schema.__request__.parse_obj({"child": {"object_type": object_type, "obj": object_type}})
        child_resp_schema = Schema.__response__.parse_obj({"child": {"object_type": object_type, "obj": object_type}})

        assert type(child_schema.child) is locals()[f"ChildSchema{object_type}"].__request__
        assert type(child_req_schema.child) is locals()[f"ChildSchema{object_type}"].__request__
        assert type(child_resp_schema.child) is locals()[f"ChildSchema{object_type}"].__response__
        with pytest.raises(ValidationError):
            Schema.parse_obj({"child": {"object_type": object_type, "obj": object_type, "extra": "extra"}})
        with pytest.raises(ValidationError):
            Schema.__request__.parse_obj({"child": {"object_type": object_type, "obj": object_type, "extra": "extra"}})
        Schema.__response__.parse_obj({"child": {"object_type": object_type, "obj": object_type, "extra": "extra"}})


@pytest.mark.parametrize("field_type", [Annotated[int, "Hello"], Annotated[int, "Hello", "Darkness"]])
def test_annotated_model_creation_with_regular_metadata(field_type):
    class Schema(ConfigMixin):
        field: field_type

    assert Schema.__fields__["field"].annotation is field_type
    assert Schema.__request__.__fields__["field"].annotation is field_type
    assert Schema.__response__.__fields__["field"].annotation is field_type


def test_eq():
    class Schema(ConfigMixin):
        field: int

    class Schema2(ConfigMixin):
        field: int

    assert Schema.__request__ == Schema
    assert Schema.__response__ != Schema
    assert Schema.__request__ != Schema.__response__

    assert Schema != Schema2


def test_hash():
    class Schema(ConfigMixin):
        field: int

    assert hash(Schema.__request__) == hash(Schema)


def test_set_items():
    class Schema(ConfigMixin):
        field: int

    assert {Schema, Schema.__request__} == {Schema}
    assert {Schema, Schema.__request__, Schema.__response__} == {Schema.__request__, Schema.__response__}


def test_fastapi_weird_lack_of_qualname():
    # No error should be raised even though neither __annotations__ nor __qualname__ are present
    type(ConfigMixin)("SomeModel", (ConfigMixin,), {})
