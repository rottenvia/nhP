
import os
import sys
import subprocess
import shutil
from pathlib import Path


def tail_text(text, lines=90):
    parts = (text or "").splitlines()
    return "\n".join(parts[-lines:])


def run_build_command(cmd, log_path):
    print(f"[Команда] {' '.join(cmd)}\n")
    proc = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace"
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(proc.stdout or "", encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        print("\n❌ PyInstaller вернул ошибку. Последние строки лога:")
        print("-" * 70)
        print(tail_text(proc.stdout, 100))
        print("-" * 70)
        print(f"Полный лог сохранён здесь: {log_path}")
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    print(proc.stdout)


def compile_player():
    print("==================================================")
    print("        Сборщик Modern Media Player в EXE        ")
    print("==================================================")

    project_dir = Path(__file__).resolve().parent
    os.chdir(project_dir)

    # 1. Проверяем наличие необходимых пакетов в системе
    required_packages = ["pyinstaller", "pywebview", "bottle"]
    for pkg in required_packages:
        try:
            if pkg == "pywebview":
                import webview  # noqa
            elif pkg == "pyinstaller":
                import PyInstaller  # noqa
            else:
                __import__(pkg)
        except ImportError:
            print(f"-> Пакет '{pkg}' не найден. Устанавливаем через pip...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
                print(f"✓ '{pkg}' успешно установлен!")
            except Exception as e:
                print(f"❌ Ошибка установки пакета '{pkg}': {e}")
                print("Попробуйте установить его вручную: pip install " + pkg)
                sys.exit(1)

    # 2. Пути сборки. Build/spec/log уводим из корня в data/, dist оставляем как понятный output.
    path_separator = ';' if os.name == 'nt' else ':'
    # IMPORTANT: when --specpath is outside root, relative add-data paths are resolved from spec folder.
    # Use absolute source path so PyInstaller always finds project templates/.
    templates_src = project_dir / "templates"
    add_data_value = f"{templates_src}{path_separator}templates"

    data_dir = project_dir / "data"
    workpath = data_dir / "pyinstaller" / "build"
    specpath = data_dir / "pyinstaller" / "spec"
    log_path = data_dir / "logs" / "pyinstaller_build.log"
    distpath = project_dir / "dist"

    workpath.mkdir(parents=True, exist_ok=True)
    specpath.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Старый/битый spec иногда ломает сборку после переноса. Удаляем перед clean build.
    for spec in [project_dir / "ModernPlayer.spec", specpath / "ModernPlayer.spec"]:
        try:
            if spec.exists():
                spec.unlink()
        except Exception:
            pass

    # 3. Команда сборки. Запускаем через текущий Python, а не через случайный pyinstaller из PATH.
    base_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        "--name", "ModernPlayer",
        "--hidden-import", "nohomo_merger_core",
        "--hidden-import", "libtorrent",
        f"--add-data={add_data_value}",
        "--clean",
        "--workpath", str(workpath),
        "--specpath", str(specpath),
        "--distpath", str(distpath),
        str(project_dir / "app.py")
    ]

    print("\n[Инфо] Запускаем компиляцию проекта...")
    print(f"[Инфо] Project: {project_dir}")
    print(f"[Инфо] Build cache: {workpath}")
    print(f"[Инфо] Spec path: {specpath}")
    print(f"[Инфо] Dist path: {distpath}")

    try:
        try:
            run_build_command(base_cmd, log_path)
        except subprocess.CalledProcessError:
            # Если проблема только в libtorrent hook/пакете, даём автоматический fallback.
            # Сам app.py всё равно умеет работать без libtorrent через qBittorrent/.torrent fallback.
            log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
            if "libtorrent" in log.lower():
                print("\n[Fallback] Сборка споткнулась на libtorrent. Пробуем собрать без hidden-import libtorrent...")
                fallback_cmd = []
                skip_next = False
                for i, item in enumerate(base_cmd):
                    if skip_next:
                        skip_next = False
                        continue
                    if item == "--hidden-import" and i + 1 < len(base_cmd) and base_cmd[i + 1] == "libtorrent":
                        skip_next = True
                        continue
                    fallback_cmd.append(item)
                run_build_command(fallback_cmd, log_path)
            else:
                raise

        print("\n==================================================")
        print("✓ КОМПИЛЯЦИЯ УСПЕШНО ЗАВЕРШЕНА!")
        print("==================================================")

        exe_ext = ".exe" if os.name == 'nt' else ""
        exe_path = distpath / f"ModernPlayer{exe_ext}"

        print(f"-> Готовый файл: {exe_path}")
        print("-> Запускайте именно этот файл после сборки.")
        print("==================================================")

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Ошибка компиляции PyInstaller: {e}")
        print(f"Полный лог: {log_path}")
        print("Если будешь присылать ошибку — пришли последние 40-80 строк из этого файла.")
        sys.exit(1)
    except FileNotFoundError:
        print("\n❌ Ошибка: PyInstaller не найден.")
        print("Попробуй: python -m pip install --upgrade pyinstaller")
        sys.exit(1)


if __name__ == "__main__":
    compile_player()
