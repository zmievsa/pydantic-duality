<p align="center">
<a href="https://github.com/zmievsa/pydantic-duality/actions?query=workflow%3ATests+event%3Apush+branch%3Amain" target="_blank">
    <img src="https://github.com/zmievsa/pydantic-duality/actions/workflows/test.yaml/badge.svg?branch=main&event=push" alt="Test">
</a>
<a href="https://codecov.io/gh/zmievsa/pydantic-duality" target="_blank">
    <img src="https://img.shields.io/codecov/c/github/zmievsa/pydantic-duality?color=%2334D058" alt="Coverage">
</a>
<a href="https://pypi.org/project/pydantic-duality/" target="_blank">
    <img alt="PyPI" src="https://img.shields.io/pypi/v/pydantic-duality?color=%2334D058&label=pypi%20package" alt="Package version">
</a>
<a href="https://pypi.org/project/pydantic-duality/" target="_blank">
    <img src="https://img.shields.io/pypi/pyversions/pydantic-duality?color=%2334D058" alt="Supported Python versions">
</a>
</p>

---

## Use cases

### Good API design

In API design, it is a good pattern to forbid any extra data from being sent to your endpoints. By default, pydantic just ignores extra data in FastAPI requests. You can fix that by passing `extra = Extra.forbid` to your model's config. However, we needed to use Extra.ignore in our response models because we might send a lot more data than required with our responses. But then we get into the following conundrum:

```python
class User(BaseModel):
    id: UUID
    name: str


class AuthResponse(BaseModel):
    some_field: str
    user: User


class AuthRequest(SomeResponse, extra=Extra.forbid):
    pass
```

Now you have a problem: even though `SomeRequest` is `Extra.forbid`, `User` is not. It means that your clients can still pass the following payload without any issues:

```json
{
    "some_field": "value",
    "user": {"id": "e65014c9-4990-4b8d-8ce7-ab5a34ab41bc", "name": "Ovsyanka", "hello": "world"}
}
```

The easiest way to solve this is to have `UserRequest` and `UserResponse`, and duplicate this field in your models:

```python
class UserResponse(BaseModel):
    id: UUID
    name: str


class UserRequest(UserResponse, extra=Extra.forbid):
    pass


class AuthResponse(BaseModel):
    some_field: str
    user: UserResponse


class AuthRequest(SomeResponse, extra=Extra.forbid):
    user: UserRequest
```

Now imagine that users also have the field named "address" that points to some `Address` model. Essentially nearly all of your models will need to be duplicated in a similar manner, leading to almost twice as much code.

When we faced this conundrum, we already had an enormous code base so the duplication solution would be a tad too expensive.

Pydantic Duality does this code duplication for you in an intuitive manner automatically. Here's how the models above would look if we used it:

```python
from pydantic_duality import DualBaseModel

class User(DualBaseModel):
    id: UUID
    name: str


class Auth(DualBaseModel):
    some_field: str
    user: User
```

You would use the models above as follows:

```python
Auth.__request__.parse_object(
    {
        "some_field": "value",
        "user": {"id": "e65014c9-4990-4b8d-8ce7-ab5a34ab41bc", "name": "Ovsyanka"}
    }
)

Auth.__response__.parse_object(
    {
        "some_field": "value",
        "user": {"id": "e65014c9-4990-4b8d-8ce7-ab5a34ab41bc", "name": "Ovsyanka", "hello": "world"}
    }
)
```

### PATCH request models

Whenever you make PATCH requests, the simplest and generally accepted API design is to have the same model as for your POST request:

```python
from pydantic import BaseModel


class UserRequest(BaseModel, extra="forbid"):
    name: str
    age: int


class UserPatchRequest(BaseModel, extra="forbid"):
    name: str | None
    age: int | None
```

Think what happens when you have hundreds of these models and tens of fields in each model. The burden of synchronizing patch schemas with post schemas is large, the chance of accidental mistake is high.

Pydantic Duality generates such schemas for you automatically:

```python
from pydantic_duality import DualBaseModel


class User(DualBaseModel):
    name: str
    age: int

UserPatchRequest = User.__patch_request__
```

Thus, you get all the benefits of patch schemas without writing any of them by hand.

## Usage

### Creation

Models are created in the exact same manner as pydantic models but you use our `DualBaseModel` as base instead of `BaseModel`.

```python
from pydantic_duality import DualBaseModel

class User(DualBaseModel):
    id: UUID
    name: str


class Auth(DualBaseModel):
    some_field: str
    user: User
```

If you wish to provide your own base config for all of your models, you can do:

```python
from pydantic_duality import generate_dual_base_model

# Any configuration options you like
class MyConfig:
    orm_mode = True
    ...


DualBaseModel = generate_dual_base_model(MyConfig)
```

### Parsing

#### Default

Whenever you do not want to use Pydantic Duality's features, you can use your models as if they were regular pydantic models. For example:

```python
class User(DualBaseModel):
    id: UUID
    name: str


user = User(id="e65014c9-4990-4b8d-8ce7-ab5a34ab41bc", name="Ovsyanka")
print(user.dict())
```

This is possible because `User` is nearly equivalent to `User.__request__`. It has all the same fields, operations, and hash value. issubclass and isinstance checks will also show that instances of `User.__request__` are also instances of `User`. It is, however, important to realize that `User is not User.__request__`, it just tries to be as similar as possible.

#### Advanced

If you need to use `__response__` version or both versions of your model, you can do so through `__request__` and `__response__` attributes. They will give you an identical model with only the difference that `__request__` has Extra.forbid and `__response__` has Extra.ignore.

```python
class User(DualBaseModel):
    id: str
    name: str


User.__request__(id="e65014c9", name="John", hello="world") # ValidationError
User.__response__(id="e65014c9", name="John", hello="world") # UserResponse(id="e65014c9", name="John")
User.__patch_request__(id="e65014c9") # UserResponse(id="e65014c9", name=None)
```

### Customizing schema names

If you need to customize the names of your model's alternatives (`__request__`, `__response__`, etc), you can pass `request_suffix`, `response_suffix`, and/or `patch_request_suffix` during model creation:

```python
class User(DualBaseModel, request_suffix="ForbidVersion", response_suffix="IgnoreVersion"):
    id: str
    name: str

print(User.__request__.__name__) # UserForbidVersion
print(User.__response__.__name__) # UserIgnoreVersion
```

These attributes will also be inherited by all child models:

```python
class UserWithAge(User):
    age: int


print(UserWithAge.__request__.__name__) # UserWithAgeForbidVersion
print(UserWithAge.__response__.__name__) # UserWithAgeIgnoreVersion
```

### FastAPI integration

Pydantic Duality works with FastAPI out of the box. Note, however, that if you want to use Extra.ignore schemas for responses, you have to specify it explicitly with `response_model=MyModel.__response__`. Otherwise the Extra.forbid schema will be used.

### Configuration override

If you specify extra=Extra.forbid or extra=Extra.ignore on your model explicitly, then Pydantic Duality will not change its or its children's extra configuration. Nested models will still be affected as you might expect.

### Editor support

This package is fully type hinted. mypy, pyright, and pycharm will detect that `__response__` and `__request__` attributes are equivalent to your model so you have full full editor support for them.

`__patch_request__` is not well supported: pyright and mypy will still think that the model's attributes are non-nullable.
