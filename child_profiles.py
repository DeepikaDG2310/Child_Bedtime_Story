import json
import os
from dataclasses import dataclass

PROFILES_FILE = os.path.join(os.path.dirname(__file__), "child_profiles.json")


@dataclass
class ChildProfile:
    name: str
    age: int                          
    last_theme: str = "✨ Surprise me!"


def load_profiles() -> dict[str, ChildProfile]:
    """Load all saved child profiles from disk."""
    if not os.path.exists(PROFILES_FILE):
        return {}
    try:
        with open(PROFILES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            name: ChildProfile(name=name, age=info["age"], last_theme=info.get("last_theme", "✨ Surprise me!"))
            for name, info in data.items()
        }
    except (json.JSONDecodeError, KeyError):
        return {}


def save_profile(profile: ChildProfile) -> None:
    """Persist a child profile, creating or updating by name."""
    profiles = load_profiles()
    profiles[profile.name] = profile
    _write(profiles)


def delete_profile(name: str) -> None:
    """Remove a saved profile by name."""
    profiles = load_profiles()
    profiles.pop(name, None)
    _write(profiles)


def _write(profiles: dict[str, ChildProfile]) -> None:
    with open(PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {name: {"age": p.age, "last_theme": p.last_theme} for name, p in profiles.items()},
            f,
            indent=2,
        )
