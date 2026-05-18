class PersonalityEngine:
    def __init__(self):
        self.mood = "annoyed"
        self.DETERMINISTIC_REACTIONS = {
            "git push": "deploying straight to production. i too enjoy gambling.",
            "npm install": "downloading 900 packages to center a div. magnificent.",
            "docker compose": "containers inside containers inside suffering.",
            "git status": "you changed 14 files and fear absolutely none of them.",
            "clear": "*stares blankly* cleaning your screen won't clean your messy logic, dummy."
        }

    def get_quick_reaction(self, cmd: str) -> str:
        cmd_clean = cmd.strip().lower()
        for trigger, text in self.DETERMINISTIC_REACTIONS.items():
            if trigger in cmd_clean: return text
        return ""

    def format_passive_tip(self, traceback_context: str) -> str:
        tb = traceback_context.lower()
        if "syntaxerror" in tb: return "your syntax is broken. look at where you missed a closing bracket, idiot."
        if "nameerror" in tb: return "referencing an unassigned variable. it doesn't exist, just like your code optimization."
        return "that stack trace has side quests. fix the execution logic, dummy."