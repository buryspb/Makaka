from __future__ import annotations


class MakakaError(Exception):
    """Ошибка компиляции с позицией в исходном файле."""

    def __init__(
        self,
        message: str,
        filename: str = "<источник>",
        line: int = 0,
        column: int = 0,
        source_line: str = "",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.filename = filename
        self.line = line
        self.column = column
        self.source_line = source_line

    def __str__(self) -> str:
        location = self.filename
        if self.line:
            location += f":{self.line}"
            if self.column:
                location += f":{self.column}"
        result = f"{location}: ошибка: {self.message}"
        if self.source_line:
            result += f"\n  {self.source_line.rstrip()}"
            if self.column:
                result += "\n  " + " " * max(0, self.column - 1) + "^"
        return result
