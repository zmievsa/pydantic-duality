# pydantic-duality

Automatically generate two versions of your pydantic models: one with Extra.forbid and one with Extra.ignore

## Installation

```bash
pip install pydantic-duality
```

## Use case

### Problem

In API design, it is a good pattern to forbid any extra data from being sent to your endpoints. By default, pydantic just ignores extra data in FastAPI requests. You can fix that by passing `extra = Extra.forbid` to your model's config. But then you get into the following conundrum:

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

### Solution

pydantic-duality does this code duplication for you in an intuitive manner automatically. Here's how the models above would look if we used it:

```python
from pydantic_duality import ConfigMixin

class User(ConfigMixin):
    id: UUID
    name: str


class Auth(ConfigMixin):
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

## Usage

### Creation

Models are created in the exact same manner as pydantic models but you use our `ConfigMixin` as base instead of `BaseModel`.

```python
from pydantic_duality import ConfigMixin

class User(ConfigMixin):
    id: UUID
    name: str


class Auth(ConfigMixin):
    some_field: str
    user: User
```

If you wish to provide your own base config for all of your models, you can do:

```python
from pydantic_duality import generate_config_mixin

# Any configuration options you like
class MyConfig:
    orm_mode = True
    ...


ConfigMixin = generate_config_mixin(MyConfig)
```

### Parsing

#### Default

Whenever you do not want to use pydantic-duality's features, you can use your models as if they were regular pydantic models. For example:

```python

class User(ConfigMixin):
    id: UUID
    name: str


user = User(id="e65014c9-4990-4b8d-8ce7-ab5a34ab41bc", name="Ovsyanka")
print(user.dict())
```

This is possible because `User` is nearly equivalent to `User.__request__`. It has all the same fields, operations, and hash value. issubclass and isinstance checks will also show that instances of `User.__request__` are also instances of `User`. It is, however, important to realize that `User is not User.__request__`, it just tries to be as similar as possible.

#### Advanced

If you need to use `__response__` version or both versions of your model, you can do so through `__request__` and `__response__` attributes. They will give you an identical model with only the difference that `__request__` has Extra.forbid and `__response__` has Extra.ignore.

```python

class User(ConfigMixin):
    id: UUID
    name: str


User.__request__(id="e65014c9-4990-4b8d-8ce7-ab5a34ab41bc", name="Ovsyanka", hello="world") # ValidationError
User.__response__(id="e65014c9-4990-4b8d-8ce7-ab5a34ab41bc", name="Ovsyanka", hello="world") # UserResponse object without "hello" field
```

### FastAPI integration

pydantic-duality works with FastAPI out of the box. Note, however, that if you want to use Extra.ignore schemas for responses, you have to specify it explicitly with `response_model=MyModel.__response__`. Otherwise the Extra.forbid schema will be used.

### Configuration override

If you specify extra=Extra.forbid or extra=Extra.ignore on your model explicitly, then pydantic-duality will not change its or its children's extra configuration. Nested models will still be affected as you might expect.

### Editor support

This package is fully type hinted. mypy, pyright, and pycharm will detect that `__response__` and `__request__` attributes are equivalent to your model so you have full full editor support.
