from __future__ import annotations

from . import ast_nodes as ast
from .errors import MakakaError
from .lexer import Lexer, Token


TOKEN_NAMES = {
    "NEWLINE": "конец строки",
    "INDENT": "отступ",
    "DEDENT": "конец блока",
    "EOF": "конец файла",
    "IDENTIFIER": "имя",
    "INTEGER": "целое число",
    "STRING": "строка",
    "LPAREN": "'('",
    "RPAREN": "')'",
    "COMMA": "','",
    "COLON": "':'",
}


class Parser:
    def __init__(self, source: str, filename: str = "<источник>") -> None:
        self.filename = filename
        self.source = source
        self.lines = source.lstrip("\ufeff").splitlines()
        self.tokens = Lexer(source, filename).tokenize()
        self.position = 0
        self.prefix_functions = self._find_function_arities()
        self.prefix_functions.update({"число": (1, 1), "ввод": (0, 1)})

    def _find_function_arities(self) -> dict[str, tuple[int, int]]:
        """Собирает арности до разбора, чтобы вызовы работали без скобок."""
        functions: dict[str, tuple[int, int]] = {}
        position = 0
        while position < len(self.tokens):
            if self.tokens[position].kind != "FUNCTION":
                position += 1
                continue
            if (
                position + 1 >= len(self.tokens)
                or self.tokens[position + 1].kind != "IDENTIFIER"
            ):
                position += 1
                continue
            name = self.tokens[position + 1].value
            position += 2  # FUNCTION и имя
            count = 0
            if position < len(self.tokens) and self.tokens[position].kind == "LPAREN":
                depth = 0
                while position < len(self.tokens):
                    kind = self.tokens[position].kind
                    if kind == "LPAREN":
                        depth += 1
                    elif kind == "RPAREN":
                        depth -= 1
                        if depth == 0:
                            break
                    elif kind == "IDENTIFIER" and depth == 1:
                        count += 1
                    position += 1
            else:
                while position < len(self.tokens):
                    kind = self.tokens[position].kind
                    if kind in {"COLON", "NEWLINE", "EOF"}:
                        break
                    if kind == "IDENTIFIER":
                        count += 1
                    position += 1
            functions[name] = (count, count)
            position += 1
        return functions

    @property
    def current(self) -> Token:
        return self.tokens[self.position]

    def advance(self) -> Token:
        token = self.current
        if token.kind != "EOF":
            self.position += 1
        return token

    def check(self, kind: str) -> bool:
        return self.current.kind == kind

    def match(self, *kinds: str) -> Token | None:
        if self.current.kind in kinds:
            return self.advance()
        return None

    def expect(self, kind: str, message: str | None = None) -> Token:
        if self.check(kind):
            return self.advance()
        expected = message or f"ожидалось {TOKEN_NAMES.get(kind, kind)}"
        raise self.error(expected, self.current)

    def error(self, message: str, token: Token) -> MakakaError:
        source_line = self.lines[token.line - 1] if 0 < token.line <= len(self.lines) else ""
        return MakakaError(
            message,
            self.filename,
            token.line,
            token.column,
            source_line,
        )

    def parse(self) -> ast.Program:
        first = self.current
        body: list[ast.Statement] = []
        self._skip_newlines()
        while not self.check("EOF"):
            if self.check("INDENT") or self.check("DEDENT"):
                raise self.error("неожиданный отступ", self.current)
            body.append(self.statement())
            self._skip_newlines()
        return ast.Program(first.line, first.column, body)

    def _skip_newlines(self) -> None:
        while self.match("NEWLINE"):
            pass

    def statement(self) -> ast.Statement:
        if self.check("IF"):
            return self.if_statement()
        if self.check("WHILE"):
            return self.while_statement()
        if self.check("FUNCTION"):
            return self.function_statement()
        return self.simple_statement()

    def simple_statement(self) -> ast.Statement:
        token = self.current
        if self.match("BREAK"):
            result: ast.Statement = ast.Break(token.line, token.column)
        elif self.match("CONTINUE"):
            result = ast.Continue(token.line, token.column)
        elif self.match("PASS"):
            result = ast.Pass(token.line, token.column)
        elif self.match("RETURN"):
            value = None if self.check("NEWLINE") else self.expression()
            result = ast.Return(token.line, token.column, value)
        elif (
            self.check("IDENTIFIER")
            and self.current.value == "печать"
            and self.tokens[self.position + 1].kind not in {"=", "LPAREN"}
        ):
            self.advance()
            arguments: list[ast.Expression] = []
            while not self.check("NEWLINE"):
                arguments.append(self.expression())
                self.match("COMMA")
            call = ast.Call(token.line, token.column, "печать", arguments)
            result = ast.ExpressionStatement(token.line, token.column, call)
        elif (
            self.check("IDENTIFIER")
            and self.tokens[self.position + 1].kind == "="
        ):
            name = self.advance()
            self.advance()
            value = self.expression()
            result = ast.Assignment(name.line, name.column, name.value, value)
        else:
            value = self.expression()
            result = ast.ExpressionStatement(value.line, value.column, value)
        self.expect("NEWLINE", "ожидался конец строки после инструкции")
        return result

    def block(self) -> list[ast.Statement]:
        self.match("COLON")
        self.expect("NEWLINE", "после заголовка блока ожидался конец строки")
        self.expect("INDENT", "ожидался блок с отступом на следующей строке")
        body: list[ast.Statement] = []
        self._skip_newlines()
        while not self.check("DEDENT") and not self.check("EOF"):
            body.append(self.statement())
            self._skip_newlines()
        self.expect("DEDENT")
        if not body:
            raise self.error("блок не может быть пустым; используйте 'проход'", self.current)
        return body

    def if_statement(self) -> ast.If:
        token = self.expect("IF")
        condition = self.expression()
        body = self.block()
        branches: list[tuple[ast.Expression, list[ast.Statement]]] = []
        else_body = None
        while self.match("ELIF"):
            branch_condition = self.expression()
            branches.append((branch_condition, self.block()))
        if self.match("ELSE"):
            else_body = self.block()
        return ast.If(token.line, token.column, condition, body, branches, else_body)

    def while_statement(self) -> ast.While:
        token = self.expect("WHILE")
        condition = self.expression()
        return ast.While(token.line, token.column, condition, self.block())

    def function_statement(self) -> ast.Function:
        token = self.expect("FUNCTION")
        name = self.expect("IDENTIFIER", "после 'функция' ожидалось имя функции")
        parameters: list[str] = []
        if self.match("LPAREN"):
            if not self.check("RPAREN"):
                while True:
                    parameter = self.expect("IDENTIFIER", "ожидалось имя параметра")
                    parameters.append(parameter.value)
                    if not self.match("COMMA"):
                        break
            self.expect("RPAREN", "ожидалось ')' после параметров функции")
        else:
            while self.check("IDENTIFIER") or self.check("COMMA"):
                if self.match("COMMA"):
                    continue
                parameters.append(self.advance().value)
        body = self.block()
        return ast.Function(token.line, token.column, name.value, parameters, body)

    def expression(self) -> ast.Expression:
        return self.parse_or()

    def parse_or(self) -> ast.Expression:
        left = self.parse_and()
        while self.match("OR"):
            operator = self.tokens[self.position - 1]
            right = self.parse_and()
            left = ast.Binary(operator.line, operator.column, left, "или", right)
        return left

    def parse_and(self) -> ast.Expression:
        left = self.parse_not()
        while self.match("AND"):
            operator = self.tokens[self.position - 1]
            right = self.parse_not()
            left = ast.Binary(operator.line, operator.column, left, "и", right)
        return left

    def parse_not(self) -> ast.Expression:
        token = self.match("NOT")
        if token:
            return ast.Unary(token.line, token.column, "не", self.parse_not())
        return self.comparison()

    def comparison(self) -> ast.Expression:
        left = self.term()
        if self.current.kind in {"=", "==", "!=", "<", ">", "<=", ">="}:
            operator = self.advance()
            right = self.term()
            return ast.Binary(operator.line, operator.column, left, operator.kind, right)
        return left

    def term(self) -> ast.Expression:
        left = self.factor()
        while self.current.kind in {"+", "-"}:
            operator = self.advance()
            right = self.factor()
            left = ast.Binary(operator.line, operator.column, left, operator.kind, right)
        return left

    def factor(self) -> ast.Expression:
        left = self.unary()
        while self.current.kind in {"*", "/", "%"}:
            operator = self.advance()
            right = self.unary()
            left = ast.Binary(operator.line, operator.column, left, operator.kind, right)
        return left

    def unary(self) -> ast.Expression:
        if self.current.kind in {"+", "-"}:
            operator = self.advance()
            return ast.Unary(operator.line, operator.column, operator.kind, self.unary())
        return self.primary()

    @staticmethod
    def _starts_expression(token: Token) -> bool:
        return token.kind in {
            "INTEGER",
            "STRING",
            "TRUE",
            "FALSE",
            "IDENTIFIER",
            "LPAREN",
            "NOT",
            "+",
            "-",
        }

    def primary(self) -> ast.Expression:
        token = self.current
        if self.match("INTEGER"):
            digits = token.value.lstrip("0") or "0"
            if len(digits) > 19:
                raise self.error(
                    "целочисленный литерал не помещается в 64 бита", token
                )
            return ast.Integer(token.line, token.column, int(digits))
        if self.match("STRING"):
            return ast.String(token.line, token.column, token.value)
        if self.match("TRUE"):
            return ast.Boolean(token.line, token.column, True)
        if self.match("FALSE"):
            return ast.Boolean(token.line, token.column, False)
        if self.match("IDENTIFIER"):
            if self.match("LPAREN"):
                arguments: list[ast.Expression] = []
                if not self.check("RPAREN"):
                    while True:
                        arguments.append(self.expression())
                        if not self.match("COMMA"):
                            break
                self.expect("RPAREN", "ожидалось ')' после аргументов вызова")
                return ast.Call(token.line, token.column, token.value, arguments)
            if token.value in self.prefix_functions:
                minimum, maximum = self.prefix_functions[token.value]
                count = minimum
                if maximum > minimum and self._starts_expression(self.current):
                    count = maximum
                # Аргумент без скобок — один простой операнд. Поэтому
                # «сложить 2 2 равно 4» сравнивает результат вызова с 4.
                arguments = [self.unary() for _ in range(count)]
                return ast.Call(token.line, token.column, token.value, arguments)
            return ast.Variable(token.line, token.column, token.value)
        if self.match("LPAREN"):
            value = self.expression()
            self.expect("RPAREN", "ожидалась закрывающая ')'")
            return value
        raise self.error("ожидалось выражение", token)
