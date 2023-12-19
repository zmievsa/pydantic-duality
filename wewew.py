from pydantic import BaseModel
import datetime as dt


class A(BaseModel):
    a: dt.date
    b: dt.datetime


A.parse_obj({"a": dt.datetime.now(), "b": dt.datetime.now()})
