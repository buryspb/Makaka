from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class Node:
    line: int
    column: int


@dataclass(slots=True)
class Expression(Node):
    pass


@dataclass(slots=True)
class Integer(Expression):
    value: int


@dataclass(slots=True)
class String(Expression):
    value: str


@dataclass(slots=True)
class Boolean(Expression):
    value: bool


@dataclass(slots=True)
class Variable(Expression):
    name: str


@dataclass(slots=True)
class Unary(Expression):
    operator: str
    operand: Expression


@dataclass(slots=True)
class Binary(Expression):
    left: Expression
    operator: str
    right: Expression


@dataclass(slots=True)
class Call(Expression):
    name: str
    arguments: list[Expression]


@dataclass(slots=True)
class Statement(Node):
    pass


@dataclass(slots=True)
class Assignment(Statement):
    name: str
    value: Expression


@dataclass(slots=True)
class ExpressionStatement(Statement):
    value: Expression


@dataclass(slots=True)
class If(Statement):
    condition: Expression
    body: list[Statement]
    elif_branches: list[tuple[Expression, list[Statement]]] = field(default_factory=list)
    else_body: Optional[list[Statement]] = None


@dataclass(slots=True)
class While(Statement):
    condition: Expression
    body: list[Statement]


@dataclass(slots=True)
class Function(Statement):
    name: str
    parameters: list[str]
    body: list[Statement]


@dataclass(slots=True)
class Return(Statement):
    value: Optional[Expression]


@dataclass(slots=True)
class Break(Statement):
    pass


@dataclass(slots=True)
class Continue(Statement):
    pass


@dataclass(slots=True)
class Pass(Statement):
    pass


@dataclass(slots=True)
class Program(Node):
    body: list[Statement]
