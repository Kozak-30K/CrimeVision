"""
CrimeVision prerequisite checker
Run inside the project's activated Python virtual environment:
    python scripts/check_prerequisites.py

This checks installed software and lightweight import/API configuration only.
It does not download large AI model weights or send requests to Groq.
"""

from __future__ import annotations

import importlib
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"
results: list[tuple[str, str, str]] = []


def report(status: str, name: str, detail: str) -> None:
    results.append((status, name, detail))
    print(f"[{status}] {name}: {detail}")


def check_command(command: str, label: str | None = None) -> bool:
    label = label or command
    path = shutil.which(command)
    if path:
        report(PASS, label, path)
        return True
    report(WARN, label, "not found on PATH")
    return False


def import_check(module_name: str, label: str | None = None) -> bool:
    label = label or module_name
    try:
        module = importlib.import_module(module_name)
        version = getattr(module, "__version__", None)
        extra = f" (version {version})" if version else ""
        report(PASS, label, f"import successful{extra}")
        return True
    except Exception as exc:
        report(FAIL, label, f"import failed: {type(exc).__name__}: {exc}")
        return False


def main() -> int:
    print("=" * 64)
    print("CrimeVision — Prerequisite Check")
    print("=" * 64)

    # Python and virtual environment
    report(PASS, "Python", sys.version.split()[0])
    report(PASS, "Python executable", sys.executable)

    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    if in_venv:
        report(PASS, "Virtual environment", sys.prefix)
    else:
        report(WARN, "Virtual environment",
               "not detected; activate CrimeVision's .venv before installing packages")

    report(PASS, "Operating system", f"{platform.system()} {platform.release()}")

    # Basic tools
    check_command("git", "Git")
    check_command("ffmpeg", "FFmpeg")
    check_command("code", "VS Code CLI (optional in WSL)")

    # Python packages
    import_check("flask", "Flask")
    import_check("flask_cors", "Flask-Cors")
    import_check("cv2", "OpenCV")
    import_check("PIL", "Pillow")
    import_check("torch", "PyTorch")
    import_check("torchvision", "Torchvision")
    import_check("ultralytics", "Ultralytics / RT-DETR support")
    import_check("transformers", "Transformers / image captioning support")
    import_check("sentencepiece", "SentencePiece")
    import_check("whisper", "OpenAI Whisper")
    import_check("groq", "Groq SDK")
    import_check("dotenv", "python-dotenv")
    import_check("numpy", "NumPy")
    import_check("pandas", "Pandas")

    # PyTorch and GPU
    try:
        import torch

        report(PASS, "PyTorch version", torch.__version__)
        report(PASS, "PyTorch CUDA build",
               str(torch.version.cuda) if torch.version.cuda else "CPU-only build")

        try:
            cuda_available = torch.cuda.is_available()
            if cuda_available:
                report(PASS, "CUDA GPU", torch.cuda.get_device_name(0))
                try:
                    test_tensor = torch.rand((2, 2), device="cuda")
                    report(PASS, "GPU tensor test", str(test_tensor.device))
                except Exception as exc:
                    report(FAIL, "GPU tensor test", str(exc))
            else:
                report(WARN, "CUDA GPU",
                       "not available to PyTorch; CPU inference can still work")
        except Exception as exc:
            report(WARN, "CUDA GPU", f"check failed: {exc}")
    except Exception:
        report(FAIL, "PyTorch runtime", "cannot test CUDA because PyTorch import failed")

    # RT-DETR class availability without downloading weights
    try:
        from ultralytics import RTDETR  # noqa: F401
        report(PASS, "RT-DETR class", "available through ultralytics")
    except Exception as exc:
        report(FAIL, "RT-DETR class", f"unavailable: {type(exc).__name__}: {exc}")

    # Environment/configuration checks
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        report(PASS, "Groq API key", "GROQ_API_KEY is set (value not displayed)")
    else:
        report(WARN, "Groq API key",
               "GROQ_API_KEY is not set; add it to .env before using the API")

    # Three.js belongs to the JavaScript frontend, not pip.
    package_json = Path("frontend/package.json")
    if package_json.exists():
        try:
            import json
            package_data = json.loads(package_json.read_text(encoding="utf-8"))
            deps = {
                **package_data.get("dependencies", {}),
                **package_data.get("devDependencies", {}),
            }
            if "three" in deps:
                report(PASS, "Three.js dependency", f"declared in package.json ({deps['three']})")
            else:
                report(WARN, "Three.js dependency",
                       "package.json exists, but 'three' is not declared")
        except Exception as exc:
            report(WARN, "Three.js dependency", f"could not inspect package.json: {exc}")
    else:
        report(WARN, "Three.js dependency",
               "no package.json in current directory; add it when creating the frontend")

    check_command("node", "Node.js (needed for Three.js frontend)")
    check_command("npm", "npm (needed for Three.js frontend)")

    # Summary: warnings are not hard failures; missing required imports are.
    print("\n" + "=" * 64)
    print("SUMMARY")
    print("=" * 64)
    counts = {status: sum(1 for s, _, _ in results if s == status)
              for status in (PASS, WARN, FAIL)}
    print(f"PASS: {counts[PASS]}  WARN: {counts[WARN]}  FAIL: {counts[FAIL]}")

    failures = [name for status, name, _ in results if status == FAIL]
    if failures:
        print("\nFix failed checks before moving to model integration:")
        for name in failures:
            print(f"  - {name}")
        return 1

    print("\nNo required Python import checks failed.")
    print("Warnings may be acceptable depending on your setup (e.g. CPU-only inference).")
    print("Note: model weights/inference and live Groq API access were not tested.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
