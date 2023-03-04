import importlib.metadata
import inspect
from collections.abc import Iterable
from types import GenericAlias, UnionType
from typing import Annotated, Any, Callable, ClassVar, Union, get_args, get_origin

from cached_classproperty import cached_classproperty
from pydantic import BaseConfig, BaseModel, Extra, Field
from pydantic.fields import FieldInfo
from pydantic.main import ModelMetaclass
from typing_extensions import Self, dataclass_transform

__version__ = importlib.metadata.version("pydantic_duality")

REQUEST_ATTR = "__request__"
RESPONSE_ATTR = "__response__"
PATCH_REQUEST_ATTR = "__patch_request__"


def _resolve_annotation(annotation, attr: str) -> Any:
    if inspect.isclass(annotation) and isinstance(annotation, ModelDuplicatorMeta):
        return getattr(annotation, attr)
    elif isinstance(annotation, GenericAlias):
        return GenericAlias(
            get_origin(annotation),
            tuple(_resolve_annotation(a, attr) for a in get_args(annotation)),
        )
    elif isinstance(annotation, UnionType):
        return Union.__getitem__(tuple(_resolve_annotation(a, attr) for a in get_args(annotation)))
    elif get_origin(annotation) is Annotated:
        return Annotated.__class_getitem__(
            tuple(_resolve_annotation(a, attr) for a in get_args(annotation)),
        )
    elif inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        return annotation
    else:
        return annotation


def _alter_attrs(attrs: dict[str, object], name: str, attr: str):
    attrs = attrs.copy()
    if "__qualname__" in attrs:
        attrs["__qualname__"] = name
    if "__annotations__" in attrs:
        annotations = attrs["__annotations__"].copy()
        for key, val in annotations.items():
            annotations[key] = _resolve_annotation(val, attr)
            if attr == PATCH_REQUEST_ATTR:
                if get_origin(annotations[key]) is Annotated:
                    args = get_args(annotations[key])
                    annotations[key] = Annotated.__class_getitem__(tuple([args[0] | None, *args[1:]]))
                elif isinstance(annotations[key], str):
                    annotations[key] += " | None"
                else:
                    annotations[key] = annotations[key] | None
        attrs["__annotations__"] = annotations
    return attrs


def _lazily_initalize_models(request_cls: type, own_attr_name: str, constructor: Callable[[], Any]):
    def constructor_wrapper(*a, **kw) -> object:
        obj = constructor()
        obj.__request__ = request_cls
        obj.__response__ = cached_classproperty(lambda cls: request_cls.__response__, RESPONSE_ATTR)
        obj.__patch_request__ = cached_classproperty(lambda cls: request_cls.__patch_request__, PATCH_REQUEST_ATTR)
        return obj

    return cached_classproperty(constructor_wrapper, own_attr_name)


@dataclass_transform(kw_only_default=True, field_specifiers=(Field, FieldInfo))
class ModelDuplicatorMeta(ModelMetaclass):
    __request__: Self
    __response__: Self
    __patch_request__: Self

    def __new__(mcls, name: str, bases: tuple[type], attrs: dict[str, object], **kwargs) -> Self:
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

            type.__setattr__(new_class, "__request__", BaseRequest)
            BaseRequest.__request__ = BaseRequest  # type: ignore
            BaseRequest.__response__ = BaseResponse  # type: ignore
            BaseRequest.__patch_request__ = BaseRequest  # type: ignore
            return new_class

        request_bases = tuple(_resolve_annotation(b, REQUEST_ATTR) for b in bases)

        request_class = ModelMetaclass(
            f"{name}Request",
            request_bases,
            _alter_attrs(attrs, f"{name}Request", REQUEST_ATTR),
            **kwargs,
        )
        request_class.__response__ = _lazily_initalize_models(
            request_class,
            RESPONSE_ATTR,
            lambda: ModelMetaclass(
                f"{name}Response",
                tuple(_resolve_annotation(b, RESPONSE_ATTR) for b in bases),
                _alter_attrs(attrs, f"{name}Response", RESPONSE_ATTR),
                **kwargs,
            ),
        )
        request_class.__patch_request__ = _lazily_initalize_models(
            request_class,
            PATCH_REQUEST_ATTR,
            lambda: ModelMetaclass(
                f"{name}PatchRequest",
                tuple(_resolve_annotation(b, PATCH_REQUEST_ATTR) for b in bases),
                _alter_attrs(attrs, f"{name}PatchRequest", PATCH_REQUEST_ATTR),
                **kwargs,
            ),
        )

        type.__setattr__(new_class, REQUEST_ATTR, request_class)

        return new_class

    def __getattribute__(self, attr: str):
        # Note here that RESPONSE_ATTR goes into REQUEST_ATTR's __getattribute__ method
        if attr in (REQUEST_ATTR, "__new__"):
            return type.__getattribute__(self, attr)
        return getattr(type.__getattribute__(self, REQUEST_ATTR), attr)

    def __setattr__(self, attr: str, value: object):
        return setattr(type.__getattribute__(self, REQUEST_ATTR), attr, value)

    def __dir__(self) -> Iterable[str]:
        return set(super().__dir__()) | set(dir(getattr(self, REQUEST_ATTR)))

    def __eq__(self, __o: object) -> bool:
        if isinstance(__o, ModelDuplicatorMeta):
            return super().__eq__(__o)
        else:
            return self.__request__ == __o

    def __hash__(self) -> int:
        return hash(self.__request__)

    def __instancecheck__(cls, instance) -> bool:
        return type.__instancecheck__(cls, instance) or isinstance(instance, cls.__request__)

    def __subclasscheck__(cls, subclass: type):
        return type.__subclasscheck__(cls, subclass) or issubclass(subclass, cls.__request__)


class ConfigMixin(BaseModel, metaclass=ModelDuplicatorMeta, __config__=BaseConfig):
    __response__: ClassVar[type[Self]]
    __request__: ClassVar[type[Self]]
    __patch_request__: ClassVar[type[Self]]

    def __new__(cls, *args, **kwargs) -> Self:
        return cls.__request__(*args, **kwargs)

    def __init_subclass__(cls, **kwargs) -> None:
        return object.__init_subclass__()


def generate_config_mixin(base_config) -> type[ConfigMixin]:
    class ConfigMixin(BaseModel, metaclass=ModelDuplicatorMeta, __config__=base_config):
        __response__: ClassVar[type[Self]]
        __request__: ClassVar[type[Self]]
        __patch_request__: ClassVar[type[Self]]

        def __new__(cls, *args, **kwargs):
            return cls.__request__(*args, **kwargs)

        def __init_subclass__(cls, **kwargs) -> None:
            return object.__init_subclass__()

    return ConfigMixin
