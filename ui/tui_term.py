import os
import sys
import time
import psutil
from core.config import LOCK_FILE, CAT_NAME
from core.personality import PersonalityEngine
from core.shell_engine import PersistentShell
from core.llm_client import LintLLMClient
from core.obsidian_mcp import ObsidianMCP


class NativeTerminalTUI:
    def __init__(self):
        self.personality = PersonalityEngine()
        self.shell = PersistentShell(tui_callback=self.async_passive_lint_print)
        self.llm = LintLLMClient()
        self.obsidian = ObsidianMCP()
        self.cat_bubble = "sandbox engine online. ready to burn code on the pi."
        self.task_count = "4/5"

    def acquire_lock(self):
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))

    def release_lock(self):
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)

    def async_passive_lint_print(self, lint_tip: str):
        self.cat_bubble = lint_tip
        sys.stdout.write("\033[s")
        sys.stdout.write("\033[7A\033[G")
        sys.stdout.write(f"    /\\_/\\    ( {self.cat_bubble.ljust(54)} )\n")
        sys.stdout.write("\033[u")
        sys.stdout.flush()

    def draw_static_box(self):
        os.system('cls' if sys.platform == 'win32' else 'clear')
        print("\n\n\n")
        print(f"  [ {CAT_NAME.capitalize()} ]---------------------------------------------------------------------+")
        print(
            f"  | CPU: --% | Tasks: {self.task_count} | Sync: {'CONNECTED' if self.obsidian.available else 'DISABLED'.ljust(9)} |")
        print(f"  +-------------------------------------------------------------------------+")

    def play_localized_hop(self):
        frames = [
            ["       ", "       ", " /\\_/\\ "],
            ["       ", " /\\_/\\ ", " ( o.o )"],
            [" /\\_/\\ ", " ( o.o )", " > ^ < "]
        ]
        frame_delay = 0.157
        for frame in frames:
            sys.stdout.write("\033[7A\033[G")
            sys.stdout.write(f"   {frame[0]}   ( {self.cat_bubble.ljust(54)} )\n")
            sys.stdout.write(f"  {frame[1]}  (                                                              )\n")
            sys.stdout.write(f"   {frame[2]}  / \n")
            sys.stdout.write("\033[4B")
            sys.stdout.flush()
            time.sleep(frame_delay)

    def draw_live_dashboard(self):
        cpu = psutil.cpu_percent()
        sys.stdout.write("\033[3A\033[G")
        sys.stdout.write(
            f"  | CPU: {str(cpu).ljust(2)}% | Tasks: {self.task_count} | Sync: {'CONNECTED' if self.obsidian.available else 'DISABLED'.ljust(9)} |\n")
        sys.stdout.write("\033[2B\033[G")
        sys.stdout.flush()

    def repaint_static_pose(self):
        sys.stdout.write("\033[7A\033[G")
        sys.stdout.write(f"    /\\_/\\    ( {self.cat_bubble.ljust(54)} )\n")
        sys.stdout.write(f"   ( o.o )  (                                                              )\n")
        sys.stdout.write(f"   > ^ <  / \n")
        sys.stdout.write("\033[4B")
        sys.stdout.flush()

    def run_loop(self):
        self.acquire_lock()
        self.draw_static_box()
        self.play_localized_hop()

        while True:
            self.draw_live_dashboard()
            print(" instructions: execute native commands, or query using context prompts.")
            # FIXED: Updated instructions so you don't think you need to type "cat >>>" twice
            print(" agentic sandbox loop:  sandbox <your explicit modification request instructions>")
            print(" type 'exit' to cleanly return focus back to the desktop pet GUI panel.\n")

            try:
                user_input_raw = input("cat >>> ")
            except (KeyboardInterrupt, EOFError):
                break

            # SANITIZATION DECK
            user_input = user_input_raw.replace('\xa0', ' ').replace('\t', ' ').strip()

            if not user_input:
                continue
            if user_input.lower() == "exit":
                print("*hops back down out of the terminal environment*")
                time.sleep(0.5)
                break

            # STRIP ACCIDENTAL PROMPT PASTES
            # Just in case you still habitually copy-paste "cat >>> sandbox" into the prompt
            clean_input = user_input
            if clean_input.lower().startswith("cat >>>"):
                clean_input = clean_input[7:].strip()
            elif clean_input.lower().startswith("cat>>>"):
                clean_input = clean_input[6:].strip()

            lower_cmd = clean_input.lower()

            # THE REAL FIX: Check for the actual command words, since "cat" isn't in your text!
            is_ai_task = (
                    lower_cmd.startswith("sandbox") or
                    lower_cmd.startswith("modify") or
                    lower_cmd.startswith("obsidian") or
                    lower_cmd.startswith("cat ")
            )

            if is_ai_task:
                if lower_cmd.startswith("modify"):
                    task = clean_input[6:].strip().lstrip(",").strip()
                    print("\n[!] lint taking operational context control of directories...")
                    self.cat_bubble = self.llm.run_multi_file_agent(task)

                elif lower_cmd.startswith("sandbox"):
                    task_instruction = clean_input[7:].strip().lstrip(",").strip()

                    if task_instruction.lower() == "accept":
                        print("\n[!] executing remote synchronization path sequence pull...")
                        from core.pi_agent import PiDevBridge
                        bridge = PiDevBridge()
                        self.cat_bubble = bridge.pull_remote_mutations()
                    if not task_instruction:
                        self.cat_bubble = "type what you want me to build and test inside the sandbox, dummy."
                    else:
                        print("\n[!] connecting via password credentials to remote pi sandbox...")
                        from core.pi_agent import PiDevBridge
                        bridge = PiDevBridge()
                        self.cat_bubble = bridge.run_agentic_sandbox(task_instruction,
                                                                     run_cmd="python3 launcher.py --help")

                elif lower_cmd.startswith("obsidian"):
                    task = clean_input[8:].strip()
                    if task.startswith("daily"):
                        self.obsidian.get_today_note()
                        success = self.obsidian.create_daily_summary(self.llm)
                        self.cat_bubble = "*purrs* daily log note pushed into vault." if success else "failed note compile."
                    else:
                        self.cat_bubble = "unknown obsidian command."

                else:  # Starts with "cat " (for random chatting)
                    chat_query = clean_input[4:].strip()
                    print("*calculating metrics via groq*...")
                    self.cat_bubble = self.llm.ask_cat(chat_query, model_override="llama-3.3-70b-versatile")

                self.draw_static_box()
                self.repaint_static_pose()
                continue  # Ironclad block preventing PowerShell from ever seeing it

            # ─── ROUTE B: PROCESS STANDARD NATIVE CMD LINE SHELL ───
            quick_check = self.personality.get_quick_reaction(user_input)
            if quick_check:
                self.cat_bubble = quick_check

            print(f"\nExecuting: {user_input}")
            out = self.shell.execute_command(user_input)
            print(out)

            input("\n[press enter to clear terminal context]")
            self.draw_static_box()
            self.repaint_static_pose()

        self.release_lock()


if __name__ == "__main__":
    tui = NativeTerminalTUI()
    tui.run_loop()