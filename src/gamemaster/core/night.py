from __future__ import annotations

from dataclasses import dataclass

from .actions import ActionResult
from .flow import GameFlow
from .types import GamePhase


@dataclass(frozen=True)
class NightResolution:
    results: tuple[ActionResult, ...]
    order: tuple[str, ...]


class NightOrderResolver:
    def __init__(self, flow: GameFlow) -> None:
        self.flow = flow

    def resolve_current_night(self) -> NightResolution:
        first_night = self.flow.grimoire.phase == GamePhase.FIRST_NIGHT
        ordered = self._ordered_player_ids(first_night)
        results: list[ActionResult] = []
        for player_id in ordered:
            results.extend(self.flow.resolve_role_night(player_id))
        return NightResolution(results=tuple(results), order=tuple(ordered))

    def _ordered_player_ids(self, first_night: bool) -> list[str]:
        entries: list[tuple[int, str]] = []
        for player_id, assignment in self.flow.grimoire.assignments.items():
            role = self.flow.script.role(assignment.visible_role_id)
            order = role.first_night_order if first_night else role.other_night_order
            if order is None:
                continue
            entries.append((order, player_id))
        entries.sort(key=lambda item: item[0])
        return [player_id for _, player_id in entries]
