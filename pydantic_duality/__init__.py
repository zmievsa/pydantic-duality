import copy
import importlib.metadata
import inspect
import sys
from types import GenericAlias
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    List,
    Literal,
    Mapping,
    Optional,
    Tuple,
    Type,
    Union,
    get_args,
    get_origin,
)

from cached_classproperty import cached_classproperty
from isort import Config
from pydantic import BaseConfig, BaseModel, ConfigDict, Field
from pydantic._internal._model_construction import ModelMetaclass
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined
from typing_extensions import Annotated, Iterable, Self, dataclass_transform

if sys.version_info > (3, 13):
    annotated_class_getitem = Annotated.__getitem__
else:
    annotated_class_getitem = Annotated.__class_getitem__


__version__ = importlib.metadata.version("pydantic_duality")

REQUEST_ATTR = "__request__"
RESPONSE_ATTR = "__response__"
PATCH_REQUEST_ATTR = "__patch_request__"


def _replace_with_or_none(val: Any) -> Any:
    if (
        isinstance(val, FieldInfo) and val.default is PydanticUndefined
    ):  # pragma: no cover
        val = copy.deepcopy(val)
        val.default = None
    else:
        return val


def _resolve_annotation(annotation, attr: str) -> Any:
    if inspect.isclass(annotation) and isinstance(annotation, DualBaseModelMeta):
        return getattr(annotation, attr)
    if get_origin(annotation) is Annotated:
        return annotated_class_getitem(
            tuple(_resolve_annotation(a, attr) for a in get_args(annotation)),
        )

    if isinstance(annotation, GenericAlias):
        return GenericAlias(
            get_origin(annotation),
            tuple(_resolve_annotation(a, attr) for a in get_args(annotation)),
        )
    if inspect.isclass(annotation) and isinstance(annotation, ModelMetaclass):
        return annotation
    if get_origin(annotation) is Union:
        return Union.__getitem__(
            tuple(_resolve_annotation(a, attr) for a in get_args(annotation))
        )
    if get_origin(annotation) is list:
        return List.__getitem__(
            tuple(_resolve_annotation(a, attr) for a in get_args(annotation))
        )
    return annotation


def _alter_attrs(attrs: Dict[str, object], name: str, suffix: str, attr: str):
    attrs = attrs.copy()

    if "__qualname__" in attrs:
        attrs["__qualname__"] = attrs["__qualname__"] + suffix
    if "Config" in attrs and inspect.isclass(attrs["Config"]):
        attrs["Config"].__qualname__ = attrs["__qualname__"] + ".Config"
    if "__annotations__" in attrs and isinstance(attrs["__annotations__"], dict):
        annotations = attrs["__annotations__"].copy()
        for key, val in annotations.items():
            annotations[key] = _resolve_annotation(val, attr)
            if attr == PATCH_REQUEST_ATTR:
                if get_origin(annotations[key]) is Annotated:
                    args = get_args(annotations[key])
                    annotations[key] = annotated_class_getitem(
                        tuple([Optional[args[0]], *args[1:]])
                    )
                elif isinstance(annotations[key], str):
                    annotations[key] = f"Optional[{annotations[key]}]"
                elif get_origin(annotations[key]) == Literal:
                    if len(get_args(annotations[key])) == 1:
                        attrs[key] = get_args(annotations[key])[0]
                    else:
                        annotations[key] = Optional[annotations[key]]
                else:
                    annotations[key] = Optional[annotations[key]]
        attrs["__annotations__"] = annotations
    return attrs


def _lazily_initalize_models(
    request_cls: type, own_attr_name: str, constructor: Callable[[], Any]
):
    def constructor_wrapper(*a, **kw) -> object:
        obj = constructor()
        obj.__request__ = request_cls
        obj.__response__ = cached_classproperty(
            lambda cls: request_cls.__response__, RESPONSE_ATTR
        )
        obj.__patch_request__ = cached_classproperty(
            lambda cls: request_cls.__patch_request__, PATCH_REQUEST_ATTR
        )
        return obj

    return cached_classproperty(constructor_wrapper, own_attr_name)


@dataclass_transform(kw_only_default=True, field_specifiers=(Field, FieldInfo))
class DualBaseModelMeta(ModelMetaclass):
    __request__: Self
    __response__: Self
    __patch_request__: Self

    def __new__(
        self,
        name: str,
        bases: Tuple[type],
        attrs: Dict[str, object],
        *,
        request_suffix: Optional[str] = None,
        response_suffix: Optional[str] = None,
        patch_request_suffix: Optional[str] = None,
        **kwargs,
    ) -> Self:
        new_class = type.__new__(self, name, bases, attrs)
        if not bases or not any(
            isinstance(b, (ModelMetaclass, DualBaseModelMeta)) for b in bases
        ):
            raise TypeError(
                f"ModelDuplicatorMeta's instances must be created with a DualBaseModel base class or a BaseModel base class."
            )
        # DualBaseModel case
        elif bases == (BaseModel,):
            if "model_config" not in attrs:
                raise TypeError(
                    f"The first instance of {self.__name__} must have a model_config attribute."
                )
            elif not isinstance(attrs["model_config"], dict):
                raise TypeError("The model_config attribute must be a dictionary.")
            elif (
                request_suffix is None
                or response_suffix is None
                or patch_request_suffix is None
            ):
                raise TypeError(
                    "The first instance of DualBaseModel must pass suffixes for the request, response, and patch request models."
                )
            new_class._generate_base_alternative_classes(
                request_suffix,
                response_suffix,
                kwargs,
                attrs,
            )
        else:
            request_suffix, response_suffix, patch_request_suffix = (
                request_suffix or new_class.request_suffix,
                response_suffix or new_class.response_suffix,
                patch_request_suffix or new_class.patch_request_suffix,
            )
            new_class._generate_alternative_classes(
                name,
                bases,
                attrs,
                request_suffix,
                response_suffix,
                patch_request_suffix,
                kwargs,
            )

        new_class.__request__.request_suffix = request_suffix  # type: ignore
        new_class.__request__.response_suffix = response_suffix  # type: ignore
        new_class.__request__.patch_request_suffix = patch_request_suffix  # type: ignore

        return new_class

    def _generate_base_alternative_classes(
        self,
        request_suffix,
        response_suffix,
        kwargs,
        attrs,
    ):
        model_config = {**attrs["model_config"], **ConfigDict(extra="forbid")}

        BaseRequest = ModelMetaclass(
            f"Base{request_suffix}", (BaseModel,), {"model_config": model_config}
        )

        model_config = {**attrs["model_config"], **ConfigDict(extra="ignore")}

        BaseResponse = ModelMetaclass(
            f"Base{response_suffix}", (BaseModel,), {"model_config": model_config}
        )

        type.__setattr__(self, "__request__", BaseRequest)
        BaseRequest.__request__ = BaseRequest  # type: ignore
        BaseRequest.__response__ = BaseResponse  # type: ignore
        BaseRequest.__patch_request__ = BaseRequest  # type: ignore

    def _generate_alternative_classes(
        self,
        name,
        bases,
        attrs,
        request_suffix,
        response_suffix,
        patch_request_suffix,
        kwargs,
    ):
        request_bases = tuple(_resolve_annotation(b, REQUEST_ATTR) for b in bases)
        request_kwargs = kwargs.copy()
        if "extra" in request_kwargs:
            request_kwargs["extra"] = "forbid"
        request_class = ModelMetaclass(
            name + request_suffix,
            request_bases,
            _alter_attrs(attrs, name, request_suffix, REQUEST_ATTR),
            **request_kwargs,
        )
        request_class.__response__ = _lazily_initalize_models(
            request_class,
            RESPONSE_ATTR,
            lambda: ModelMetaclass(
                name + response_suffix,
                tuple(_resolve_annotation(b, RESPONSE_ATTR) for b in bases),
                _alter_attrs(attrs, name, response_suffix, RESPONSE_ATTR),
                **kwargs,
            ),
        )
        patch_attrs: dict[str, Any] = {
            key: _replace_with_or_none(val)
            if key in request_class.model_fields
            else val
            for key, val in attrs.items()
        }
        if "__annotations__" in attrs and isinstance(attrs["__annotations__"], dict):
            patch_attrs |= {
                key: None
                for key in attrs["__annotations__"]
                if key not in patch_attrs and key in request_class.model_fields
            }
        request_class.__patch_request__ = _lazily_initalize_models(
            request_class,
            PATCH_REQUEST_ATTR,
            lambda: ModelMetaclass(
                name + patch_request_suffix,
                tuple(_resolve_annotation(b, PATCH_REQUEST_ATTR) for b in bases),
                _alter_attrs(
                    patch_attrs, name, patch_request_suffix, PATCH_REQUEST_ATTR
                ),
                **request_kwargs,
            ),
        )
        type.__setattr__(self, REQUEST_ATTR, request_class)
        return request_class

    def __getattribute__(self, attr: str):
        # Note here that RESPONSE_ATTR and PATCH_REQUEST_ATTR goes into REQUEST_ATTR's __getattribute__ method
        if attr in {
            REQUEST_ATTR,
            "__new__",
            "_generate_base_alternative_classes",
            "_generate_alternative_classes",
        }:
            return type.__getattribute__(self, attr)
        return getattr(type.__getattribute__(self, REQUEST_ATTR), attr)

    def __setattr__(self, attr: str, value: object):
        return setattr(type.__getattribute__(self, REQUEST_ATTR), attr, value)

    def __dir__(self) -> Iterable[str]:
        return set(super().__dir__()).union(set(dir(getattr(self, REQUEST_ATTR))))

    def __eq__(self, __o: object) -> bool:
        if isinstance(__o, DualBaseModelMeta):
            return super().__eq__(__o)
        else:
            return self.__request__ == __o

    def __hash__(self) -> int:
        return hash(self.__request__)

    def __instancecheck__(cls, instance) -> bool:
        return type.__instancecheck__(cls, instance) or isinstance(
            instance, (cls.__request__, cls.__response__, cls.__patch_request__)
        )

    def __subclasscheck__(cls, subclass: type):
        return type.__subclasscheck__(cls, subclass) or issubclass(
            subclass, (cls.__request__, cls.__response__, cls.__patch_request__)
        )


def generate_dual_base_model(
    base_config: Union[ConfigDict, None] = None,
    response_suffix="Response",
    request_suffix="Request",
    patch_request_suffix="PatchRequest",
) -> "Type[DualBaseModel]":
    if base_config is None:  # pragma: no branch
        base_config = ConfigDict()

    class DualBaseModel(
        BaseModel,
        metaclass=DualBaseModelMeta,
        request_suffix=request_suffix,
        response_suffix=response_suffix,
        patch_request_suffix=patch_request_suffix,
    ):
        model_config = base_config
        __response__: ClassVar[Type[Self]]
        __request__: ClassVar[Type[Self]]
        __patch_request__: ClassVar[Type[Self]]

        request_suffix: ClassVar[str]
        response_sufx: ClassVar[str]
        patch_request_suffix: ClassVar[str]

        def __new__(cls, *args, **kwargs):
            return cls.__request__(*args, **kwargs)

        def __init_subclass__(cls, **kwargs) -> None:
            return object.__init_subclass__()

    return DualBaseModel


if TYPE_CHECKING:

    class DualBaseModel(BaseModel, metaclass=DualBaseModelMeta):
        __request__: ClassVar[Type[Self]]
        __response__: ClassVar[Type[Self]]
        __patch_request__: ClassVar[Type[Self]]

        request_suffix: ClassVar[str]
        response_sufx: ClassVar[str]
        patch_request_suffix: ClassVar[str]

else:
    DualBaseModel = generate_dual_base_model()
