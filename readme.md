Here is the ultimate, production-ready `README.md` for your project workspace. It is fully updated to cover the new sprite sheet layout, file organization, API acquisition, configuration parameters, and multi-file agentic commands.

You can drop this text straight into a file named `README.md` in your project root folder:

```markdown
# 🐾 Lint (or Scratch) — Sarcastic Terminal Cat Companion

Lint is a personality-first developer companion designed to balance deep terminal utility with streamer-friendly entertainment. Lint can operate as a transparent, draggable desktop pet that loops through custom sprite frames, or as an embedded terminal shell wrapper that runs native commands, catches build tracebacks, and executes intelligent multi-file code modifications using Gemini.

---

## 🚀 1. Getting Your Gemini API Key (Step-by-Step)

Lint uses Google Gemini (`gemini-2.0-flash`) to execute smart developer commands and conversational context tracking. The free tier gives you up to 15 Requests per Minute and 1,500 Requests per Day with **no credit card required**.

1. Go to **[aistudio.google.com](https://aistudio.google.com/)**.
2. Sign in with any standard Google account.
3. Click the **"Get API key"** button in the top-left menu sidebar.
4. Click **"Create API key"**, select your default project workspace, and confirm.
5. Copy the generated character string (starts with `AIzaSy...`).
6. Open the `.env` file in your root folder and paste your key cleanly:
   ```ini
   GEMINI_API_KEY=AIzaSyYourActualKeyGoesHere

```

*(Note: Do not wrap your key in quotation marks or leave extra spaces around the `=` sign.)*

---

## 🛠️ 2. First-Time Repository Installation

1. **Unpack the Workspace:**
Execute your workspace builder script to automatically build out the project directories and operational source files:
```bash
python setup_project.py

```


2. **Install Codebox Dependencies:**
Install the ultra-lightweight layout libraries (`PyQt5` for the desktop pet layer, `requests` for remote API handling, and `psutil` for internal hardware mapping):
```bash
pip install -r requirements.txt

```


3. **Wire Up Your Cat PNGs (Optional):**
* Create a folder named `anim` right in your root directory.
* Drop your sprite sheet files directly inside it. The asset manager maps these files exactly:
* `idle.png` (Idle/Base state)
* `lie.png` (Resting state)
* `sleep.png` (Deep sleep state)
* `yawn.png` (Idle fatigue transition)
* `angry2.png` (Aggressive click state)
*(Note: If the `anim/` directory or its assets are missing, Lint safely uses a crisp text-based ASCII cat backup so the interface never crashes.)*





---

## 📂 3. Repository Structure Map

```text
desktopPetV2/
│
├── anim/                   <-- Drop your .png asset sprite sheets here
│   ├── idle.png
│   ├── lie.png
│   ├── sleep.png
│   ├── yawn.png
│   └── angry2.png
│
├── core/                   <-- Logic Engine Processing Framework
│   ├── config.py           <-- Native .env file parsing runtime module
│   ├── llm_client.py       <-- Structural agentic multi-directory client
│   ├── personality.py      <-- Deterministic reaction profiles & clean voice rules
│   └── shell_engine.py     <-- Background persistent interactive shell worker
│
├── ui/                     <-- Core Interface Canvas Layer
│   ├── gui_pet.py          <-- PyQt5 transparent floating window painter
│   └── tui_term.py         <-- Native console terminal dashboard dashboard
│
├── .env                    <-- Local hidden application configurations
├── launcher.py             <-- Application dispatch launcher
├── requirements.txt        <-- Locked production library constraints
│
├── enable_startup.bat      <-- Registers background pet execution to boot routines
├── kill_lint.bat           <-- Total fail-safe application hard termination switch
└── start_lint_background.bat

```

---

## 💻 4. How to Launch & Interact with Lint

### The Native TUI Shell Window (PyCharm Terminal Core)

To open Lint inside an interactive terminal session:

```bash
python launcher.py --tui

```

* **Native Mode:** Type standard console commands (`git status`, `npm install`, `pytest`). Lint will match your inputs against static triggers first to save API tokens and respond with instant snark.
* **Passive Linter Feedback:** If a command returns an explicit traceback (like a `SyntaxError` or `NameError`), Lint automatically triggers a delayed calculation to print out dry, judgmental tips explaining what you messed up.

### The Agentic Programming Commands

To unlock Lint's autonomous file modification capabilities inside the TUI, use the explicit **`cat >>> modify`** string prefix:

```text
cat >>> modify rewrite core/shell_engine.py to print out custom debug statements and refactor error logging

```

* **How it handles directories:** Lint automatically maps your workspace folder tree, evaluates your request, plans file changes across multiple targets, uses `os.makedirs` to create any missing subdirectories on your drive, and safely overwrites the specified files with clean replacement source code.

### The Floating Desktop Pet

To launch Lint as an independent, transparent, draggable window overlay on your screen:

```bash
python launcher.py --gui

```

* **Interactions:** Left-click the cat to drag it anywhere across your monitor workspace. Clicking its sprite strip forces Lint to cycle randomly through its alternative animation profiles (`angry`, `yawn`, `lie`).

---

## ⚙️ 5. Setting Up Automation & Background Triggers

* **Enable Boot Autostart:** Double-click **`enable_startup.bat`**. This generates a secure VBS script that injects a shortcut into your Windows startup system (`shell:startup`). Lint will now boot silently in the background using `pythonw.exe` every time your PC turns on—consuming near-zero idle resources.
* **Coexistence Lock Engine:** The TUI and GUI never fight for screen real estate. When you launch the TUI shell, it creates an atomic lockfile (`.lint_tui.lock`). The GUI instantly reads this file and hides its window from your desktop. As soon as you type `exit` in your terminal shell, the lockfile clears and the desktop pet pops back into view automatically.
* **Force Close/Kill Switch:** If Lint is running silently in the background and you want it completely gone, double-click **`kill_lint.bat`**. This executes an un-throttled task-kill macro targeting all underlying background loaders, handles memory garbage collection, and destroys active workspace lockfiles instantly.

