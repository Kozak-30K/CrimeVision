# CrimeVision
### Intelligent Multimodal Forensic Analysis Platform

CrimeVision is a local-first prototype for organizing digital evidence and running supported analysis workflows on image, video, and audio files. It combines a Flask application with computer-vision and audio-processing libraries, and is designed to present results in a way that can be useful to both technical and non-technical users.

> **Project status:** This repository is a prototype under development. The capabilities available in a particular checkout depend on which routes, services, and frontend workflows are implemented and enabled. Do not treat automated results as proof of a crime or as a substitute for qualified forensic examination.

## Contents

- [Current capabilities and scope](#current-capabilities-and-scope)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Quick start on Ubuntu or WSL 2](#quick-start-on-ubuntu-or-wsl-2)
- [Run the server](#run-the-server)
- [Use CrimeVision](#use-crimevision)
- [Configuration and API keys](#configuration-and-api-keys)
- [Evidence and generated files](#evidence-and-generated-files)
- [Testing and diagnostics](#testing-and-diagnostics)
- [Troubleshooting](#troubleshooting)
- [Security and responsible use](#security-and-responsible-use)
- [Limitations and future work](#limitations-and-future-work)

## Current capabilities and scope

The project environment has been set up with the following components:

- **Flask** for the web application/API.
- **OpenCV** for image and video handling.
- **Ultralytics with PyTorch** for supported object-detection models, including the YOLO and RT-DETR model weights when present.
- **OpenAI Whisper** for audio transcription workflows where the application code invokes it.
- **FFmpeg** for media conversion/processing where required.
- **Optional Groq integration** for features that explicitly call the configured service.

The repository includes code areas for evidence handling, case management, services, utilities, a web interface, tests, and output/report storage. Some components may still be incomplete. A library being installed does not, by itself, mean that a complete user-facing feature has been implemented.

The current development environment was verified using CPU-only PyTorch. A CUDA-capable GPU is **not required** for the basic setup, though processing can be slower on CPU.

## Architecture

The intended high-level flow is:

1. A user opens the browser interface and selects an evidence file or case-related action.
2. The Flask application receives the request and validates/records supported evidence.
3. The relevant service invokes available local processing libraries/models; optional external AI calls occur only in code paths configured to use them.
4. Results and generated artifacts are stored in the project's data/output locations and presented through the application where that workflow is implemented.

This is a **single Flask application with internal modules**, not a deployed microservice cluster. Storage is currently filesystem-based. Authentication, multi-user authorization, production-grade deployment, and a database-backed case store should not be assumed unless they have been added and tested in your version.

## Requirements

- Ubuntu 22.04/24.04 or another supported Linux environment. Windows users can use WSL 2 with Ubuntu.
- Python version compatible with the pinned packages in `requirements.txt`. The development environment has used Python 3.14, but some machine-learning dependencies may not provide compatible wheels for every Python release. If installation fails, use a clean Python 3.11 or 3.12 environment and validate the dependencies against `requirements.txt`.
- `pip` and `venv`.
- FFmpeg for media workflows that need it.
- Git is recommended.
- Sufficient free disk space for Python packages, model weights, and uploaded media.

## Quick start on Ubuntu or WSL 2

### 1. Get the project files

Open a terminal in the project directory. If using a Git repository, clone it and enter the folder:

```bash
git clone <YOUR-REPOSITORY-URL>
cd CrimeVision
```

If you received a ZIP/archive instead, extract it and `cd` into the extracted project folder. Replace the placeholder repository URL with the real URL; do not use it literally.

### 2. Install system dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ffmpeg git
```

If the system Python is not compatible with the dependencies in `requirements.txt`, install/use a compatible Python version separately rather than changing the system Python.

### 3. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

If the project already has a `.venv` directory but it is broken, recreate it only after confirming it contains no files you need:

```bash
deactivate 2>/dev/null || true
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

**Do not delete the project folders or model-weight files when rebuilding `.venv`.** A virtual environment contains installed Python packages; it is not the source code.

### 4. Install Python dependencies

```bash
python -m pip install -r requirements.txt
python -m pip check
```

If an installation error mentions that no compatible distribution exists, check `python --version` and the failing package's supported Python versions. Try Python 3.11 or 3.12 in a new environment if necessary. Avoid installing random versions of PyTorch or other ML libraries without checking compatibility with the project's requirements.

### 5. Configure environment variables

If the application uses environment variables, create a local `.env` file from the example template if one is provided:

```bash
cp .env.example .env
```

Edit `.env` and fill in only the values required by the features you intend to use. If `.env.example` is not present, inspect the configuration code before creating one. A Groq API key is only needed for code paths that call Groq.

**Never commit `.env`, API keys, tokens, or personal evidence to a public repository.** If a key is exposed, revoke it and create a new one.

### 6. Confirm model weights

The development folder has included `yolo11n.pt` and `rtdetr-l.pt`. Keep these files in the location expected by the model-loading code. In the current development layout they have been stored in the project root. If a weight file is missing, inspect the model configuration/code to confirm its expected path before downloading a replacement from a trusted source.

## Run the server

From the project root, with `.venv` activated:

```bash
python run.py
```

The exact host and port are determined by `run.py` and the Flask application configuration. Read the terminal output for the local address, then open that address in a browser.

For WSL 2, a server bound to `127.0.0.1` or `0.0.0.0` is usually accessible from the Windows browser via the printed localhost port. If you want another device on your network to access it, configure the bind address, firewall, and network exposure deliberately; do not expose a development server directly to the public internet.

For a more explicit Flask development invocation, first inspect the application's entry point and configured app import, then use the corresponding Flask command. Do not guess the module path if the repository structure has changed.

## Use CrimeVision

1. Start the server with `python run.py`.
2. Open the address printed in the terminal.
3. Use the available interface to create or select a case, if that workflow is present.
4. Upload only file types supported by the current upload route. The project has evidence directories for images, audio, and video; actual format limits depend on the implemented validation.
5. Start the relevant analysis workflow from the interface. If a workflow is not exposed in the interface, it may exist only as a service or may still be pending.
6. Review the output and its limitations. Preserve original evidence separately and document how any working copy was created.
7. Check the application's output folders and reports area for generated artifacts where applicable.

Do not assume that every modality, report, timeline, or multimodal-fusion workflow is fully implemented just because its folder exists.

## Configuration and API keys

- Keep secrets in a local `.env` file or an equivalent secret-management mechanism.
- Use `.env.example` for variable names and safe placeholder values only.
- Features that use Groq require a valid key and network access. Local object-detection and media-processing paths can run without a Groq key if those paths do not call the external service.
- Never paste API keys into source files, README files, screenshots, or issue reports.

## Evidence and generated files

The project layout includes directories such as:

- `evidence/` — evidence files organized by media type in the development environment.
- `data/uploads/` — uploaded or staged files, depending on the active route.
- `data/processed/` — processed data, where used.
- `outputs/` and `runs/` — analysis artifacts and model outputs.
- `reports/` — report output location, if generated by the active workflow.

The exact storage path depends on the route/service implementation. These folders may contain sensitive material. Do not upload real personal, confidential, or case-related evidence to a public repository. Add local evidence, outputs, caches, `.venv`, `node_modules`, and secrets to `.gitignore` as appropriate.

## Testing and diagnostics

Run the project's prerequisite checker:

```bash
python checker.py
```

Run tests that are present in the checkout:

```bash
python -m pytest -q
```

If `pytest` is not installed, install it in the active virtual environment only if it is part of the project's test setup. A passing import check confirms that dependencies can be imported; it does not prove that every feature works end-to-end.

For an individual model smoke test, use the project's existing test script or UI workflow and a non-sensitive sample image/video/audio file. Do not use confidential evidence for testing.

## Troubleshooting

### `python` or `.venv/bin/python` is missing

Recreate the virtual environment and reinstall requirements as described above. Confirm you are in the project root before running commands.

### A package cannot be installed

Check the Python version and package compatibility. ML packages often lag behind the newest Python release. Try a clean supported Python version in a separate environment and rerun `pip install -r requirements.txt`.

### Model weights cannot be found

Check the path expected by the model-loading code and whether the `.pt` file is present. Do not rename model files unless the code/configuration is updated accordingly.

### FFmpeg-related error

Install FFmpeg using the operating system package manager and verify it is available:

```bash
ffmpeg -version
```

### The web page does not open

Check the terminal for the actual host/port and any Flask errors. Confirm that `python run.py` is still running. Check whether the configured port is already in use.

### CPU processing is slow

CPU-only inference is supported by the development setup but may take longer for large images or long videos. Use small sample files for demos, reduce video resolution/frame sampling where the code supports it, and consider GPU acceleration only after confirming hardware and library compatibility.

## Security and responsible use

- Treat uploaded files as untrusted input and validate file size, extension, content type, and storage names.
- Run the application with least-privilege permissions and keep it bound to localhost for local demos.
- Do not expose Flask's development server to the public internet. Use a production WSGI server, HTTPS, authentication, authorization, and appropriate network controls before any real deployment.
- Preserve originals and maintain a documented chain of custody for forensic use. Hashing, immutable audit logs, access controls, and formal validation should be added before operational use.
- AI detections and transcriptions can be wrong. They are leads for human review, not conclusions about identity, intent, guilt, or legal responsibility.

## Limitations and future work

Potential next steps include a persistent database-backed case store, user authentication and role-based access, background job processing for long media files, file-size and queue limits, audit logging, integrity hashes, reproducible model/version records, automated integration tests, secure production deployment, and a documented evaluation dataset with measured accuracy and performance.

These are proposed enhancements, not claims that the current prototype already provides them.

## License and attribution

Add the project's chosen license and record the licenses/attributions for third-party models, datasets, and libraries before redistribution. Do not assume that every downloaded model weight can be redistributed freely.
