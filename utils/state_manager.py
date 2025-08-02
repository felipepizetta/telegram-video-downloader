from pathlib import Path
import json
import logging

class StateManager:
    def __init__(self):
        self.state_file = Path("config/download_state.json")
        self.state_file.parent.mkdir(exist_ok=True)
        self._state = {"processed_videos": {}, "remaining_videos": 0}

    def load_state(self):
        if self.state_file.exists():
            try:
                with self.state_file.open('r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logging.error(f"Failed to decode state file: {str(e)}")
                return {"processed_videos": {}, "remaining_videos": 0}
        return {"processed_videos": {}, "remaining_videos": 0}

    def save_state(self):
        try:
            with self.state_file.open('w', encoding='utf-8') as f:
                json.dump(self._state, f)
        except Exception as e:
            logging.error(f"Failed to save state: {str(e)}")

    def mark_processed(self, message_id, filename):
        self._state["processed_videos"][message_id] = filename
        self._state["remaining_videos"] -= 1

    def get_processed_videos(self):
        return self._state["processed_videos"]

    def clear_state(self):
        self._state = {"processed_videos": {}, "remaining_videos": 0}
        if self.state_file.exists():
            self.state_file.unlink()