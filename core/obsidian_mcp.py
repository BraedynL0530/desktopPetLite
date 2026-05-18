import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from core.config import OBSIDIAN_VAULT_PATH

class ObsidianMCP:
    def __init__(self, vault_path: str = None):
        p = vault_path if vault_path else OBSIDIAN_VAULT_PATH
        self.vault_path = Path(p) if p else None
        self.available = False

        if self.vault_path and self.vault_path.exists():
            self.daily_dir = self.vault_path / "Daily"
            self.plans_dir = self.vault_path / "Plans"
            self.summaries_dir = self.vault_path / "Summaries"

            self.daily_dir.mkdir(parents=True, exist_ok=True)
            self.plans_dir.mkdir(parents=True, exist_ok=True)
            self.summaries_dir.mkdir(parents=True, exist_ok=True)
            self.available = True

    def get_today_note(self) -> Optional[str]:
        if not self.available: return None
        today = datetime.now().strftime("%Y-%m-%d")
        note_path = self.daily_dir / f"{today}.md"
        if note_path.exists(): return note_path.read_text()

        template = f"# {today}\n\n## Todo\n- \n\n## Done\n- \n\n## Notes\n- \n"
        try:
            note_path.write_text(template)
            return template
        except Exception: return None

    def add_todo(self, item: str) -> bool:
        if not self.available: return False
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            note_path = self.daily_dir / f"{today}.md"
            content = note_path.read_text() if note_path.exists() else (self.get_today_note() or "")
            lines = content.split("\n")
            todo_idx = -1
            for i, line in enumerate(lines):
                if "## Todo" in line:
                    todo_idx = i
                    break
            if todo_idx >= 0:
                lines.insert(todo_idx + 1, f"- [ ] {item}")
                note_path.write_text("\n".join(lines))
                return True
            return False
        except Exception: return False

    def add_plan(self, plan_name: str, plan_content: str, graph_data: Optional[dict] = None) -> bool:
        if not self.available: return False
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            plan_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            plan_file = self.plans_dir / f"{plan_id}_{plan_name.replace(' ', '_')}.md"
            plan_text = f"# {plan_name}\n**Created**: {timestamp}\n\n## Plan\n{plan_content}\n\n## Status\n- [ ] Started\n- [ ] In Progress\n- [ ] Completed\n\n## Metadata\n- id: {plan_id}\n"
            if graph_data:
                plan_text += f"\n## Data\n```json\n{json.dumps(graph_data, indent=2)}\n```"
            plan_file.write_text(plan_text)
            return True
        except Exception: return False

    def create_daily_summary(self, llm_client, today_content: Optional[str] = None) -> bool:
        if not self.available: return False
        try:
            if not today_content: today_content = self.get_today_note() or ""
            today = datetime.now().strftime("%Y-%m-%d")
            summary_file = self.summaries_dir / f"{today}_summary.md"

            summary_prompt = f"summarize this day's work log in 2-3 bullet points. then list 3 todos for tomorrow. be sarcastic. don't use markdown formatting, just plain text.\n\n{today_content}"
            summary = llm_client.ask_cat(summary_prompt, model_override="llama-3.3-70b-versatile")

            summary_content = f"# Summary - {today}\n\n## Summary\n{summary}\n\n## Tomorrow\n- [ ] \n- [ ] \n- [ ] \n"
            summary_file.write_text(summary_content)
            return True
        except Exception: return False