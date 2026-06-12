from __future__ import annotations

from dataclasses import dataclass

from .grimoire import Grimoire
from .script import Script
from .types import GamePhase


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    error: str | None = None


NIGHT_TARGET_COUNTS: dict[str, tuple[int, int]] = {
    "poisoner": (1, 1),
    "imp": (1, 1),
    "monk": (1, 1),
    "fortune_teller": (2, 2),
    "ravenkeeper": (1, 1),
    "butler": (1, 1),
}


class ActionValidator:
    def __init__(self, script: Script) -> None:
        self.script = script

    def validate_night_action(
        self,
        grimoire: Grimoire,
        actor_id: str,
        role_id: str,
        targets: tuple[str, ...],
    ) -> ValidationResult:
        if grimoire.phase not in {GamePhase.FIRST_NIGHT, GamePhase.NIGHT}:
            return ValidationResult(False, "night actions can only be submitted at night")
        if actor_id not in grimoire.players or actor_id not in grimoire.assignments:
            return ValidationResult(False, "unknown actor")
        if actor_id in grimoire.night_actions:
            return ValidationResult(False, "night action already submitted")

        assignment = grimoire.assignments[actor_id]
        if not assignment.is_alive and assignment.visible_role_id != "ravenkeeper":
            return ValidationResult(False, "dead players cannot submit this night action")
        if role_id != assignment.visible_role_id:
            return ValidationResult(False, "submitted role does not match visible role")
        if role_id not in NIGHT_TARGET_COUNTS:
            return ValidationResult(False, "role does not submit a night action")

        role = self.script.role(role_id)
        order = role.first_night_order if grimoire.phase == GamePhase.FIRST_NIGHT else role.other_night_order
        if order is None:
            return ValidationResult(False, "role does not wake in this night phase")

        minimum, maximum = NIGHT_TARGET_COUNTS[role_id]
        if len(targets) < minimum or len(targets) > maximum:
            return ValidationResult(False, f"{role_id} requires {minimum} target(s)")
        if len(set(targets)) != len(targets):
            return ValidationResult(False, "targets must be unique")
        unknown_targets = [target for target in targets if target not in grimoire.assignments]
        if unknown_targets:
            return ValidationResult(False, "unknown target")
        if role_id == "monk" and actor_id in targets:
            return ValidationResult(False, "monk cannot protect themself")
        return ValidationResult(True)
