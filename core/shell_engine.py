import os
import sys
import subprocess
import threading
import queue
import time
from core.personality import PersonalityEngine


class PersistentShell:
    def __init__(self, tui_callback=None):
        cmd = ["powershell.exe", "-NoExit", "-Command",
               "$OutputEncoding = [System.Text.Encoding]::UTF8"] if sys.platform == "win32" else ["/bin/bash",
                                                                                                  "--login"]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, bufsize=1)
        self.q = queue.Queue()
        self.personality = PersonalityEngine()
        self.tui_callback = tui_callback

        # Passive Linting Debounce Trackers
        self.last_activity_time = time.time()
        self.last_captured_output = ""
        self.timer_lock = threading.Lock()

        # Start Threads
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._passive_lint_debounce_worker, daemon=True).start()

    def _read(self):
        while True:
            line = self.proc.stdout.readline()
            if not line: break
            self.q.put(line)

    def execute_command(self, cmd_str: str) -> str:
        with self.timer_lock:
            self.last_activity_time = time.time()  # Reset on command execution

        self.proc.stdin.write(cmd_str + "\n")
        self.proc.stdin.flush()
        time.sleep(0.25)

        lines = []
        while not self.q.empty():
            lines.append(self.q.get_nowait())

        output = "".join(lines)

        with self.timer_lock:
            self.last_captured_output = output

        return output

    def _passive_lint_debounce_worker(self):
        """Monitors system idle state. Triggers passive linting only after 15s of pure silence."""
        while True:
            time.sleep(1.0)
            with self.timer_lock:
                current_idle = time.time() - self.last_activity_time
                if 15.0 <= current_idle < 16.0 and self.last_captured_output:
                    # Look for system failures or bad execution formatting traces
                    if any(i in self.last_captured_output.lower() for i in ["error", "fail", "traceback", "exception"]):
                        tip = self.personality.format_passive_tip(self.last_captured_output)
                        self.last_captured_output = ""  # Consume the output
                        if self.tui_callback:
                            self.tui_callback(tip)