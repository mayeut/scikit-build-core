from __future__ import annotations

import ast
import dataclasses
import inspect
import sys
import textwrap
from collections.abc import Generator
from pathlib import Path

from packaging.version import Version

from .._compat.typing import get_args, get_origin

__all__ = ["pull_docs"]


def __dir__() -> list[str]:
    return __all__


def _get_value(value: ast.expr) -> str:
    if sys.version_info < (3, 8):
        assert isinstance(value, ast.Str)
        return value.s

    assert isinstance(value, ast.Constant)
    return value.value


def pull_docs(dc: type[object]) -> dict[str, str]:
    """
    Pulls documentation from a dataclass.
    """
    t = ast.parse(inspect.getsource(dc))
    (obody,) = t.body
    assert isinstance(obody, ast.ClassDef)
    body = obody.body
    return {
        assign.target.id: textwrap.dedent(_get_value(expr.value)).strip().replace("\n", " ")  # type: ignore[union-attr]
        for assign, expr in zip(body[:-1], body[1:])
        if isinstance(assign, ast.AnnAssign) and isinstance(expr, ast.Expr)
    }


@dataclasses.dataclass
class DCDoc:
    name: str
    default: str
    docs: str

    def __str__(self) -> str:
        docs = "\n".join(f"# {s}" for s in textwrap.wrap(self.docs, width=78))
        return f"{docs}\n{self.name} = {self.default}\n"


def mk_docs(dc: type[object], prefix: str = "") -> Generator[DCDoc, None, None]:
    """
    Makes documentation for a dataclass.
    """
    assert dataclasses.is_dataclass(dc)
    docs = pull_docs(dc)

    for field in dataclasses.fields(dc):
        if dataclasses.is_dataclass(field.type):
            yield from mk_docs(field.type, prefix=f"{prefix}{field.name}.")
            continue

        if get_origin(field.type) is list:
            field_type = get_args(field.type)[0]
            if dataclasses.is_dataclass(field_type):
                yield from mk_docs(field_type, prefix=f"{prefix}{field.name}[].")
                continue

        if field.default is not dataclasses.MISSING and field.default is not None:
            default = repr(
                str(field.default)
                if isinstance(field.default, (Path, Version))
                else field.default
            )
        elif field.default_factory is not dataclasses.MISSING:
            default = repr(field.default_factory())
        else:
            default = '""'

        yield DCDoc(
            f"{prefix}{field.name}".replace("_", "-"),
            default.replace("'", '"').replace("True", "true").replace("False", "false"),
            docs[field.name],
        )
