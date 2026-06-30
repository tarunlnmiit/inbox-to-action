"""User-configurable triage settings.

Lets the user override the default "newsletter/job-alert = no action" behavior:
- `triage_instructions`: freeform text injected into the classifier prompt
  (e.g. "I'm job hunting — treat relevant job alerts as action_needed").
- `rules`: deterministic match→category overrides applied BEFORE the LLM
  (fast, free, exact). First matching rule wins.

Sources (in order): explicit path arg → `INBOX_TO_ACTION_CONFIG` env →
`config.json` in the working dir. All optional — a missing file yields defaults
and never errors. `TRIAGE_INSTRUCTIONS` env overrides the file's instructions.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from inbox_to_action.models import CATEGORIES

_RULE_FIELDS = ("sender", "subject", "body", "any")
_DEFAULT_CONFIG_NAME = "config.json"


@dataclass(frozen=True)
class Rule:
    field: str  # one of _RULE_FIELDS
    contains: str
    category: str  # one of CATEGORIES


@dataclass(frozen=True)
class Settings:
    triage_instructions: str = ""
    rules: tuple[Rule, ...] = field(default_factory=tuple)


def _coerce_rules(raw) -> tuple[Rule, ...]:
    """Build valid Rule objects from raw dicts, dropping malformed ones."""
    rules: list[Rule] = []
    if not isinstance(raw, list):
        return ()
    for item in raw:
        if not isinstance(item, dict):
            continue
        fld = str(item.get("field", "any")).strip().lower()
        contains = str(item.get("contains", "")).strip()
        category = str(item.get("category", "")).strip()
        if fld not in _RULE_FIELDS or not contains or category not in CATEGORIES:
            # Skip silently-bad rules rather than crash the whole run.
            continue
        rules.append(Rule(field=fld, contains=contains, category=category))
    return tuple(rules)


def _config_path(path: str | os.PathLike | None) -> Path | None:
    if path:
        return Path(path)
    env = os.environ.get("INBOX_TO_ACTION_CONFIG", "").strip()
    if env:
        return Path(env)
    default = Path(_DEFAULT_CONFIG_NAME)
    return default if default.exists() else None


def load_settings(path: str | os.PathLike | None = None) -> Settings:
    """Load triage settings from config file + env overrides (never raises)."""
    instructions = ""
    rules: tuple[Rule, ...] = ()

    cfg_path = _config_path(path)
    if cfg_path and cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                instructions = str(data.get("triage_instructions", "") or "")
                rules = _coerce_rules(data.get("rules", []))
        except (json.JSONDecodeError, OSError):
            # Bad config shouldn't break triage — fall back to defaults.
            pass

    env_instructions = os.environ.get("TRIAGE_INSTRUCTIONS", "").strip()
    if env_instructions:
        instructions = env_instructions

    return Settings(triage_instructions=instructions.strip(), rules=rules)


def match_rule(sender: str, subject: str, body: str, rules: tuple[Rule, ...]) -> str | None:
    """Return the category of the first matching rule, or None."""
    fields = {"sender": sender, "subject": subject, "body": body}
    for rule in rules:
        haystacks = (
            (sender, subject, body) if rule.field == "any" else (fields[rule.field],)
        )
        needle = rule.contains.lower()
        if any(needle in (h or "").lower() for h in haystacks):
            return rule.category
    return None
