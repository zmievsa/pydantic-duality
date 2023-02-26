import importlib.metadata
import inspect
from collections.abc import Iterable
from types import GenericAlias, UnionType
from typing import Annotated, ClassVar, Union, get_args, get_origin

from pydantic import BaseConfig, BaseModel, Extra
from pydantic.main import ModelMetaclass
from typing_extensions import Self

__version__ = importlib.metadata.version("pydantic_duality")

REQUEST_ATTR = "__request__"
RESPONSE_ATTR = "__response__"
AnnotatedType = type(Annotated[int, int])


def _resolve_annotation(annotation, attr: str):
    if inspect.isclass(annotation) and isinstance(annotation, ModelDuplicatorMeta):
        return getattr(annotation, attr)
    elif isinstance(annotation, GenericAlias):
        return GenericAlias(
            get_origin(annotation),
            tuple(_resolve_annotation(a, attr) for a in get_args(annotation)),
        )
    elif isinstance(annotation, UnionType):
        return Union.__getitem__(tuple(_resolve_annotation(a, attr) for a in annotation.__args__))
    elif isinstance(annotation, AnnotatedType):
        return Annotated.__class_getitem__(
            tuple(
                [
                    *[_resolve_annotation(a, attr) for a in annotation.__args__],
                    *[_resolve_annotation(a, attr) for a in annotation.__metadata__],
                ]
            ),
        )
    elif inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        return annotation
    else:
        return annotation


def _alter_attrs(attrs: dict[str, object], attr: str):
    attrs = attrs.copy()
    if "__qualname__" in attrs:
        if attr == RESPONSE_ATTR:
            attrs["__qualname__"] = attrs["__qualname__"] + "Response"
        else:
            attrs["__qualname__"] = attrs["__qualname__"] + "Request"
    if "__annotations__" in attrs:
        annotations = attrs["__annotations__"].copy()
        for key, val in annotations.items():
            annotations[key] = _resolve_annotation(val, attr)
        attrs["__annotations__"] = annotations
    return attrs


class ModelDuplicatorMeta(ModelMetaclass):
    def __new__(mcls, name: str, bases: tuple[type], attrs: dict[str, object], **kwargs):
        new_class = type.__new__(mcls, name, bases, attrs)
        if not bases or not any(isinstance(b, (ModelMetaclass, ModelDuplicatorMeta)) for b in bases):
            raise TypeError(
                f"ModelDuplicatorMeta's instances must be created with a ConfigMixin base class or a BaseModel base class."
            )
        # ConfigMixin case
        elif bases == (BaseModel,):
            if "__config__" not in kwargs:
                raise TypeError(
                    f"The first instance of {mcls.__name__} must pass a __config__ argument into the __new__ method."
                )

            __config__ = kwargs["__config__"]

            class BaseRequest(BaseModel):
                class Config(__config__):
                    extra = Extra.forbid

            class BaseResponse(BaseModel):
                class Config(__config__):
                    extra = Extra.ignore

            new_class.__request__ = BaseRequest
            new_class.__response__ = BaseResponse
            return new_class

        request_bases = tuple(_resolve_annotation(b, REQUEST_ATTR) for b in bases)
        response_bases = tuple(_resolve_annotation(b, RESPONSE_ATTR) for b in bases)

        request_class = ModelMetaclass(f"{name}Request", request_bases, _alter_attrs(attrs, REQUEST_ATTR), **kwargs)
        response_class = ModelMetaclass(
            f"{name}Response",
            response_bases,
            _alter_attrs(attrs, RESPONSE_ATTR),
            **kwargs,
        )

        type.__setattr__(new_class, REQUEST_ATTR, request_class)
        type.__setattr__(new_class, RESPONSE_ATTR, response_class)

        type.__setattr__(request_class, REQUEST_ATTR, request_class)
        type.__setattr__(request_class, RESPONSE_ATTR, response_class)

        type.__setattr__(response_class, REQUEST_ATTR, request_class)
        type.__setattr__(response_class, RESPONSE_ATTR, response_class)

        return new_class

    def __getattribute__(self, attr: str):
        if attr in (REQUEST_ATTR, RESPONSE_ATTR, "__new__"):
            return type.__getattribute__(self, attr)
        return getattr(type.__getattribute__(self, REQUEST_ATTR), attr)

    def __dir__(self) -> Iterable[str]:
        return set(super().__dir__()) | set(dir(getattr(self, REQUEST_ATTR)))

    def __eq__(self, __o: object) -> bool:
        if isinstance(__o, ModelDuplicatorMeta):
            return super().__eq__(__o)
        else:
            return self.__request__ == __o

    def __hash__(self) -> int:
        return hash(self.__request__)

    def __instancecheck__(cls, instance) -> None:
        return type.__instancecheck__(cls, instance) or isinstance(instance, cls.__request__)

    def __subclasscheck__(cls, subclass: type):
        return type.__subclasscheck__(cls, subclass) or issubclass(subclass, cls.__request__)


class ConfigMixin(BaseModel, metaclass=ModelDuplicatorMeta, __config__=BaseConfig):
    __response__: ClassVar[type[Self]]
    __request__: ClassVar[type[Self]]

    def __new__(cls, *args, **kwargs) -> Self:
        return cls.__request__(*args, **kwargs)

    def __init_subclass__(cls, **kwargs) -> None:
        return object.__init_subclass__()


def generate_config_mixin(base_config) -> type[ConfigMixin]:
    class ConfigMixin(BaseModel, metaclass=ModelDuplicatorMeta, __config__=base_config):
        __response__: ClassVar[type[Self]]
        __request__: ClassVar[type[Self]]

        def __new__(cls, *args, **kwargs):
            return cls.__request__(*args, **kwargs)

        def __init_subclass__(cls, **kwargs) -> None:
            return object.__init_subclass__()

    return ConfigMixin
