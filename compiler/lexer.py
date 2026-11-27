from __future__ import annotations

from dataclasses import dataclass

from .errors import MakakaError


KEYWORDS = {
    "Истина": "TRUE",
    "Ложь": "FALSE",
    "если": "IF",
    "иначе_если": "ELIF",
    "иначе": "ELSE",
    "пока": "WHILE",
    "прервать": "BREAK",
    "продолжить": "CONTINUE",
    "функция": "FUNCTION",
    "вернуть": "RETURN",
    "проход": "PASS",
    "и": "AND",
    "или": "OR",
    "не": "NOT",
    "равно": "=",
    "не_равно": "!=",
    "меньше": "<",
    "больше": ">",
    "не_меньше": ">=",
    "не_больше": "<=",
    "меньше_или_равно": "<=",
    "больше_или_равно": ">=",
}

TWO_CHAR_OPERATORS = {"==", "!=", "<=", ">="}
ONE_CHAR_TOKENS = {
    "+": "+",
    "-": "-",
    "*": "*",
    "/": "/",
    "%": "%",
    "<": "<",
    ">": ">",
    "=": "=",
    "(": "LPAREN",
    ")": "RPAREN",
    ",": "COMMA",
    ":": "COLON",
}


@dataclass(slots=True)
class Token:
    kind: str
    value: str
    line: int
    column: int


class Lexer:
    def __init__(self, source: str, filename: str = "<источник>") -> None:
        self.source = source.lstrip("\ufeff")
        self.filename = filename
        self.lines = self.source.splitlines()
        self.tokens: list[Token] = []
        self.indents = [0]

    def error(self, message: str, line: int, column: int = 1) -> MakakaError:
        source_line = self.lines[line - 1] if 0 < line <= len(self.lines) else ""
        return MakakaError(message, self.filename, line, column, source_line)

    def tokenize(self) -> list[Token]:
        for line_number, raw_line in enumerate(self.lines, 1):
            content = self._without_comment(raw_line)
            if not content.strip():
                continue

            prefix = content[: len(content) - len(content.lstrip(" \t"))]
            width = self._indent_width(prefix, line_number)
            if width > self.indents[-1]:
                self.indents.append(width)
                self.tokens.append(Token("INDENT", "", line_number, 1))
            else:
                while width < self.indents[-1]:
                    self.indents.pop()
                    self.tokens.append(Token("DEDENT", "", line_number, 1))
                if width != self.indents[-1]:
                    raise self.error(
                        "несогласованный отступ: строка не совпадает ни с одним уровнем",
                        line_number,
                    )

            start = len(prefix)
            self._tokenize_line(content, line_number, start)
            self.tokens.append(Token("NEWLINE", "", line_number, len(content) + 1))

        last_line = max(1, len(self.lines))
        while len(self.indents) > 1:
            self.indents.pop()
            self.tokens.append(Token("DEDENT", "", last_line, 1))
        self.tokens.append(Token("EOF", "", last_line + (not self.lines), 1))
        return self.tokens

    def _indent_width(self, prefix: str, line: int) -> int:
        width = 0
        for char in prefix:
            width += 4 if char == "\t" else 1
        if "\t" in prefix and " " in prefix.strip("\t"):
            # Смешивание разрешено, но визуальная ширина определяется однозначно:
            # табуляция всегда имеет ширину четырёх пробелов.
            pass
        return width

    @staticmethod
    def _without_comment(line: str) -> str:
        quote = ""
        escaped = False
        for index, char in enumerate(line):
            if escaped:
                escaped = False
                continue
            if quote and char == "\\":
                escaped = True
                continue
            if char in "\"'":
                if not quote:
                    quote = char
                elif quote == char:
                    quote = ""
            elif char == "#" and not quote:
                return line[:index]
        return line

    def _tokenize_line(self, line: str, line_number: int, start: int) -> None:
        index = start
        while index < len(line):
            char = line[index]
            if char in " \t":
                index += 1
                continue
            column = index + 1
            if char.isalpha() or char == "_":
                end = index + 1
                while end < len(line) and (line[end].isalnum() or line[end] == "_"):
                    end += 1
                value = line[index:end]
                self.tokens.append(
                    Token(KEYWORDS.get(value, "IDENTIFIER"), value, line_number, column)
                )
                index = end
                continue
            if "0" <= char <= "9":
                end = index + 1
                while end < len(line) and "0" <= line[end] <= "9":
                    end += 1
                value = line[index:end]
                self.tokens.append(Token("INTEGER", value, line_number, column))
                index = end
                continue
            if char in "\"'":
                value, index = self._string(line, index, line_number)
                self.tokens.append(Token("STRING", value, line_number, column))
                continue
            pair = line[index : index + 2]
            if pair in TWO_CHAR_OPERATORS:
                self.tokens.append(Token(pair, pair, line_number, column))
                index += 2
                continue
            if char in ONE_CHAR_TOKENS:
                self.tokens.append(
                    Token(ONE_CHAR_TOKENS[char], char, line_number, column)
                )
                index += 1
                continue
            raise self.error(f"неожиданный символ {char!r}", line_number, column)

    def _string(self, line: str, start: int, line_number: int) -> tuple[str, int]:
        quote = line[start]
        result: list[str] = []
        index = start + 1
        escapes = {
            "n": "\n",
            "r": "\r",
            "t": "\t",
            "\\": "\\",
            '"': '"',
            "'": "'",
            "0": "\0",
        }
        while index < len(line):
            char = line[index]
            if char == quote:
                return "".join(result), index + 1
            if char == "\\":
                index += 1
                if index >= len(line):
                    break
                escaped = line[index]
                if escaped not in escapes:
                    raise self.error(
                        f"неизвестная escape-последовательность \\{escaped}",
                        line_number,
                        index,
                    )
                result.append(escapes[escaped])
                index += 1
                continue
            result.append(char)
            index += 1
        raise self.error("строковый литерал не закрыт", line_number, start + 1)
