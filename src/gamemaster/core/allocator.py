from __future__ import annotations

import random
from dataclasses import dataclass

from .players import RoleAssignment
from .script import Script
from .types import RoleType


PLAYER_DISTRIBUTION: dict[int, tuple[int, int, int, int]] = {
    5: (3, 0, 1, 1),
    6: (3, 1, 1, 1),
    7: (5, 0, 1, 1),
    8: (5, 1, 1, 1),
    9: (5, 2, 1, 1),
    10: (7, 0, 2, 1),
    11: (7, 1, 2, 1),
    12: (7, 2, 2, 1),
    13: (9, 0, 3, 1),
    14: (9, 1, 3, 1),
    15: (9, 2, 3, 1),
}


@dataclass(frozen=True)
class AllocationResult:
    assignments: tuple[RoleAssignment, ...]
    demon_bluffs: tuple[str, ...]
    setup_notes: tuple[str, ...] = ()


class RoleAllocator:
    def __init__(self, script: Script, rng: random.Random | None = None) -> None:
        self.script = script
        self.rng = rng or random.Random()

    def allocate(self, player_ids: tuple[str, ...]) -> AllocationResult:
        player_count = len(player_ids)
        if player_count not in PLAYER_DISTRIBUTION:
            raise ValueError("minimal allocator currently supports 5-15 players")

        townsfolk_count, outsider_count, minion_count, demon_count = PLAYER_DISTRIBUTION[player_count]
        minions = self._sample_by_type(RoleType.MINION, minion_count)
        demons = self._sample_by_type(RoleType.DEMON, demon_count)
        setup_notes: list[str] = []

        townsfolk_count, outsider_count = self._apply_setup_modifiers(
            townsfolk_count,
            outsider_count,
            minions,
        )
        if "baron" in minions:
            setup_notes.append("baron_added_two_outsiders")

        townsfolk = self._sample_by_type(RoleType.TOWNSFOLK, townsfolk_count)
        outsiders = self._sample_by_type(RoleType.OUTSIDER, outsider_count)
        role_ids = [*townsfolk, *outsiders, *minions, *demons]
        self.rng.shuffle(role_ids)

        assignments: list[RoleAssignment] = []
        for player_id, role_id in zip(player_ids, role_ids, strict=True):
            role = self.script.role(role_id)
            shown_role_id = self._shown_role_for_drunk(role_id, role_ids)
            assignments.append(
                RoleAssignment(
                    player_id=player_id,
                    role_id=role_id,
                    alignment=role.alignment,
                    shown_role_id=shown_role_id,
                    is_drunk=role_id == "drunk",
                )
            )
            if role_id == "drunk":
                setup_notes.append(f"drunk_shown_as:{shown_role_id}")

        in_play = set(role_ids)
        bluff_pool = [
            role_id
            for role_id, role in self.script.roles.items()
            if role.role_type in {RoleType.TOWNSFOLK, RoleType.OUTSIDER} and role_id not in in_play
        ]
        demon_bluffs = tuple(self.rng.sample(bluff_pool, min(3, len(bluff_pool))))
        return AllocationResult(
            assignments=tuple(assignments),
            demon_bluffs=demon_bluffs,
            setup_notes=tuple(setup_notes),
        )

    def _apply_setup_modifiers(
        self,
        townsfolk_count: int,
        outsider_count: int,
        minions: list[str],
    ) -> tuple[int, int]:
        if "baron" not in minions:
            return townsfolk_count, outsider_count
        if townsfolk_count < 2:
            raise ValueError("baron setup needs at least two townsfolk slots to replace")
        return townsfolk_count - 2, outsider_count + 2

    def _shown_role_for_drunk(self, role_id: str, in_play_role_ids: list[str]) -> str | None:
        if role_id != "drunk":
            return None
        candidates = [
            candidate_id
            for candidate_id, role in self.script.roles.items()
            if role.role_type == RoleType.TOWNSFOLK and candidate_id not in in_play_role_ids
        ]
        if not candidates:
            candidates = [
                candidate_id
                for candidate_id, role in self.script.roles.items()
                if role.role_type == RoleType.TOWNSFOLK
            ]
        if not candidates:
            raise ValueError("drunk setup needs at least one townsfolk role to show")
        return self.rng.choice(candidates)

    def _sample_by_type(self, role_type: RoleType, count: int) -> list[str]:
        role_ids = [
            role_id for role_id, role in self.script.roles.items() if role.role_type == role_type
        ]
        if len(role_ids) < count:
            raise ValueError(f"not enough {role_type.value} roles in script")
        return self.rng.sample(role_ids, count)
