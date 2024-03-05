from pydantic import ConfigDict, Field
import pytest

from pydantic_duality import DualBaseModel, generate_dual_base_model


@pytest.fixture(params=[True, False])
def schemas(request):
    if request.param:
        Base = generate_dual_base_model(ConfigDict())
    else:
        Base = DualBaseModel

    class E(Base):
        e: str

    class D(Base):
        grand: str

    class C(D, E):
        friend: str

    class B(Base):
        my: str
        old: list[C]
        right: "str | None" = Field(default=None)

    class G(Base):
        g: str

    class H(Base):
        h: str

    class A(Base):
        hello: str
        darkness: B

    return locals()
