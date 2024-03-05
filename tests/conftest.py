import sys
from typing import List, Optional
import pytest

from pydantic_duality import DualBaseModel, generate_dual_base_model


@pytest.fixture(params=[True, False])
def schemas(request):
    if request.param:
        Base = generate_dual_base_model(object)
    else:
        Base = DualBaseModel

    class E(Base):
        e: str

    class D(Base):
        grand: str

    class C(D, E):
        friend: str

    class G(Base):
        g: str

    class H(Base):
        h: str

    if sys.version_info >= (3, 10):
        class B(Base):
            my: str
            old: list[C]
            right: "str | None"

        class A(Base):
            hello: str
            darkness: B
    else:
        class B(Base):
            my: str
            old: List[C]
            right: Optional["str"]

        class A(Base):
            hello: str
            darkness: B

    return locals()
