from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .decisions import DecisionRequest
from .effects import ApplyConditionEffect, GiveInfoEffect, KillEffect, NoOpEffect
from .types import Alignment, DecisionType, RoleType


class GrimoireLike(Protocol):
    assignments: dict
    events: list
    night_actions: dict
    pipeline_state: dict

    def evil_neighbor_count(self, player_id: str) -> int: ...
    def player_ids_by_role(self, role_id: str) -> tuple[str, ...]: ...
    def player_ids_by_alignment(self, alignment: Alignment) -> tuple[str, ...]: ...
    def registered_alignment(self, player_id: str) -> Alignment: ...
    def action_for(self, player_id: str) -> dict | None: ...


@dataclass(frozen=True)
class RoleCard:
    role_id: str
    name: str
    role_type: RoleType
    alignment: Alignment
    ability_text: str
    first_night_order: int | None = None
    other_night_order: int | None = None

    def on_setup(self, grimoire: GrimoireLike, player_id: str) -> tuple[object, ...]:
        return ()

    def on_night(self, grimoire: GrimoireLike, player_id: str) -> tuple[object, ...]:
        return ()

    def on_day(self, grimoire: GrimoireLike, player_id: str) -> tuple[object, ...]:
        return ()


class Empath(RoleCard):
    def __init__(self) -> None:
        super().__init__(
            role_id="empath",
            name="Empath",
            role_type=RoleType.TOWNSFOLK,
            alignment=Alignment.GOOD,
            ability_text="Each night, learn how many of your 2 alive neighbors are evil.",
            first_night_order=50,
            other_night_order=50,
        )

    def on_night(self, grimoire: GrimoireLike, player_id: str) -> tuple[object, ...]:
        assignment = grimoire.assignments[player_id]
        true_count = grimoire.evil_neighbor_count(player_id)
        if assignment.is_drunk or assignment.is_poisoned:
            request = DecisionRequest.create(
                DecisionType.FALSE_INFORMATION,
                actor_id=player_id,
                role_id=self.role_id,
                prompt="Choose a plausible Empath number for a drunk or poisoned player.",
                allowed_outputs=(0, 1, 2),
                true_value=true_count,
                constraints=(
                    "Prefer a false value when possible.",
                    "Do not reveal that the player is drunk or poisoned.",
                    "Keep the information plausible for the current table.",
                ),
                context={"true_count": true_count},
                fallback_output=1 if true_count != 1 else 0,
            )
            return (request,)
        return (
            GiveInfoEffect(
                recipient_id=player_id,
                role_id=self.role_id,
                value=true_count,
                message=f"You learn that {true_count} of your alive neighbors are evil.",
            ),
        )


class Washerwoman(RoleCard):
    def __init__(self) -> None:
        super().__init__(
            role_id="washerwoman",
            name="Washerwoman",
            role_type=RoleType.TOWNSFOLK,
            alignment=Alignment.GOOD,
            ability_text="You start knowing that 1 of 2 players is a particular Townsfolk.",
            first_night_order=10,
        )

    def on_night(self, grimoire: GrimoireLike, player_id: str) -> tuple[object, ...]:
        townsfolk = [
            pid
            for pid, assignment in grimoire.assignments.items()
            if assignment.role_id not in {self.role_id}
            and assignment.alignment == Alignment.GOOD
            and assignment.role_id not in {"drunk"}
        ]
        true_candidate = townsfolk[0] if townsfolk else player_id
        allowed_decoys = tuple(pid for pid in grimoire.assignments if pid != true_candidate and pid != player_id)
        request = DecisionRequest.create(
            DecisionType.SETUP_SELECTION,
            actor_id=player_id,
            role_id=self.role_id,
            prompt="Choose the second Washerwoman candidate.",
            allowed_outputs=allowed_decoys or (true_candidate,),
            true_value=true_candidate,
            constraints=(
                "The final pair must contain the true Townsfolk.",
                "Choose a plausible decoy who creates useful discussion.",
            ),
            context={"true_candidate": true_candidate},
            fallback_output=allowed_decoys[0] if allowed_decoys else true_candidate,
        )
        return (request,)


class Librarian(RoleCard):
    def __init__(self) -> None:
        super().__init__(
            role_id="librarian",
            name="Librarian",
            role_type=RoleType.TOWNSFOLK,
            alignment=Alignment.GOOD,
            ability_text="You start knowing that 1 of 2 players is a particular Outsider, or that zero Outsiders are in play.",
            first_night_order=12,
        )

    def on_night(self, grimoire: GrimoireLike, player_id: str) -> tuple[object, ...]:
        outsiders = [
            pid
            for pid, assignment in grimoire.assignments.items()
            if _role_type_from_id(assignment.role_id) == RoleType.OUTSIDER
        ]
        if not outsiders:
            return (
                GiveInfoEffect(
                    recipient_id=player_id,
                    role_id=self.role_id,
                    value=0,
                    message="You learn that there are 0 Outsiders in play.",
                ),
            )
        true_candidate = outsiders[0]
        decoy = _first_decoy(grimoire, player_id, true_candidate)
        true_role = grimoire.assignments[true_candidate].role_id
        return (
            GiveInfoEffect(
                recipient_id=player_id,
                role_id=self.role_id,
                value={"true_candidate": true_candidate, "decoy": decoy, "role_id": true_role},
                message=f"You learn that one of {true_candidate} and {decoy} is the {true_role}.",
            ),
        )


class Investigator(RoleCard):
    def __init__(self) -> None:
        super().__init__(
            role_id="investigator",
            name="Investigator",
            role_type=RoleType.TOWNSFOLK,
            alignment=Alignment.GOOD,
            ability_text="You start knowing that 1 of 2 players is a particular Minion.",
            first_night_order=14,
        )

    def on_night(self, grimoire: GrimoireLike, player_id: str) -> tuple[object, ...]:
        minions = [
            pid
            for pid, assignment in grimoire.assignments.items()
            if _role_type_from_id(assignment.role_id) == RoleType.MINION
        ]
        if not minions:
            return (NoOpEffect("Investigator found no Minion candidate."),)
        true_candidate = minions[0]
        decoy = _first_decoy(grimoire, player_id, true_candidate)
        true_role = grimoire.assignments[true_candidate].role_id
        return (
            GiveInfoEffect(
                recipient_id=player_id,
                role_id=self.role_id,
                value={"true_candidate": true_candidate, "decoy": decoy, "role_id": true_role},
                message=f"You learn that one of {true_candidate} and {decoy} is the {true_role}.",
            ),
        )


class Chef(RoleCard):
    def __init__(self) -> None:
        super().__init__(
            role_id="chef",
            name="Chef",
            role_type=RoleType.TOWNSFOLK,
            alignment=Alignment.GOOD,
            ability_text="You start knowing how many pairs of evil players are neighbors.",
            first_night_order=40,
        )

    def on_night(self, grimoire: GrimoireLike, player_id: str) -> tuple[object, ...]:
        evil = set(grimoire.player_ids_by_alignment(Alignment.EVIL))
        seats = [seat.player_id for seat in grimoire.seats if seat.player_id in grimoire.assignments]
        count = 0
        for index, current in enumerate(seats):
            nxt = seats[(index + 1) % len(seats)]
            if current in evil and nxt in evil:
                count += 1
        return (
            GiveInfoEffect(
                recipient_id=player_id,
                role_id=self.role_id,
                value=count,
                message=f"You learn that there are {count} pairs of evil neighbors.",
            ),
        )


class FortuneTeller(RoleCard):
    def __init__(self) -> None:
        super().__init__(
            role_id="fortune_teller",
            name="Fortune Teller",
            role_type=RoleType.TOWNSFOLK,
            alignment=Alignment.GOOD,
            ability_text="Each night, choose 2 players: learn if either is a Demon. One good player registers as Demon.",
            first_night_order=60,
            other_night_order=60,
        )

    def on_night(self, grimoire: GrimoireLike, player_id: str) -> tuple[object, ...]:
        action = grimoire.action_for(player_id)
        if not action or len(action.get("targets", [])) < 2:
            return (NoOpEffect("Fortune Teller has not selected two targets."),)
        targets = tuple(action["targets"][:2])
        demon_ids = set(grimoire.player_ids_by_role("imp"))
        red_herring = grimoire.pipeline_state.get("fortune_teller_red_herring")
        value = any(
            target in demon_ids
            or target == red_herring
            or _registers_as_demon(grimoire, target)
            for target in targets
        )
        assignment = grimoire.assignments[player_id]
        if assignment.is_drunk or assignment.is_poisoned:
            request = DecisionRequest.create(
                DecisionType.FALSE_INFORMATION,
                actor_id=player_id,
                role_id=self.role_id,
                prompt="Choose a plausible Fortune Teller yes/no result for a drunk or poisoned player.",
                allowed_outputs=(True, False),
                true_value=value,
                constraints=("Do not reveal drunkenness or poisoning.", "Keep the answer plausible."),
                context={"targets": targets, "true_value": value},
                fallback_output=not value,
            )
            return (request,)
        return (
            GiveInfoEffect(
                recipient_id=player_id,
                role_id=self.role_id,
                value=value,
                message="You learn: yes." if value else "You learn: no.",
            ),
        )


class Slayer(RoleCard):
    def __init__(self) -> None:
        super().__init__(
            role_id="slayer",
            name="Slayer",
            role_type=RoleType.TOWNSFOLK,
            alignment=Alignment.GOOD,
            ability_text="Once per game, during the day, publicly choose a player: if they are the Demon, they die.",
        )


class Soldier(RoleCard):
    def __init__(self) -> None:
        super().__init__(
            role_id="soldier",
            name="Soldier",
            role_type=RoleType.TOWNSFOLK,
            alignment=Alignment.GOOD,
            ability_text="You are safe from the Demon.",
        )


class Undertaker(RoleCard):
    def __init__(self) -> None:
        super().__init__(
            role_id="undertaker",
            name="Undertaker",
            role_type=RoleType.TOWNSFOLK,
            alignment=Alignment.GOOD,
            ability_text="Each night, learn which character died by execution today.",
            other_night_order=30,
        )

    def on_night(self, grimoire: GrimoireLike, player_id: str) -> tuple[object, ...]:
        day_state = grimoire.pipeline_state.get("day_state") or {}
        executed_player_id = day_state.get("executed_player_id")
        if not executed_player_id:
            return (
                GiveInfoEffect(
                    recipient_id=player_id,
                    role_id=self.role_id,
                    value=None,
                    message="You learn that nobody died by execution today.",
                ),
            )

        true_role = grimoire.assignments[executed_player_id].visible_role_id
        assignment = grimoire.assignments[player_id]
        if assignment.is_drunk or assignment.is_poisoned:
            allowed_roles = tuple(
                sorted({item.visible_role_id for item in grimoire.assignments.values()})
            )
            fallback = next((role_id for role_id in allowed_roles if role_id != true_role), true_role)
            request = DecisionRequest.create(
                DecisionType.FALSE_INFORMATION,
                actor_id=player_id,
                role_id=self.role_id,
                prompt="Choose a plausible Undertaker role for a drunk or poisoned player.",
                allowed_outputs=allowed_roles,
                true_value=true_role,
                constraints=(
                    "Do not reveal drunkenness or poisoning.",
                    "Prefer a false role when possible.",
                ),
                context={"executed_player_id": executed_player_id, "true_role": true_role},
                fallback_output=fallback,
            )
            return (request,)

        return (
            GiveInfoEffect(
                recipient_id=player_id,
                role_id=self.role_id,
                value=true_role,
                message=f"You learn that the executed player was the {true_role}.",
            ),
        )


class Monk(RoleCard):
    def __init__(self) -> None:
        super().__init__(
            role_id="monk",
            name="Monk",
            role_type=RoleType.TOWNSFOLK,
            alignment=Alignment.GOOD,
            ability_text="Each night, choose a player other than yourself: they are safe from the Demon tonight.",
            other_night_order=20,
        )

    def on_night(self, grimoire: GrimoireLike, player_id: str) -> tuple[object, ...]:
        action = grimoire.action_for(player_id)
        if not action or not action.get("targets"):
            return (NoOpEffect("Monk has not selected a target."),)
        assignment = grimoire.assignments[player_id]
        if assignment.is_drunk or assignment.is_poisoned:
            return (NoOpEffect("Drunk or poisoned Monk protection has no effect."),)
        target = action["targets"][0]
        return (
            ApplyConditionEffect(
                target_id=target,
                condition="protected_by_monk",
                source_role_id=self.role_id,
                source_player_id=player_id,
                duration="tonight",
            ),
        )


class Ravenkeeper(RoleCard):
    def __init__(self) -> None:
        super().__init__(
            role_id="ravenkeeper",
            name="Ravenkeeper",
            role_type=RoleType.TOWNSFOLK,
            alignment=Alignment.GOOD,
            ability_text="If you die at night, you are woken to choose a player: learn their character.",
            other_night_order=90,
        )

    def on_night(self, grimoire: GrimoireLike, player_id: str) -> tuple[object, ...]:
        died_tonight = any(
            event.event_type.value == "death"
            and event.payload.get("target_id") == player_id
            and event.phase.value in {"night", "first_night"}
            for event in grimoire.events
        )
        if not died_tonight:
            return (NoOpEffect("Ravenkeeper did not die tonight."),)

        action = grimoire.action_for(player_id)
        if not action or not action.get("targets"):
            return (NoOpEffect("Ravenkeeper has not selected a target."),)
        target_id = action["targets"][0]
        true_role = grimoire.assignments[target_id].visible_role_id
        assignment = grimoire.assignments[player_id]
        if assignment.is_drunk or assignment.is_poisoned:
            allowed_roles = tuple(
                sorted({item.visible_role_id for item in grimoire.assignments.values()})
            )
            fallback = next((role_id for role_id in allowed_roles if role_id != true_role), true_role)
            request = DecisionRequest.create(
                DecisionType.FALSE_INFORMATION,
                actor_id=player_id,
                role_id=self.role_id,
                prompt="Choose a plausible Ravenkeeper role for a drunk or poisoned player.",
                allowed_outputs=allowed_roles,
                true_value=true_role,
                constraints=(
                    "Do not reveal drunkenness or poisoning.",
                    "Prefer a false role when possible.",
                ),
                context={"target_id": target_id, "true_role": true_role},
                fallback_output=fallback,
            )
            return (request,)

        return (
            GiveInfoEffect(
                recipient_id=player_id,
                role_id=self.role_id,
                value=true_role,
                message=f"You learn that {target_id} is the {true_role}.",
            ),
        )


class Mayor(RoleCard):
    def __init__(self) -> None:
        super().__init__(
            role_id="mayor",
            name="Mayor",
            role_type=RoleType.TOWNSFOLK,
            alignment=Alignment.GOOD,
            ability_text=(
                "If only 3 players live and no execution occurs today, your team wins. "
                "If you die at night, another player might die instead."
            ),
        )


class Virgin(RoleCard):
    def __init__(self) -> None:
        super().__init__(
            role_id="virgin",
            name="Virgin",
            role_type=RoleType.TOWNSFOLK,
            alignment=Alignment.GOOD,
            ability_text="The 1st time you are nominated, if the nominator is a Townsfolk, they are executed immediately.",
        )


class Poisoner(RoleCard):
    def __init__(self) -> None:
        super().__init__(
            role_id="poisoner",
            name="Poisoner",
            role_type=RoleType.MINION,
            alignment=Alignment.EVIL,
            ability_text="Each night, choose a player: they are poisoned tonight.",
            first_night_order=5,
            other_night_order=5,
        )

    def on_night(self, grimoire: GrimoireLike, player_id: str) -> tuple[object, ...]:
        action = grimoire.action_for(player_id)
        if not action or not action.get("targets"):
            return (NoOpEffect("Poisoner has not selected a target."),)
        target = action["targets"][0]
        return (
            ApplyConditionEffect(
                target_id=target,
                condition="poisoned",
                source_role_id=self.role_id,
                source_player_id=player_id,
            ),
        )


class Imp(RoleCard):
    def __init__(self) -> None:
        super().__init__(
            role_id="imp",
            name="Imp",
            role_type=RoleType.DEMON,
            alignment=Alignment.EVIL,
            ability_text="Each night, choose a player: they die.",
            other_night_order=80,
        )

    def on_night(self, grimoire: GrimoireLike, player_id: str) -> tuple[object, ...]:
        action = grimoire.action_for(player_id)
        if not action or not action.get("targets"):
            return (NoOpEffect("Imp has not selected a target."),)
        return (
            KillEffect(
                target_id=action["targets"][0],
                source_role_id=self.role_id,
                source_player_id=player_id,
                cause="imp_attack",
            ),
        )


class Drunk(RoleCard):
    def __init__(self) -> None:
        super().__init__(
            role_id="drunk",
            name="Drunk",
            role_type=RoleType.OUTSIDER,
            alignment=Alignment.GOOD,
            ability_text="You do not know you are the Drunk. You think you are a Townsfolk, but you are not.",
        )


class Recluse(RoleCard):
    def __init__(self) -> None:
        super().__init__(
            role_id="recluse",
            name="Recluse",
            role_type=RoleType.OUTSIDER,
            alignment=Alignment.GOOD,
            ability_text="You might register as evil and as a Minion or Demon, even if dead.",
        )


class Butler(RoleCard):
    def __init__(self) -> None:
        super().__init__(
            role_id="butler",
            name="Butler",
            role_type=RoleType.OUTSIDER,
            alignment=Alignment.GOOD,
            ability_text="Each night, choose a player: tomorrow, you may vote only if they are voting too.",
            first_night_order=15,
            other_night_order=15,
        )

    def on_night(self, grimoire: GrimoireLike, player_id: str) -> tuple[object, ...]:
        action = grimoire.action_for(player_id)
        if not action or not action.get("targets"):
            return (NoOpEffect("Butler has not selected a master."),)
        assignment = grimoire.assignments[player_id]
        if assignment.is_drunk or assignment.is_poisoned:
            return (NoOpEffect("Drunk or poisoned Butler master choice has no effect."),)
        target = action["targets"][0]
        return (
            ApplyConditionEffect(
                target_id=player_id,
                condition=f"butler_master:{target}",
                source_role_id=self.role_id,
                source_player_id=player_id,
                duration="tomorrow",
            ),
        )


class Saint(RoleCard):
    def __init__(self) -> None:
        super().__init__(
            role_id="saint",
            name="Saint",
            role_type=RoleType.OUTSIDER,
            alignment=Alignment.GOOD,
            ability_text="If you die by execution, your team loses.",
        )


class ScarletWoman(RoleCard):
    def __init__(self) -> None:
        super().__init__(
            role_id="scarlet_woman",
            name="Scarlet Woman",
            role_type=RoleType.MINION,
            alignment=Alignment.EVIL,
            ability_text="If there are 5 or more players alive and the Demon dies, you become the Demon.",
        )


class Baron(RoleCard):
    def __init__(self) -> None:
        super().__init__(
            role_id="baron",
            name="Baron",
            role_type=RoleType.MINION,
            alignment=Alignment.EVIL,
            ability_text="There are extra Outsiders in play.",
        )


class Spy(RoleCard):
    def __init__(self) -> None:
        super().__init__(
            role_id="spy",
            name="Spy",
            role_type=RoleType.MINION,
            alignment=Alignment.EVIL,
            ability_text="Each night, you see the Grimoire. You might register as good and as a Townsfolk or Outsider, even if dead.",
            first_night_order=70,
            other_night_order=70,
        )

    def on_night(self, grimoire: GrimoireLike, player_id: str) -> tuple[object, ...]:
        rows = [
            f"{pid}: {assignment.role_id}"
            for pid, assignment in sorted(grimoire.assignments.items())
        ]
        return (
            GiveInfoEffect(
                recipient_id=player_id,
                role_id=self.role_id,
                value=rows,
                message="Grimoire: " + "; ".join(rows),
            ),
        )


class PlaceholderTownsfolk(RoleCard):
    def __init__(self, role_id: str, name: str) -> None:
        super().__init__(
            role_id=role_id,
            name=name,
            role_type=RoleType.TOWNSFOLK,
            alignment=Alignment.GOOD,
            ability_text="Placeholder Townsfolk ability for allocation tests.",
        )


class PlaceholderOutsider(RoleCard):
    def __init__(self, role_id: str, name: str) -> None:
        super().__init__(
            role_id=role_id,
            name=name,
            role_type=RoleType.OUTSIDER,
            alignment=Alignment.GOOD,
            ability_text="Placeholder Outsider ability for allocation tests.",
        )


class PlaceholderMinion(RoleCard):
    def __init__(self, role_id: str, name: str) -> None:
        super().__init__(
            role_id=role_id,
            name=name,
            role_type=RoleType.MINION,
            alignment=Alignment.EVIL,
            ability_text="Placeholder Minion ability for allocation tests.",
        )


ROLE_TYPE_BY_ID = {
    "drunk": RoleType.OUTSIDER,
    "saint": RoleType.OUTSIDER,
    "recluse": RoleType.OUTSIDER,
    "butler": RoleType.OUTSIDER,
    "poisoner": RoleType.MINION,
    "scarlet_woman": RoleType.MINION,
    "baron": RoleType.MINION,
    "spy": RoleType.MINION,
}


def _role_type_from_id(role_id: str) -> RoleType:
    return ROLE_TYPE_BY_ID.get(role_id, RoleType.TOWNSFOLK)


def _first_decoy(grimoire: GrimoireLike, actor_id: str, true_candidate: str) -> str:
    return next(
        (
            pid
            for pid in grimoire.assignments
            if pid not in {actor_id, true_candidate}
        ),
        true_candidate,
    )


def _registers_as_demon(grimoire: GrimoireLike, player_id: str) -> bool:
    overrides = grimoire.pipeline_state.get("registration_overrides") or {}
    override = overrides.get(player_id) or {}
    return override.get("role_type") == RoleType.DEMON.value
