from __future__ import annotations

from dataclasses import dataclass

from .roles import (
    Baron,
    Butler,
    Chef,
    Drunk,
    Empath,
    FortuneTeller,
    Imp,
    Investigator,
    Librarian,
    Mayor,
    Monk,
    Poisoner,
    Ravenkeeper,
    Recluse,
    RoleCard,
    Saint,
    ScarletWoman,
    Slayer,
    Soldier,
    Spy,
    Undertaker,
    Virgin,
    Washerwoman,
)


@dataclass(frozen=True)
class Script:
    script_id: str
    name: str
    roles: dict[str, RoleCard]

    def role(self, role_id: str) -> RoleCard:
        return self.roles[role_id]


def trouble_brewing_minimal() -> Script:
    roles = [
        Washerwoman(),
        Librarian(),
        Investigator(),
        Chef(),
        Empath(),
        FortuneTeller(),
        Undertaker(),
        Slayer(),
        Soldier(),
        Monk(),
        Ravenkeeper(),
        Virgin(),
        Mayor(),
        Drunk(),
        Saint(),
        Recluse(),
        Butler(),
        Poisoner(),
        Spy(),
        ScarletWoman(),
        Baron(),
        Imp(),
    ]
    return Script(
        script_id="trouble_brewing",
        name="Trouble Brewing",
        roles={role.role_id: role for role in roles},
    )
