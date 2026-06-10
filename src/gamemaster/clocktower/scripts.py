from __future__ import annotations

from dataclasses import dataclass, field


TEAM_GOOD = "good"
TEAM_EVIL = "evil"

ROLE_TOWNSFOLK = "townsfolk"
ROLE_OUTSIDER = "outsider"
ROLE_MINION = "minion"
ROLE_DEMON = "demon"
ROLE_TRAVELER = "traveler"


@dataclass(frozen=True)
class Role:
    name: str
    role_type: str
    team: str
    summary: str
    first_night: int | None = None
    other_night: int | None = None
    outsider_delta: int = 0
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Script:
    script_id: str
    name: str
    aliases: tuple[str, ...]
    roles: tuple[Role, ...]

    def by_name(self, name: str) -> Role:
        normalized = normalize_role_name(name)
        for role in self.roles:
            if normalize_role_name(role.name) == normalized:
                return role
        raise KeyError(name)

    def roles_by_type(self, role_type: str) -> list[Role]:
        return [role for role in self.roles if role.role_type == role_type]


def normalize_role_name(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


TROUBLE_BREWING = Script(
    script_id="trouble_brewing",
    name="Trouble Brewing / 暗流涌动",
    aliases=("tb", "trouble", "trouble_brewing", "暗流涌动", "暗流"),
    roles=(
        Role("Washerwoman", ROLE_TOWNSFOLK, TEAM_GOOD, "首夜得知某个镇民角色，并看到两名候选玩家。", first_night=10),
        Role("Librarian", ROLE_TOWNSFOLK, TEAM_GOOD, "首夜得知某个外来者角色，并看到两名候选玩家；也可能得知没有外来者。", first_night=20),
        Role("Investigator", ROLE_TOWNSFOLK, TEAM_GOOD, "首夜得知某个爪牙角色，并看到两名候选玩家。", first_night=30),
        Role("Chef", ROLE_TOWNSFOLK, TEAM_GOOD, "首夜得知相邻邪恶玩家对数。", first_night=40),
        Role("Empath", ROLE_TOWNSFOLK, TEAM_GOOD, "每夜得知两侧存活邻居中邪恶玩家数量。", first_night=50, other_night=50),
        Role("Fortune Teller", ROLE_TOWNSFOLK, TEAM_GOOD, "每夜选择两名玩家，得知其中是否包含恶魔；存在一个误判目标。", first_night=60, other_night=60),
        Role("Undertaker", ROLE_TOWNSFOLK, TEAM_GOOD, "每夜得知白天被处决玩家的角色。", other_night=70),
        Role("Monk", ROLE_TOWNSFOLK, TEAM_GOOD, "每夜保护一名非自己的玩家免受恶魔伤害。", other_night=20),
        Role("Ravenkeeper", ROLE_TOWNSFOLK, TEAM_GOOD, "若夜晚死亡，可选择一名玩家并得知其角色。"),
        Role("Virgin", ROLE_TOWNSFOLK, TEAM_GOOD, "首次被镇民提名时，提名者可能立刻被处决。"),
        Role("Slayer", ROLE_TOWNSFOLK, TEAM_GOOD, "整局一次，白天公开射击一名玩家；若其是恶魔，目标死亡。"),
        Role("Soldier", ROLE_TOWNSFOLK, TEAM_GOOD, "不会被恶魔杀死。"),
        Role("Mayor", ROLE_TOWNSFOLK, TEAM_GOOD, "若仅剩三人且无人处决，善良阵营可能获胜；夜晚死亡可能被转移。"),
        Role("Butler", ROLE_OUTSIDER, TEAM_GOOD, "每夜选择主人，白天投票需跟随该玩家。", first_night=90, other_night=90),
        Role("Drunk", ROLE_OUTSIDER, TEAM_GOOD, "以为自己是镇民，但能力无效，信息可被说书人误导。", tags=("misregisters_as_townsfolk",)),
        Role("Recluse", ROLE_OUTSIDER, TEAM_GOOD, "可能被侦测为邪恶或爪牙/恶魔。"),
        Role("Saint", ROLE_OUTSIDER, TEAM_GOOD, "若被处决，邪恶阵营获胜。"),
        Role("Poisoner", ROLE_MINION, TEAM_EVIL, "每夜选择一名玩家使其能力暂时失效。", first_night=5, other_night=5),
        Role("Spy", ROLE_MINION, TEAM_EVIL, "每夜查看魔典，并可能被侦测为善良或镇民/外来者。", first_night=100, other_night=100),
        Role("Scarlet Woman", ROLE_MINION, TEAM_EVIL, "若恶魔在存活人数足够多时死亡，她会成为新恶魔。"),
        Role("Baron", ROLE_MINION, TEAM_EVIL, "设置阶段增加外来者数量。", outsider_delta=2),
        Role("Imp", ROLE_DEMON, TEAM_EVIL, "每夜杀死一名玩家；可自杀并把恶魔身份传给爪牙。", other_night=80),
        Role("Bureaucrat", ROLE_TRAVELER, TEAM_GOOD, "使一名玩家的投票权重临时增加。"),
        Role("Thief", ROLE_TRAVELER, TEAM_EVIL, "使一名玩家的投票权重临时变为负面。"),
        Role("Gunslinger", ROLE_TRAVELER, TEAM_GOOD, "投票后可选择杀死一名参与投票的玩家。"),
        Role("Scapegoat", ROLE_TRAVELER, TEAM_GOOD, "善良玩家被处决时，可能改为处决替罪羊。"),
        Role("Beggar", ROLE_TRAVELER, TEAM_GOOD, "投票能力受限，但死者可给其投票权。"),
    ),
)


BAD_MOON_RISING = Script(
    script_id="bad_moon_rising",
    name="Bad Moon Rising / 黯月初升",
    aliases=("bmr", "bad_moon_rising", "bad_moon", "黯月初升", "黯月"),
    roles=(
        Role("Grandmother", ROLE_TOWNSFOLK, TEAM_GOOD, "首夜得知一名善良玩家及其角色；若该玩家被恶魔杀死，祖母也可能死亡。", first_night=10),
        Role("Sailor", ROLE_TOWNSFOLK, TEAM_GOOD, "每夜选择一名玩家；两者之一醉酒，水手通常难以被杀死。", first_night=20, other_night=20),
        Role("Chambermaid", ROLE_TOWNSFOLK, TEAM_GOOD, "每夜选择两名玩家，得知其中有多少人在当夜因自身能力醒来。", first_night=30, other_night=30),
        Role("Exorcist", ROLE_TOWNSFOLK, TEAM_GOOD, "每夜选择一名玩家；若是恶魔，阻止其当夜行动且彼此获知。", other_night=40),
        Role("Innkeeper", ROLE_TOWNSFOLK, TEAM_GOOD, "每夜保护两名玩家免死，但其中一人可能醉酒。", other_night=50),
        Role("Gambler", ROLE_TOWNSFOLK, TEAM_GOOD, "每夜猜一名玩家的角色；猜错则自己死亡。", other_night=60),
        Role("Gossip", ROLE_TOWNSFOLK, TEAM_GOOD, "白天公开作出陈述；若为真，当晚可能额外死亡。"),
        Role("Courtier", ROLE_TOWNSFOLK, TEAM_GOOD, "整局一次，选择角色使该角色相关玩家长期醉酒。", first_night=70, other_night=70),
        Role("Professor", ROLE_TOWNSFOLK, TEAM_GOOD, "整局一次，夜晚尝试复活一名镇民。", other_night=80),
        Role("Minstrel", ROLE_TOWNSFOLK, TEAM_GOOD, "爪牙被处决后，所有人次日可能醉酒。"),
        Role("Tea Lady", ROLE_TOWNSFOLK, TEAM_GOOD, "若两侧存活邻居善良，他们难以死亡。"),
        Role("Pacifist", ROLE_TOWNSFOLK, TEAM_GOOD, "善良玩家被处决时，可能不会死亡。"),
        Role("Fool", ROLE_TOWNSFOLK, TEAM_GOOD, "首次将要死亡时可能免死。"),
        Role("Goon", ROLE_OUTSIDER, TEAM_GOOD, "第一个夜晚选择他的玩家会醉酒，并可能改变他的阵营。"),
        Role("Lunatic", ROLE_OUTSIDER, TEAM_GOOD, "以为自己是恶魔；真正恶魔可能得知其选择。"),
        Role("Tinker", ROLE_OUTSIDER, TEAM_GOOD, "随时可能死亡。"),
        Role("Moonchild", ROLE_OUTSIDER, TEAM_GOOD, "死亡后选择一名善良玩家，该玩家可能死亡。"),
        Role("Godfather", ROLE_MINION, TEAM_EVIL, "得知外来者角色；外来者死亡后可能额外杀人；设置时可调整外来者数量。", outsider_delta=1),
        Role("Devil's Advocate", ROLE_MINION, TEAM_EVIL, "每夜保护一名玩家免于处决死亡。", first_night=5, other_night=5),
        Role("Assassin", ROLE_MINION, TEAM_EVIL, "整局一次，夜晚杀死一名玩家，常可穿透保护。", other_night=90),
        Role("Mastermind", ROLE_MINION, TEAM_EVIL, "若恶魔被处决，游戏可能额外进行一天。"),
        Role("Zombuul", ROLE_DEMON, TEAM_EVIL, "首次死亡时秘密存活；每夜在特定条件下杀人。", other_night=100),
        Role("Pukka", ROLE_DEMON, TEAM_EVIL, "每夜使一名玩家中毒，之后该玩家死亡。", first_night=100, other_night=100),
        Role("Shabaloth", ROLE_DEMON, TEAM_EVIL, "每夜可造成多名死亡，并可能让死者复活。", other_night=100),
        Role("Po", ROLE_DEMON, TEAM_EVIL, "可蓄力后在下一夜造成多名死亡。", other_night=100),
        Role("Apprentice", ROLE_TRAVELER, TEAM_GOOD, "获得一个镇民或爪牙能力。"),
        Role("Matron", ROLE_TRAVELER, TEAM_GOOD, "限制座位移动和私聊对象。"),
        Role("Judge", ROLE_TRAVELER, TEAM_EVIL, "整局一次，影响一次处决是否发生。"),
        Role("Bishop", ROLE_TRAVELER, TEAM_GOOD, "改变提名流程，由说书人参与指定提名。"),
        Role("Voudon", ROLE_TRAVELER, TEAM_EVIL, "死亡玩家投票规则改变，且恶魔相关胜负受到影响。"),
    ),
)


SECTS_AND_VIOLETS = Script(
    script_id="sects_and_violets",
    name="Sects & Violets / 梦殒春宵",
    aliases=("sv", "sects_and_violets", "sects", "梦殒春宵", "梦殒"),
    roles=(
        Role("Clockmaker", ROLE_TOWNSFOLK, TEAM_GOOD, "首夜得知恶魔与最近爪牙之间的距离。", first_night=10),
        Role("Dreamer", ROLE_TOWNSFOLK, TEAM_GOOD, "每夜选择一名玩家，得知一个善良和一个邪恶角色候选。", first_night=20, other_night=20),
        Role("Snake Charmer", ROLE_TOWNSFOLK, TEAM_GOOD, "每夜选择一名玩家；若选中恶魔，两者交换身份与阵营。", first_night=30, other_night=30),
        Role("Mathematician", ROLE_TOWNSFOLK, TEAM_GOOD, "每夜得知有多少名玩家能力异常。", first_night=40, other_night=40),
        Role("Flowergirl", ROLE_TOWNSFOLK, TEAM_GOOD, "每夜得知恶魔白天是否投票。", other_night=50),
        Role("Town Crier", ROLE_TOWNSFOLK, TEAM_GOOD, "每夜得知爪牙白天是否提名。", other_night=60),
        Role("Oracle", ROLE_TOWNSFOLK, TEAM_GOOD, "每夜得知死亡玩家中邪恶玩家数量。", first_night=70, other_night=70),
        Role("Savant", ROLE_TOWNSFOLK, TEAM_GOOD, "每天获得两条信息，其中一真一假。"),
        Role("Seamstress", ROLE_TOWNSFOLK, TEAM_GOOD, "整局一次，选择两名玩家得知阵营是否相同。", first_night=80, other_night=80),
        Role("Philosopher", ROLE_TOWNSFOLK, TEAM_GOOD, "整局一次，选择获得一个善良角色能力，可能使原能力者醉酒。", first_night=90, other_night=90),
        Role("Artist", ROLE_TOWNSFOLK, TEAM_GOOD, "整局一次，向说书人问一个是/否问题。"),
        Role("Juggler", ROLE_TOWNSFOLK, TEAM_GOOD, "首日公开猜若干玩家角色，次夜得知命中数。", other_night=100),
        Role("Sage", ROLE_TOWNSFOLK, TEAM_GOOD, "若被恶魔杀死，得知两名候选玩家中包含恶魔。"),
        Role("Mutant", ROLE_OUTSIDER, TEAM_GOOD, "若公开承认自己是外来者，可能被处决。"),
        Role("Sweetheart", ROLE_OUTSIDER, TEAM_GOOD, "死亡后，一名玩家可能长期醉酒。"),
        Role("Barber", ROLE_OUTSIDER, TEAM_GOOD, "死亡后，恶魔可能交换两名玩家角色。"),
        Role("Klutz", ROLE_OUTSIDER, TEAM_GOOD, "死亡时选择一名存活玩家；若其邪恶，善良阵营失败。"),
        Role("Evil Twin", ROLE_MINION, TEAM_EVIL, "一名善良玩家知道彼此为双子；若善双子被处决，邪恶获胜。"),
        Role("Witch", ROLE_MINION, TEAM_EVIL, "每夜诅咒一名玩家；该玩家若提名可能死亡。", first_night=5, other_night=5),
        Role("Cerenovus", ROLE_MINION, TEAM_EVIL, "每夜使一名玩家陷入疯狂，要求其表现为某角色。", first_night=15, other_night=15),
        Role("Pit-Hag", ROLE_MINION, TEAM_EVIL, "每夜改变一名玩家角色，可能造成异常死亡。", other_night=25),
        Role("Fang Gu", ROLE_DEMON, TEAM_EVIL, "每夜杀人；首次杀死外来者时可能跳转到该外来者。", outsider_delta=1, other_night=100),
        Role("Vigormortis", ROLE_DEMON, TEAM_EVIL, "每夜杀人；爪牙被杀后仍保留能力但毒害邻近镇民。", outsider_delta=-1, other_night=100),
        Role("No Dashii", ROLE_DEMON, TEAM_EVIL, "每夜杀人；邻近镇民中毒。", other_night=100),
        Role("Vortox", ROLE_DEMON, TEAM_EVIL, "每夜杀人；镇民信息倾向错误，且不处决会导致善良失败。", other_night=100),
        Role("Barista", ROLE_TRAVELER, TEAM_GOOD, "让玩家能力强化或绕过醉酒/中毒。"),
        Role("Harlot", ROLE_TRAVELER, TEAM_EVIL, "夜晚选择玩家，若对方同意则得知其角色，失败可能死亡。"),
        Role("Butcher", ROLE_TRAVELER, TEAM_GOOD, "允许每天额外处决一次。"),
        Role("Bone Collector", ROLE_TRAVELER, TEAM_EVIL, "让死者临时恢复能力。"),
        Role("Deviant", ROLE_TRAVELER, TEAM_GOOD, "若逗乐说书人，可能被处决。"),
    ),
)


SCRIPTS = {
    TROUBLE_BREWING.script_id: TROUBLE_BREWING,
    BAD_MOON_RISING.script_id: BAD_MOON_RISING,
    SECTS_AND_VIOLETS.script_id: SECTS_AND_VIOLETS,
}

SCRIPT_ALIASES = {
    alias: script.script_id
    for script in SCRIPTS.values()
    for alias in (script.script_id, script.name, *script.aliases)
}


def resolve_script(value: str | None) -> Script:
    if not value:
        return TROUBLE_BREWING
    key = value.strip().lower().replace(" ", "_").replace("-", "_")
    script_id = SCRIPT_ALIASES.get(key)
    if script_id is None:
        known = ", ".join(script.script_id for script in SCRIPTS.values())
        raise ValueError(f"Unknown script '{value}'. Known scripts: {known}")
    return SCRIPTS[script_id]
