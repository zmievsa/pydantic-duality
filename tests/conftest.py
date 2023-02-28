import pytest

from pydantic_duality import ConfigMixin, generate_config_mixin


@pytest.fixture(params=[True, False])
def schemas(request):
    if request.param:
        Base = generate_config_mixin(object)
    else:
        Base = ConfigMixin

    class E(Base):
        e: str

    class D(Base):
        grand: str

    class C(D, E):
        friend: str

    class B(Base):
        my: str
        old: list[C]
        right: "str | None"

    class G(Base):
        g: str

    class H(Base):
        h: str

    class A(Base):
        hello: str
        darkness: B

    return locals()
