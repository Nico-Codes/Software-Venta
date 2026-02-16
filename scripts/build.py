from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    venv_dir = root / ".venv"

    if platform.system().lower().startswith("win"):
        py = venv_dir / "Scripts" / "python.exe"
    else:
        py = venv_dir / "bin" / "python"

    if not py.exists():
        run([sys.executable, "-m", "venv", str(venv_dir)])

    run([str(py), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(py), "-m", "pip", "install", "-r", str(root / "requirements-dev.txt")])
    run(
        [
            str(py),
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--windowed",
            "--onedir",
            "--name",
            "VentaLocal",
            str(root / "main.py"),
        ]
    )

    if platform.system().lower().startswith("win"):
        print("Build finalizado: dist/VentaLocal/VentaLocal.exe")
    else:
        print("Build finalizado: dist/VentaLocal/VentaLocal")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
