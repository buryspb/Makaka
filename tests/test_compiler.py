from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

from compiler.cli import compile_source
from compiler.errors import MakakaError
from compiler.parser import Parser
from compiler.semantic import SemanticAnalyzer


ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "tests" / "_work"


def run_executable(path: Path, input_text: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(path)],
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )


class CompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        WORK.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(WORK, ignore_errors=True)

    def compile_program(self, name: str, source: str) -> Path:
        path = WORK / f"{name}.mkk"
        path.write_text(source, encoding="utf-8")
        return compile_source(path)

    def test_language_features(self) -> None:
        executable = self.compile_program(
            "features",
            '''функция факториал(н):
    если н <= 1:
        вернуть 1
    вернуть н * факториал(н - 1)

функция пусто():
    проход

печать("арифметика:", 7 / 2, -7 / 2, -7 % 3, 2 + 3 * 4)
печать("границы:", 9223372036854775807, -9223372036854775808)
печать("строки:", "Мака" + "ка", "а" < "б", "а" != "б")
печать("логика:", не Ложь, Ложь и (1 / 0 == 0), Истина или (1 / 0 == 0))
печать("факториал:", факториал(6))
печать("пустой результат:", пусто())
i = 0
сумма = 0
пока i < 10:
    i = i + 1
    если i % 2 == 0:
        продолжить
    сумма = сумма + i
    если i >= 5:
        прервать
печать("цикл:", i, сумма)
имя = ввод("Имя: ")
число_из_ввода = число(ввод("Число: "))
печать("ввод:", имя, число_из_ввода + 1)
''',
        )
        result = run_executable(executable, "Макака\n  -41  \n")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(
            result.stdout,
            "арифметика: 3 -3 -1 14\n"
            "границы: 9223372036854775807 -9223372036854775808\n"
            "строки: Макака Истина Истина\n"
            "логика: Истина Ложь Истина\n"
            "факториал: 720\n"
            "пустой результат: Ничего\n"
            "цикл: 5 9\n"
            "Имя: Число: ввод: Макака -40\n",
        )

    def test_child_friendly_syntax(self) -> None:
        executable = self.compile_program(
            "simple_syntax",
            '''функция сложить а б
    вернуть а + б

функция ноль
    вернуть 0

печать "сложение:" сложить 2 3
печать "сравнение вызова:" сложить 2 3 равно 5
печать "равно:" 2 = 2
печать "не равно:" 2 не_равно 3
печать "меньше:" 2 меньше 3
печать "больше:" 3 больше 2
печать "не меньше:" 5 не_меньше 5
печать "не больше:" 5 не_больше 5
печать "нулевая функция:" ноль
''',
        )
        result = run_executable(executable)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(
            result.stdout,
            "сложение: 5\n"
            "сравнение вызова: Истина\n"
            "равно: Истина\n"
            "не равно: Истина\n"
            "меньше: Истина\n"
            "больше: Истина\n"
            "не меньше: Истина\n"
            "не больше: Истина\n"
            "нулевая функция: 0\n",
        )

    def test_examples(self) -> None:
        cases = [
            ("hello.mkk", "", "Привет, Алиса!"),
            ("calculator.mkk", "20\n-\n7\n", "Результат: 13"),
            ("guess_number.mkk", "42\n20\n60\n42\n", "Количество попыток: 3"),
        ]
        for filename, input_text, expected in cases:
            with self.subTest(filename=filename):
                source = ROOT / "examples" / filename
                executable = compile_source(source)
                result = run_executable(executable, input_text)
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertIn(expected, result.stdout)

    def test_runtime_errors(self) -> None:
        cases = [
            ("печать(1 / 0)\n", "деление на ноль"),
            ("печать(число(\"двенадцать\"))\n", "не удалось преобразовать"),
            ("печать(9223372036854775807 + 1)\n", "переполнение"),
            ("печать(\"а\" + 1)\n", "оператор '+'"),
        ]
        for index, (source, message) in enumerate(cases):
            with self.subTest(message=message):
                executable = self.compile_program(f"error_{index}", source)
                result = run_executable(executable)
                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stdout)

    def test_compile_errors_have_russian_location(self) -> None:
        path = WORK / "syntax.mkk"
        path.write_text("если Истина\nпечать 1\n", encoding="utf-8")
        with self.assertRaises(MakakaError) as caught:
            compile_source(path)
        self.assertIn(":2:", str(caught.exception))
        self.assertIn("ожидался блок", str(caught.exception))

        path = WORK / "name.mkk"
        path.write_text("печать(неизвестная)\n", encoding="utf-8")
        with self.assertRaises(MakakaError) as caught:
            compile_source(path)
        self.assertIn("переменная 'неизвестная' не определена", str(caught.exception))

    def test_edge_cases_and_unicode_paths(self) -> None:
        unicode_dir = WORK / "путь с пробелом"
        unicode_dir.mkdir()
        source = unicode_dir / "привет.mkk"
        source.write_text('печать("Путь работает")\n', encoding="utf-8")
        executable = compile_source(source)
        result = run_executable(executable)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout, "Путь работает\n")

        executable = self.compile_program(
            "long_input", "строка = ввод()\nпечать(число(ввод()) + 1)\n"
        )
        result = run_executable(executable, "я" * 5000 + "\n41\n")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout, "42\n")

    def test_print_evaluates_arguments_before_output(self) -> None:
        executable = self.compile_program(
            "print_order",
            '''функция побочный():
    печать("функция")
    вернуть 1
печать("результат", побочный())
''',
        )
        result = run_executable(executable)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout, "функция\nрезультат 1\n")

    def test_large_stack_frame(self) -> None:
        assignments = "".join(f"переменная_{index} = {index}\n" for index in range(300))
        executable = self.compile_program(
            "large_frame", assignments + 'печать("кадр:", переменная_299)\n'
        )
        result = run_executable(executable)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout, "кадр: 299\n")

    def test_invalid_numbers_are_diagnostics(self) -> None:
        for index, literal in enumerate(("²", "１２", "9" * 10000, "9223372036854775808")):
            with self.subTest(literal=literal[:30]):
                path = WORK / f"invalid_number_{index}.mkk"
                path.write_text(f"значение = {literal}\n", encoding="utf-8")
                with self.assertRaises(MakakaError):
                    compile_source(path, check_only=True)

    def test_variables_after_terminating_branch(self) -> None:
        executable = self.compile_program(
            "branch_flow",
            '''функция выбрать(условие):
    если условие:
        вернуть 0
    иначе:
        ответ = 42
    печать("ответ:", ответ)
    вернуть ответ
печать(выбрать(Ложь))
''',
        )
        result = run_executable(executable)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout, "ответ: 42\n42\n")

    def test_forward_call_and_return_without_value(self) -> None:
        executable = self.compile_program(
            "forward",
            '''печать(дважды(21))
функция дважды(значение):
    вернуть значение * 2
''',
        )
        result = run_executable(executable)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout, "42\n")


if __name__ == "__main__":
    unittest.main()
