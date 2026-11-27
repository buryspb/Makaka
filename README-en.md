# Makakalang — as simple as BASIC

**Makakalang** is a language for writing your first programs. Commands use ordinary Russian words. Parentheses, colons, commas, and symbolic comparison operators are optional.

```python
печать "Привет, мир!"
```

Save this as `privet.mkk` in UTF-8, then run:

```bat
makaka run privet.mkk
```

That is all — you have created a real Windows application.

> **Note:** Makakalang keywords are intentionally Russian. This guide is in English, but the source code keeps the original Russian syntax.

## Quick start

You need 64-bit Windows and Python 3.10 or newer. Portable copies of NASM and GoLink are already included in `tools/bin`; no installation or additional configuration is required.

From the project root:

```bat
makaka build examples\hello.mkk
examples\hello.exe

makaka run examples\calculator.mkk
makaka run examples\guess_number.mkk
```

`build` creates `.asm` and `.exe` files next to the `.mkk` source file. `run` builds the program and starts it immediately. `check` validates the source without building it:

```bat
makaka check privet.mkk
```

If the bundled tools have been deleted, restore them with:

```bat
python tools\setup_tools.py
```

## 1. Talking to your program

### Print text

```python
печать "Привет!"
печать "Мне нравится Makaka"
```

### Ask for a name

```python
имя = ввод "Как тебя зовут?"
печать "Привет," имя
```

Items after `печать` are automatically separated by spaces. You do not need commas.

### Ask for a number

`ввод` reads a string. `число` converts it to an integer:

```python
возраст = число ввод "Сколько тебе лет?"
печать "Твой возраст:" возраст
```

## 2. Making simple decisions

Comparisons are written as words:

| Keyword | Meaning |
|---|---|
| `равно` | values are equal |
| `не_равно` | values are not equal |
| `меньше` | the left value is less than the right value |
| `больше` | the left value is greater than the right value |
| `не_меньше` | greater than or equal to |
| `не_больше` | less than or equal to |

For example:

```python
возраст = число ввод "Сколько тебе лет?"

если возраст не_меньше 18
    печать "Ты взрослый"
иначе_если возраст не_меньше 5
    печать "Ты уже большой"
иначе
    печать "Ты ещё совсем маленький"
```

Indent each command inside a conditional block with four spaces. The indentation shows which commands belong to that block.

More examples:

```python
если ответ равно "да"
    печать "Здорово!"

если секрет не_равно 7
    печать "Попробуй ещё"

если очки больше 100
    печать "Победа!"
```

## 3. Repeating commands

`пока` repeats commands while its condition is true:

```python
счёт = 5

пока счёт больше 0
    печать счёт
    счёт = счёт - 1

печать "Пуск!"
```

`прервать` exits a loop early. `продолжить` immediately starts the next iteration:

```python
число = 0

пока число меньше 10
    число = число + 1
    если число равно 3
        продолжить
    если число равно 8
        прервать
    печать число
```

## 4. Creating your own commands — functions

A function accepts values and returns a result. Parameter names are separated by spaces:

```python
функция сложить а б
    вернуть а + б

ответ = сложить 2 3
печать "Два плюс три:" ответ
```

You can also print the result directly:

```python
печать "Ответ:" сложить 10 20
```

Functions may be called before their declaration. Recursion is supported. A function without `вернуть` returns `Ничего` (`Nothing`).

## 5. A small game

```python
секрет = 7
ответ = 0

пока ответ не_равно секрет
    ответ = число ввод "Угадай число: "
    если ответ меньше секрет
        печать "Больше!"
    иначе_если ответ больше секрет
        печать "Меньше!"
    иначе
        печать "Ты угадал!"
```

## Values and calculations

```python
число = 42
текст = "Привет"
правда = Истина
ложь = Ложь
```

- Integers are signed 64-bit values.
- Strings use UTF-8 and may be enclosed in double or single quotes.
- A comment starts with `#` and continues to the end of the line.
- `+` adds numbers or concatenates strings.
- `-`, `*`, `/`, and `%` perform subtraction, multiplication, division, and remainder operations.
- `и`, `или`, and `не` mean logical AND, OR, and NOT.

```python
имя = "Алиса"
печать "Привет, " + имя + "!"

если Истина и не Ложь
    печать "Работает"
```

Zero, an empty string, `Ложь` (`False`), and `Ничего` (`Nothing`) are considered false. All other values are considered true. Division is integer division. Division by zero, integer overflow, and incompatible types produce clear error messages in Russian.

Use `проход` for an empty block:

```python
если Истина
    проход
```

## Can I still use the old syntax?

Yes. Existing programs remain compatible. Parentheses, commas, colons, and symbolic comparison operators are still accepted:

```python
функция сложить(а, б):
    вернуть а + б

если сложить(2, 3) == 5:
    печать("Старый вариант тоже работает")
```

For new programs, words and spaces are usually simpler.

## Exact operator precedence

From lowest to highest:

1. `или` — OR;
2. `и` — AND;
3. `не` — NOT;
4. word-based comparisons;
5. `+`, `-`;
6. `*`, `/`, `%`;
7. unary `+`, `-`;
8. calls and optional parentheses.

In a call without parentheses, each argument is a single simple operand. Therefore, `сложить 2 3 равно 5` means “the result of the call is equal to five.” Optional parentheses can be used for a complex argument: `сложить (а + 1) б`.

## Tooling reference

Executables depend only on the Windows system library `kernel32.dll`. At startup, they automatically call `SetConsoleOutputCP(65001)` and `SetConsoleCP(65001)`, so Russian text works without running `chcp`.

Project layout:

```text
compiler/       lexer, parser, AST, semantic analysis, and NASM generator
examples/       ready-to-run example programs
makaka.py       command-line interface
makaka.bat      launcher for cmd.exe
tools/bin/      portable NASM and GoLink
tests/          automated tests
```

Run the tests with:

```bat
python -m unittest discover -s tests -v
```

MVP limitation: memory allocated for dynamic strings is released by the operating system when the process exits.
