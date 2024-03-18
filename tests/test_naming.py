from typing import Dict

import pytest
from pydantic import BaseModel

from pydantic_duality import DualBaseModel, DualBaseModelMeta

overrides = pytest.mark.parametrize(
    "overrides",
    [
        {"request_suffix": "RequestSuffix"},
        {"response_suffix": "ResponseSuffix"},
        {"patch_request_suffix": "PatchRequestSuffix"},
        {
            "request_suffix": "MyRequestSuffix",
            "response_suffix": "MyResponseSuffix",
            "patch_request_suffix": "MyPatchRequestSuffix",
        },
    ],
)


def test_default_name():
    class Schema(DualBaseModel):
        pass

    assert Schema.__request__.__name__ == "SchemaRequest"
    assert Schema.__response__.__name__ == "SchemaResponse"
    assert Schema.__patch_request__.__name__ == "SchemaPatchRequest"


def test_inheritance():
    class Schema(DualBaseModel):
        pass

    class SubSchema(Schema):
        pass

    assert SubSchema.__request__.__name__ == "SubSchemaRequest"
    assert SubSchema.__response__.__name__ == "SubSchemaResponse"
    assert SubSchema.__patch_request__.__name__ == "SubSchemaPatchRequest"


@overrides
def test_name_overrides(overrides: Dict[str, str]):
    class Schema(DualBaseModel, **overrides):
        pass

    if "request_suffix" in overrides:
        assert Schema.__request__.__name__ == "Schema" + overrides["request_suffix"]
    if "response_suffix" in overrides:
        assert Schema.__response__.__name__ == "Schema" + overrides["response_suffix"]
    if "patch_request_suffix" in overrides:
        assert Schema.__patch_request__.__name__ == "Schema" + overrides["patch_request_suffix"]


@overrides
def test_name_overrides_level1_inheritance(overrides: Dict[str, str]):
    class Schema(DualBaseModel, **overrides):
        pass

    class SubSchema(Schema):
        pass

    if "request_suffix" in overrides:
        assert SubSchema.__request__.__name__ == "SubSchema" + overrides["request_suffix"]
    if "response_suffix" in overrides:
        assert SubSchema.__response__.__name__ == "SubSchema" + overrides["response_suffix"]
    if "patch_request_suffix" in overrides:
        assert SubSchema.__patch_request__.__name__ == "SubSchema" + overrides["patch_request_suffix"]


@overrides
def test_name_overrides_level2_inheritance(overrides: Dict[str, str]):
    class Schema(DualBaseModel):
        pass

    class SubSchema(Schema, **overrides):
        pass

    class SubSubSchema(SubSchema):
        pass

    assert Schema.__request__.__name__ == "SchemaRequest"
    assert Schema.__response__.__name__ == "SchemaResponse"
    assert Schema.__patch_request__.__name__ == "SchemaPatchRequest"

    if "request_suffix" in overrides:
        assert SubSchema.__request__.__name__ == "SubSchema" + overrides["request_suffix"]
        assert SubSubSchema.__request__.__name__ == "SubSubSchema" + overrides["request_suffix"]
    if "response_suffix" in overrides:
        assert SubSchema.__response__.__name__ == "SubSchema" + overrides["response_suffix"]
        assert SubSubSchema.__response__.__name__ == "SubSubSchema" + overrides["response_suffix"]
    if "patch_request_suffix" in overrides:
        assert SubSchema.__patch_request__.__name__ == "SubSchema" + overrides["patch_request_suffix"]
        assert SubSubSchema.__patch_request__.__name__ == "SubSubSchema" + overrides["patch_request_suffix"]


@overrides
def test_lack_of_suffix_for_base_class(overrides: Dict[str, str]):
    if "request_suffix" in overrides and "response_suffix" in overrides and "patch_request_suffix" in overrides:
        return
    with pytest.raises(
        TypeError,
        match=(
            "The first instance of DualBaseModel must pass suffixes for the "
            "request, response, and patch request models."
        ),
    ):

        class Schema(BaseModel, metaclass=DualBaseModelMeta, __config__=DualBaseModel.__config__, **overrides):
            pass
