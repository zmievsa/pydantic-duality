
<p align="center">
  <a href="https://ovsyanka83.github.io/pydantic-duality/"><img src="https://raw.githubusercontent.com/Ovsyanka83/pydantic-duality/main/docs/_media/logo_with_text.svg" alt="Pydantic Duality"></a>
</p>
<p align="center">
  <b>Automatically and lazily generate three versions of your pydantic models: one with Extra.forbid, one with Extra.ignore, and one with all fields optional</b>
</p>

---

<p align="center">
<a href="https://github.com/ovsyanka83/pydantic-duality/actions?query=workflow%3ATests+event%3Apush+branch%3Amain" target="_blank">
    <img src="https://github.com/Ovsyanka83/pydantic-duality/actions/workflows/test.yaml/badge.svg?branch=main&event=push" alt="Test">
</a>
<a href="https://codecov.io/gh/ovsyanka83/pydantic-duality" target="_blank">
    <img src="https://img.shields.io/codecov/c/github/ovsyanka83/pydantic-duality?color=%2334D058" alt="Coverage">
</a>
<a href="https://pypi.org/project/pydantic-duality/" target="_blank">
    <img alt="PyPI" src="https://img.shields.io/pypi/v/pydantic-duality?color=%2334D058&label=pypi%20package" alt="Package version">
</a>
<a href="https://pypi.org/project/pydantic-duality/" target="_blank">
    <img src="https://img.shields.io/pypi/pyversions/pydantic-duality?color=%2334D058" alt="Supported Python versions">
</a>
</p>

## Installation

```bash
pip install pydantic-duality
```

## Quickstart

Given the following models:

```python

from pydantic_duality import DualBaseModel


class User(DualBaseModel):
    id: UUID
    name: str

class Auth(DualBaseModel):
    some_field: str
    user: User
```

Using pydantic-duality is roughly equivalent to making all of the following models by hand:

```python

from pydantic import BaseModel

# Equivalent to User and User.__request__
class UserRequest(BaseModel, extra=Extra.forbid):
    id: UUID
    name: str

# Rougly equivalent to Auth and Auth.__request__
class AuthRequest(BaseModel, extra=Extra.forbid):
    some_field: str
    user: UserRequest


# Rougly equivalent to User.__response__
class UserResponse(BaseModel, extra=Extra.ignore):
    id: UUID
    name: str

# Rougly equivalent to Auth.__response__
class AuthResponse(BaseModel, extra=Extra.ignore):
    some_field: str
    user: UserResponse


# Rougly equivalent to User.__patch_request__
class UserPatchRequest(BaseModel, extra=Extra.forbid):
    id: UUID | None
    name: str | None

# Rougly equivalent to Auth.__patch_request__
class AuthPatchRequest(BaseModel, extra=Extra.forbid):
    some_field: str | None
    user: UserPatchRequest | None

```

So it takes you up to 3 times less code to write the same thing. Note also that pydantic-duality does everything lazily so you will not notice any significant performance or memory usage difference when using it instead of writing everything by hand. Think of it as using all the customized models as cached properties.

Inheritance, inner models, custom configs, [custom names](https://ovsyanka83.github.io/pydantic-duality/#/?id=customizing-schema-names), config kwargs, isinstance and subclass checks work intuitively and in the same manner as they would work if you were not using pydantic-duality.

## Help

See [documentation](https://ovsyanka83.github.io/pydantic-duality/#/) for more details
