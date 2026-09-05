import re
from pathlib import Path

import yaml

from .state import digest


class SkillRegistry:
    """Versioned Agent Skills with metadata-first loading and task-local audit events."""

    def __init__(self, root=None):
        self.root = Path(root) if root else Path(__file__).parent / "skills"
        self._skills = {}
        for path in sorted(self.root.glob("*/SKILL.md")):
            raw = path.read_text()
            parts = raw.split("---", 2)
            if len(parts) != 3 or parts[0].strip():
                raise ValueError(f"Invalid frontmatter: {path.name}")
            metadata = yaml.safe_load(parts[1])
            name = metadata["name"]
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or name != path.parent.name:
                raise ValueError("Skill name must match its directory")
            if not isinstance(metadata.get("description"), str):
                raise ValueError("Skill description is required")
            self._skills[name] = {
                "name": name,
                "description": metadata["description"],
                "instructions": parts[2].strip(),
                "sha256": digest(raw),
            }
        if not self._skills:
            raise ValueError("No skills found")

    @property
    def fingerprint(self):
        return digest({k: v["sha256"] for k, v in self._skills.items()})

    def metadata(self):
        return [{k: s[k] for k in ("name", "description", "sha256")} for s in self._skills.values()]

    def load(self, name):
        if name not in self._skills:
            raise ValueError("Unknown skill")
        return dict(self._skills[name])

    def full_context(self):
        return list(self._skills.values())
