from __future__ import annotations

from pathlib import Path

from . import ast_nodes as ast
from .errors import MakakaError


TAG_INTEGER = 0
TAG_STRING = 1
TAG_BOOLEAN = 2
TAG_NOTHING = 3
MAX_INTEGER = (1 << 63) - 1


class CodeGenerator:
    def __init__(
        self,
        program: ast.Program,
        functions: dict[str, ast.Function],
        filename: str,
        source: str,
    ) -> None:
        self.program = program
        self.functions = functions
        self.filename = filename
        self.source_lines = source.lstrip("\ufeff").splitlines()
        self.lines: list[str] = []
        self.counter = 0
        self.string_labels: dict[str, str] = {}
        self.function_labels = {
            name: f"mk_function_{index}" for index, name in enumerate(functions, 1)
        }
        self.scopes: list[dict[str, int]] = []
        self.current_return = ""
        self.loop_labels: list[tuple[str, str]] = []

    def label(self, prefix: str = "L") -> str:
        self.counter += 1
        return f".{prefix}_{self.counter}"

    def emit(self, line: str = "") -> None:
        self.lines.append(line)

    def error(self, message: str, node: ast.Node) -> MakakaError:
        source_line = (
            self.source_lines[node.line - 1]
            if 0 < node.line <= len(self.source_lines)
            else ""
        )
        return MakakaError(
            message, self.filename, node.line, node.column, source_line
        )

    def generate(self) -> str:
        self.emit("bits 64")
        self.emit("default rel")
        self.emit("")
        self.emit("global start")
        self.emit(
            "extern SetConsoleOutputCP, SetConsoleCP, GetStdHandle, WriteFile, ReadFile"
        )
        self.emit("extern GetProcessHeap, HeapAlloc, HeapReAlloc, ExitProcess")
        self.emit("")
        self.emit("section .text")
        self.emit("start:")
        self.emit("    and rsp, -16")
        self.emit("    sub rsp, 32")
        self.emit("    mov ecx, 65001")
        self.emit("    call SetConsoleOutputCP")
        self.emit("    mov ecx, 65001")
        self.emit("    call SetConsoleCP")
        self.emit("    add rsp, 32")
        self.emit("    call mk_main")
        self.emit("    xor ecx, ecx")
        self.emit("    sub rsp, 32")
        self.emit("    call ExitProcess")
        self.emit("    int3")
        self.emit("")

        main_names = self._collect_variables(self.program.body)
        self._function("mk_main", [], self.program.body, main_names, main=True)
        for name, function in self.functions.items():
            variables = self._collect_variables(function.body)
            for parameter in function.parameters:
                if parameter not in variables:
                    variables[parameter] = 16 * (len(variables) + 1)
            self._function(
                self.function_labels[name],
                function.parameters,
                function.body,
                variables,
            )

        self.emit("section .data")
        self.emit("mk__space: db ' '")
        for value, label in self.string_labels.items():
            data = value.encode("utf-8") + b"\0"
            encoded = ",".join(str(byte) for byte in data)
            comment = value.replace("\n", "\\n").replace("\r", "\\r")
            self.emit(f'{label}: ; "{comment}"')
            self.emit(f"    dq {len(data) - 1}")
            self.emit(f"    db {encoded}")
        self.emit("")

        runtime = Path(__file__).with_name("runtime.asm").read_text(encoding="utf-8")
        return "\n".join(self.lines) + "\n" + runtime

    def _collect_variables(self, statements: list[ast.Statement]) -> dict[str, int]:
        names: dict[str, int] = {}

        def visit_body(body: list[ast.Statement]) -> None:
            for statement in body:
                if isinstance(statement, ast.Assignment):
                    if statement.name not in names:
                        names[statement.name] = 16 * (len(names) + 1)
                elif isinstance(statement, ast.If):
                    visit_body(statement.body)
                    for _, branch in statement.elif_branches:
                        visit_body(branch)
                    if statement.else_body is not None:
                        visit_body(statement.else_body)
                elif isinstance(statement, ast.While):
                    visit_body(statement.body)

        visit_body(statements)
        return names

    def _function(
        self,
        label: str,
        parameters: list[str],
        body: list[ast.Statement],
        variables: dict[str, int],
        main: bool = False,
    ) -> None:
        self.scopes.append(variables)
        self.current_return = self.label("return")
        frame_size = max(16, ((len(variables) * 16 + 15) // 16) * 16)
        self.emit(f"{label}:")
        self.emit("    push rbp")
        self.emit("    mov rbp, rsp")
        if frame_size > 4096:
            probe = self.label("probe_stack")
            finish_probe = self.label("finish_probe")
            self.emit(f"    mov r10, {frame_size}")
            self.emit(f"{probe}:")
            self.emit("    cmp r10, 4096")
            self.emit(f"    jb {finish_probe}")
            self.emit("    sub rsp, 4096")
            self.emit("    or qword [rsp], 0")
            self.emit("    sub r10, 4096")
            self.emit(f"    jmp {probe}")
            self.emit(f"{finish_probe}:")
            self.emit("    sub rsp, r10")
            self.emit("    or qword [rsp], 0")
        else:
            self.emit(f"    sub rsp, {frame_size}")
        count = len(parameters)
        for index, name in enumerate(parameters):
            source_offset = 16 + (count - 1 - index) * 16
            destination = variables[name]
            self.emit(f"    mov rax, [rbp+{source_offset + 8}]")
            self.emit(f"    mov [rbp-{destination}], rax")
            self.emit(f"    mov rax, [rbp+{source_offset}]")
            self.emit(f"    mov [rbp-{destination - 8}], rax")
        for statement in body:
            if main and isinstance(statement, ast.Function):
                continue
            self.statement(statement)
        self.emit("    mov eax, 3")
        self.emit("    xor edx, edx")
        self.emit(f"{self.current_return}:")
        self.emit("    leave")
        self.emit("    ret")
        self.emit("")
        self.scopes.pop()

    def statement(self, statement: ast.Statement) -> None:
        self.emit(f"    ; строка {statement.line}")
        if isinstance(statement, ast.Assignment):
            self.expression(statement.value)
            offset = self.scopes[-1][statement.name]
            self.emit(f"    mov [rbp-{offset}], rax")
            self.emit(f"    mov [rbp-{offset - 8}], rdx")
        elif isinstance(statement, ast.ExpressionStatement):
            self.expression(statement.value)
        elif isinstance(statement, ast.If):
            self._if(statement)
        elif isinstance(statement, ast.While):
            start = self.label("while")
            end = self.label("end_while")
            self.emit(f"{start}:")
            self.expression(statement.condition)
            self.emit("    call mk__truthy")
            self.emit("    test eax, eax")
            self.emit(f"    jz {end}")
            self.loop_labels.append((start, end))
            for child in statement.body:
                self.statement(child)
            self.loop_labels.pop()
            self.emit(f"    jmp {start}")
            self.emit(f"{end}:")
        elif isinstance(statement, ast.Return):
            if statement.value is None:
                self.emit("    mov eax, 3")
                self.emit("    xor edx, edx")
            else:
                self.expression(statement.value)
            self.emit(f"    jmp {self.current_return}")
        elif isinstance(statement, ast.Break):
            self.emit(f"    jmp {self.loop_labels[-1][1]}")
        elif isinstance(statement, ast.Continue):
            self.emit(f"    jmp {self.loop_labels[-1][0]}")
        elif isinstance(statement, ast.Pass):
            self.emit("    nop")
        elif isinstance(statement, ast.Function):
            raise self.error("вложенные функции не поддерживаются", statement)

    def _if(self, statement: ast.If) -> None:
        end = self.label("end_if")
        next_label = self.label("else")
        self.expression(statement.condition)
        self.emit("    call mk__truthy")
        self.emit("    test eax, eax")
        self.emit(f"    jz {next_label}")
        for child in statement.body:
            self.statement(child)
        self.emit(f"    jmp {end}")
        for condition, body in statement.elif_branches:
            self.emit(f"{next_label}:")
            next_label = self.label("else")
            self.expression(condition)
            self.emit("    call mk__truthy")
            self.emit("    test eax, eax")
            self.emit(f"    jz {next_label}")
            for child in body:
                self.statement(child)
            self.emit(f"    jmp {end}")
        self.emit(f"{next_label}:")
        if statement.else_body is not None:
            for child in statement.else_body:
                self.statement(child)
        self.emit(f"{end}:")

    def expression(self, expression: ast.Expression) -> None:
        if isinstance(expression, ast.Integer):
            if expression.value > MAX_INTEGER:
                raise self.error(
                    "целочисленный литерал не помещается в 64 бита", expression
                )
            self.emit("    xor eax, eax")
            self.emit(f"    mov rdx, {expression.value}")
        elif isinstance(expression, ast.String):
            label = self._string_label(expression.value)
            self.emit("    mov eax, 1")
            self.emit(f"    lea rdx, [rel {label}]")
        elif isinstance(expression, ast.Boolean):
            self.emit("    mov eax, 2")
            self.emit(f"    mov edx, {int(expression.value)}")
        elif isinstance(expression, ast.Variable):
            offset = self.scopes[-1][expression.name]
            self.emit(f"    mov rax, [rbp-{offset}]")
            self.emit(f"    mov rdx, [rbp-{offset - 8}]")
        elif isinstance(expression, ast.Unary):
            if (
                expression.operator == "-"
                and isinstance(expression.operand, ast.Integer)
                and expression.operand.value == MAX_INTEGER + 1
            ):
                self.emit("    xor eax, eax")
                self.emit("    mov rdx, 0x8000000000000000")
                return
            self.expression(expression.operand)
            if expression.operator == "-":
                self.emit("    call mk__negate")
            elif expression.operator == "+":
                self.emit("    call mk__positive")
            else:
                self.emit("    call mk__truthy")
                self.emit("    xor eax, 1")
                self.emit("    mov edx, eax")
                self.emit("    mov eax, 2")
        elif isinstance(expression, ast.Binary):
            self._binary(expression)
        elif isinstance(expression, ast.Call):
            self._call(expression)
        else:
            raise self.error("неизвестное выражение", expression)

    def _binary(self, expression: ast.Binary) -> None:
        if expression.operator in {"и", "или"}:
            self.expression(expression.left)
            self.emit("    call mk__truthy")
            self.emit("    test eax, eax")
            shortcut = self.label("logic")
            end = self.label("end_logic")
            if expression.operator == "и":
                self.emit(f"    jz {shortcut}")
            else:
                self.emit(f"    jnz {shortcut}")
            self.expression(expression.right)
            self.emit("    call mk__truthy")
            self.emit("    and eax, 1")
            self.emit(f"    jmp {end}")
            self.emit(f"{shortcut}:")
            self.emit(f"    mov eax, {0 if expression.operator == 'и' else 1}")
            self.emit(f"{end}:")
            self.emit("    mov edx, eax")
            self.emit("    mov eax, 2")
            return

        self.expression(expression.left)
        self.emit("    push rax")
        self.emit("    push rdx")
        self.expression(expression.right)
        self.emit("    mov r10, rax")
        self.emit("    mov r11, rdx")
        self.emit("    pop rdx")
        self.emit("    pop rax")
        self.emit("    mov rcx, r10")
        self.emit("    mov r8, r11")
        operations = {
            "+": "mk__add",
            "-": "mk__sub",
            "*": "mk__mul",
            "/": "mk__div",
            "%": "mk__mod",
            "=": "mk__equal",
            "==": "mk__equal",
            "!=": "mk__equal",
        }
        if expression.operator in operations:
            self.emit(f"    call {operations[expression.operator]}")
            if expression.operator == "!=":
                self.emit("    xor rdx, 1")
        else:
            comparison = {"<": 0, "<=": 1, ">": 2, ">=": 3}[expression.operator]
            self.emit(f"    mov r9d, {comparison}")
            self.emit("    call mk__compare")

    def _call(self, expression: ast.Call) -> None:
        name = expression.name
        if name == "печать":
            count = len(expression.arguments)
            for argument in expression.arguments:
                self.expression(argument)
                self.emit("    push rax")
                self.emit("    push rdx")
            for index in range(count):
                if index:
                    self.emit("    lea rcx, [rel mk__space]")
                    self.emit("    mov edx, 1")
                    self.emit("    call mk__write_bytes")
                offset = (count - 1 - index) * 16
                self.emit(f"    mov rax, [rsp+{offset + 8}]")
                self.emit(f"    mov rdx, [rsp+{offset}]")
                self.emit("    call mk__print")
            if count:
                self.emit(f"    add rsp, {count * 16}")
            self.emit("    lea rcx, [rel mk__newline]")
            self.emit("    mov edx, 2")
            self.emit("    call mk__write_bytes")
            self.emit("    mov eax, 3")
            self.emit("    xor edx, edx")
            return
        if name == "ввод":
            if expression.arguments:
                self.expression(expression.arguments[0])
                self.emit("    call mk__print")
            self.emit("    call mk__input")
            return
        if name == "число":
            self.expression(expression.arguments[0])
            self.emit("    call mk__to_integer")
            return

        for argument in expression.arguments:
            self.expression(argument)
            self.emit("    push rax")
            self.emit("    push rdx")
        self.emit(f"    call {self.function_labels[name]}")
        if expression.arguments:
            self.emit(f"    add rsp, {len(expression.arguments) * 16}")

    def _string_label(self, value: str) -> str:
        if value not in self.string_labels:
            self.string_labels[value] = f"mk_string_{len(self.string_labels) + 1}"
        return self.string_labels[value]
