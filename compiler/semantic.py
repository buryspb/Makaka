from __future__ import annotations

from dataclasses import dataclass

from . import ast_nodes as ast
from .errors import MakakaError


BUILTINS = {
    "печать": (0, None),
    "ввод": (0, 1),
    "число": (1, 1),
}
MAX_INTEGER = (1 << 63) - 1


@dataclass
class Context:
    variables: set[str]
    function: str | None
    loop_depth: int = 0


class SemanticAnalyzer:
    def __init__(self, program: ast.Program, filename: str, source: str) -> None:
        self.program = program
        self.filename = filename
        self.lines = source.lstrip("\ufeff").splitlines()
        self.functions: dict[str, ast.Function] = {}

    def error(self, message: str, node: ast.Node) -> MakakaError:
        source_line = self.lines[node.line - 1] if 0 < node.line <= len(self.lines) else ""
        return MakakaError(
            message,
            self.filename,
            node.line,
            node.column,
            source_line,
        )

    def analyze(self) -> dict[str, ast.Function]:
        for statement in self.program.body:
            if isinstance(statement, ast.Function):
                if statement.name in self.functions:
                    raise self.error(f"функция '{statement.name}' уже объявлена", statement)
                if statement.name in BUILTINS:
                    raise self.error(
                        f"имя встроенной функции '{statement.name}' нельзя переопределить",
                        statement,
                    )
                self.functions[statement.name] = statement

        main = Context(set(), None)
        self._statements(self.program.body, main, top_level=True)
        for function in self.functions.values():
            duplicates = {
                name for name in function.parameters if function.parameters.count(name) > 1
            }
            if duplicates:
                raise self.error(
                    f"параметр '{next(iter(duplicates))}' указан более одного раза",
                    function,
                )
            if any(name in BUILTINS or name in self.functions for name in function.parameters):
                raise self.error("параметр не может совпадать с именем функции", function)
            context = Context(set(function.parameters), function.name)
            self._statements(function.body, context)
        return self.functions

    def _statements(
        self, statements: list[ast.Statement], context: Context, top_level: bool = False
    ) -> bool:
        """Проверяет список и сообщает, достижима ли инструкция после него."""
        falls_through = True
        for statement in statements:
            statement_falls_through = True
            if isinstance(statement, ast.Function):
                if not top_level:
                    raise self.error("вложенные определения функций не поддерживаются", statement)
                continue
            if isinstance(statement, ast.Assignment):
                if statement.name in BUILTINS or statement.name in self.functions:
                    raise self.error("имя функции нельзя использовать как переменную", statement)
                self.expression(statement.value, context)
                context.variables.add(statement.name)
            elif isinstance(statement, ast.ExpressionStatement):
                self.expression(statement.value, context)
            elif isinstance(statement, ast.If):
                self.expression(statement.condition, context)
                original = set(context.variables)
                branches: list[tuple[set[str], bool]] = []
                body_context = Context(set(original), context.function, context.loop_depth)
                body_reaches_end = self._statements(statement.body, body_context)
                branches.append((body_context.variables, body_reaches_end))
                for condition, body in statement.elif_branches:
                    self.expression(condition, context)
                    branch = Context(set(original), context.function, context.loop_depth)
                    reaches_end = self._statements(body, branch)
                    branches.append((branch.variables, reaches_end))
                if statement.else_body is not None:
                    branch = Context(set(original), context.function, context.loop_depth)
                    reaches_end = self._statements(statement.else_body, branch)
                    branches.append((branch.variables, reaches_end))
                else:
                    branches.append((original, True))
                reachable = [variables for variables, reaches in branches if reaches]
                if reachable:
                    context.variables = set.intersection(*reachable)
                statement_falls_through = any(reaches for _, reaches in branches)
            elif isinstance(statement, ast.While):
                self.expression(statement.condition, context)
                original = set(context.variables)
                body = Context(set(original), context.function, context.loop_depth + 1)
                self._statements(statement.body, body)
                context.variables = original
            elif isinstance(statement, ast.Return):
                if context.function is None:
                    raise self.error("'вернуть' можно использовать только внутри функции", statement)
                if statement.value is not None:
                    self.expression(statement.value, context)
                statement_falls_through = False
            elif isinstance(statement, (ast.Break, ast.Continue)):
                if context.loop_depth == 0:
                    word = "прервать" if isinstance(statement, ast.Break) else "продолжить"
                    raise self.error(f"'{word}' можно использовать только внутри цикла", statement)
                statement_falls_through = False
            elif isinstance(statement, ast.Pass):
                pass
            falls_through = statement_falls_through and falls_through
        return falls_through

    def expression(self, expression: ast.Expression, context: Context) -> None:
        if isinstance(expression, ast.Integer):
            if expression.value > MAX_INTEGER:
                raise self.error("целочисленный литерал не помещается в 64 бита", expression)
        elif isinstance(expression, ast.Variable):
            if expression.name not in context.variables:
                raise self.error(f"переменная '{expression.name}' не определена", expression)
        elif isinstance(expression, ast.Unary):
            if (
                expression.operator == "-"
                and isinstance(expression.operand, ast.Integer)
                and expression.operand.value == MAX_INTEGER + 1
            ):
                return
            self.expression(expression.operand, context)
        elif isinstance(expression, ast.Binary):
            self.expression(expression.left, context)
            self.expression(expression.right, context)
        elif isinstance(expression, ast.Call):
            for argument in expression.arguments:
                self.expression(argument, context)
            if expression.name in BUILTINS:
                minimum, maximum = BUILTINS[expression.name]
                count = len(expression.arguments)
                if count < minimum or (maximum is not None and count > maximum):
                    if maximum == minimum:
                        expected = str(minimum)
                    elif maximum is None:
                        expected = f"не менее {minimum}"
                    else:
                        expected = f"от {minimum} до {maximum}"
                    raise self.error(
                        f"функция '{expression.name}' принимает аргументов: {expected}; получено: {count}",
                        expression,
                    )
            elif expression.name in self.functions:
                expected = len(self.functions[expression.name].parameters)
                if len(expression.arguments) != expected:
                    raise self.error(
                        f"функция '{expression.name}' принимает аргументов: {expected}; получено: {len(expression.arguments)}",
                        expression,
                    )
            else:
                raise self.error(f"неизвестная функция '{expression.name}'", expression)
