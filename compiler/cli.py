from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from .codegen import CodeGenerator
from .errors import MakakaError
from .parser import Parser
from .semantic import SemanticAnalyzer


ROOT = Path(__file__).resolve().parent.parent


def find_tool(name: str) -> Path | None:
    environment = os.environ.get(f"MAKAKA_{name.upper()}")
    if environment:
        candidate = Path(environment)
        if candidate.is_file():
            return candidate
    executable = name + (".exe" if os.name == "nt" else "")
    installed = shutil.which(executable)
    if installed:
        return Path(installed)
    bundled = ROOT / "tools" / "bin" / executable
    return bundled if bundled.is_file() else None


def read_source(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as error:
        raise MakakaError(
            "исходный файл должен быть сохранён в кодировке UTF-8", str(path)
        ) from error


def compile_source(path: Path, check_only: bool = False) -> Path:
    if not path.is_file():
        raise MakakaError("файл не найден", str(path))
    if path.suffix.lower() != ".mkk":
        raise MakakaError("ожидался исходный файл с расширением .mkk", str(path))

    source = read_source(path)
    program = Parser(source, str(path)).parse()
    functions = SemanticAnalyzer(program, str(path), source).analyze()
    if check_only:
        return path

    nasm = find_tool("nasm")
    golink = find_tool("golink")
    missing = []
    if nasm is None:
        missing.append("NASM")
    if golink is None:
        missing.append("GoLink")
    if missing:
        raise MakakaError(
            f"не найдены инструменты: {', '.join(missing)}. "
            "Запустите: python tools/setup_tools.py",
            str(path),
        )

    assembly = CodeGenerator(program, functions, str(path), source).generate()
    asm_path = path.with_suffix(".asm")
    exe_path = path.with_suffix(".exe")
    asm_path.write_text(assembly, encoding="utf-8", newline="\n")

    # У NASM для Windows есть проблемы с кириллицей в именах файлов. Поэтому
    # инструменты получают короткие ASCII-имена, а готовый exe копируется Python.
    with tempfile.TemporaryDirectory(prefix="build_", dir=ROOT / "tools") as temporary:
        work = Path(temporary)
        work_asm = work / "program.asm"
        work_obj = work / "program.obj"
        work_exe = work / "program.exe"
        work_asm.write_text(assembly, encoding="utf-8", newline="\n")
        nasm_command = str(nasm)
        golink_command = str(golink)
        commands = [
            [nasm_command, "-f", "win64", work_asm.name, "-o", work_obj.name],
            [
                golink_command,
                "/console",
                "/entry:start",
                f"/fo:{work_exe.name}",
                work_obj.name,
                "kernel32.dll",
            ],
        ]
        for command in commands:
            try:
                result = subprocess.run(
                    command,
                    cwd=work,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError as error:
                raise MakakaError(
                    f"не удалось запустить инструмент сборки: {error}", str(path)
                ) from error
            if result.returncode != 0:
                output = result.stdout.strip()
                raise MakakaError(
                    "сбой ассемблера или компоновщика"
                    + (f"\n{output}" if output else ""),
                    str(path),
                )
        shutil.copyfile(work_exe, exe_path)
    return exe_path


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="makaka",
        description="Компилятор Makakalang: .mkk → NASM x86-64 → Windows .exe",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("build", "собрать .asm и .exe"),
        ("run", "собрать и сразу запустить программу"),
        ("check", "проверить синтаксис и имена без сборки"),
    ):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("source", type=Path, help="путь к файлу .mkk")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = create_argument_parser().parse_args(argv)
    try:
        if args.command == "check":
            compile_source(args.source, check_only=True)
            print(f"Проверка завершена: {args.source}")
            return 0
        executable = compile_source(args.source)
        print(f"Создан исполняемый файл: {executable}", flush=args.command == "run")
        if args.command == "run":
            completed = subprocess.run([str(executable.resolve())])
            return completed.returncode
        return 0
    except MakakaError as error:
        print(error, file=sys.stderr)
        return 1
    except OSError as error:
        print(f"Ошибка файловой системы: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
