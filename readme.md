# desktopPetLite

`desktopPetLite` is a personality-driven desktop companion that runs in two modes:

- **TUI mode** for terminal-first workflows, shell command execution, and agentic commands.
- **GUI mode** for a floating desktop pet rendered with PyQt5.

The project combines a persistent shell, optional LLM-powered editing flows, and a Raspberry Pi sandbox bridge for remote validation before local apply.

## Project Layout

```text
desktopPetLite/
├── anim/                  # Optional pet sprites
├── core/                  # Runtime engines (shell, LLM, Pi bridge, config)
├── ui/                    # TUI and GUI entry components
├── launcher.py            # Main launcher (TUI default, GUI optional)
├── requirements.txt
└── readme.md
```

## Environment Setup

1. Install Python 3.10+.
2. Create and activate a virtual environment.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create `.env` from `ex.env` and populate required values:
   - `GROQ_API_KEY` and/or `GEMINI_API_KEY`
   - `PI_PASSWORD` for Raspberry Pi sandbox workflows
   - Optional UI/config values (`CAT_NAME`, `DEFAULT_MOOD`, `OBSIDIAN_VAULT_PATH`)

## Run Modes

### TUI Mode

```bash
python launcher.py
```

TUI supports:

- **Normal shell commands** (example: `git status`, `python -m pip list`)
- **Agentic commands** routed through built-in command prefixes
- **Sandbox controls** for remote Pi workflows

### GUI Mode

```bash
python launcher.py --gui
```

GUI mode requires a desktop session with display support and PyQt5-compatible runtime dependencies.

## TUI Command Model

### Normal Commands

Any command that does not match an agent command prefix is executed in the persistent shell backend.

### Custom Commands

- `modify <instruction>`: run local multi-file LLM editing flow.
- `sandbox <instruction>`: run Raspberry Pi sandbox agent loop.
- `sandbox accept`: apply pending `.sandbox_mutations.json` changes from Pi to the local project.
- `sandbox clear <confirmation phrase>`: clear remote sandbox workspace contents only when the confirmation phrase is exactly `confirm clear sandbox`.
- `obsidian daily`: run Obsidian daily summary flow.
- `memory show`: display shared memory summary/preview.
- `memory clear`: clear shared memory store.
- `cat <prompt>`: conversational LLM response.

## GUI Agent Controls

GUI mode now includes agent controls:

- `agent` button: run any agent command (`modify ...`, `sandbox ...`, `obsidian daily`, `memory clear/show`)
- `daily` button: quick `obsidian daily`
- `mem clr` button: quick `memory clear`

Long-running agent tasks in GUI run in worker threads so the UI remains responsive.

## Raspberry Pi Agentic Sandbox

The Raspberry Pi bridge (`core/pi_agent.py`) runs an iterative workflow:

1. Upload project archive to `/home/pi/sandbox/workspace`.
2. Execute validation command(s) on Raspberry Pi.
3. Request structured edits from the agent.
4. Write remote mutations and store `.sandbox_mutations.json`.
5. Generate runtime `diff.md` report locally.

### `diff.md` Runtime Report

`diff.md` is generated during sandbox runs and is **not tracked** in git.  
The report includes:

- Task summary
- Human-readable rationale
- Commands executed/requested in sandbox
- JSON parse retry/recovery notes
- Unified diffs (`diff` format) for each changed file

### Acceptance Flow

Remote changes are applied locally only through explicit `sandbox accept`.  
Running `sandbox <instruction>` alone does not directly modify local files.

### SSH Host Key Requirement

Pi bridge connections use strict SSH host-key validation.  
Ensure the Raspberry Pi host key is trusted in local `known_hosts` before running sandbox commands.

## Safety Notes

- Sandbox cleanup requires an explicit confirmation phrase and hard-checks the cleanup path.
- Remote cleanup only targets `/home/pi/sandbox/workspace`.
- Local apply path checks reject writes that escape the repository root.
- Sensitive values (API keys/passwords) are loaded from `.env` and should never be committed.

## Docker Setup

### Build

```bash
docker build -t desktoppetlite .
```

### Run TUI

```bash
docker run --rm -it --env-file .env desktoppetlite
```

### Run with Compose

```bash
docker compose up --build
```

## GUI in Docker (Limitations)

GUI mode generally requires host display forwarding and platform-specific setup (X11/Wayland on Linux, additional tooling on macOS/Windows).  
TUI mode is the recommended default inside containers.

## IDE / Dev Container

A devcontainer configuration is included at `.devcontainer/devcontainer.json` for VS Code compatible environments.  
Open the repository in a devcontainer and run the same launcher commands from the integrated terminal.
