#!/usr/bin/env python3
"""Загружает портативные NASM и GoLink только в каталог проекта."""

from __future__ import annotations

import io
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "tools" / "bin"
DOWNLOADS = {
    "nasm.exe": (
        "https://www.nasm.us/pub/nasm/releasebuilds/3.01/win64/nasm-3.01-win64.zip",
        "nasm-3.01/nasm.exe",
    ),
    "GoLink.exe": (
        "https://www.godevtool.com/Golink.zip",
        "GoLink.exe",
    ),
}


def install(name: str, url: str, member: str) -> None:
    print(f"Загрузка {name}...")
    request = urllib.request.Request(url, headers={"User-Agent": "Makakalang-Setup/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        archive = response.read()
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        try:
            content = zipped.read(member)
        except KeyError:
            matches = [item for item in zipped.namelist() if item.endswith("/" + name)]
            if not matches:
                raise RuntimeError(f"В архиве не найден {member}")
            content = zipped.read(matches[0])
    BIN.mkdir(parents=True, exist_ok=True)
    (BIN / name).write_bytes(content)
    print(f"Установлено: {BIN / name}")


def main() -> int:
    if shutil.which("nasm") and (shutil.which("GoLink") or shutil.which("golink")):
        print("NASM и GoLink уже доступны в PATH; загрузка не требуется.")
        return 0
    for name, (url, member) in DOWNLOADS.items():
        if (BIN / name).is_file():
            print(f"Уже установлен: {BIN / name}")
            continue
        install(name, url, member)
    version = subprocess.run(
        [str(BIN / "nasm.exe"), "-v"], capture_output=True, text=True, check=True
    )
    print(version.stdout.strip())
    print("Инструменты готовы. Изменять PATH не требуется.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
