from __future__ import annotations

from enum import StrEnum


class Alignment(StrEnum):
    GOOD = "good"
    EVIL = "evil"


class RoleType(StrEnum):
    TOWNSFOLK = "townsfolk"
    OUTSIDER = "outsider"
    MINION = "minion"
    DEMON = "demon"
    TRAVELER = "traveler"


class GamePhase(StrEnum):
    WAITING_PLAYERS = "waiting_players"
    CONFIRMING_PLAYERS = "confirming_players"
    SETUP = "setup"
    FIRST_NIGHT = "first_night"
    DAY = "day"
    NOMINATION = "nomination"
    VOTING = "voting"
    EXECUTION = "execution"
    NIGHT = "night"
    RESOLUTION = "resolution"
    GAME_OVER = "game_over"


class Visibility(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"
    EVIL_TEAM = "evil_team"
    STORYTELLER = "storyteller"
    SYSTEM = "system"
    POSTGAME = "postgame"


class EventType(StrEnum):
    PLAYER_JOINED = "player_joined"
    PLAYER_READY = "player_ready"
    ROLE_ASSIGNED = "role_assigned"
    PHASE_CHANGED = "phase_changed"
    PUBLIC_MESSAGE = "public_message"
    PRIVATE_MESSAGE = "private_message"
    NIGHT_ACTION_SUBMITTED = "night_action_submitted"
    CONDITION_APPLIED = "condition_applied"
    PLAYER_TARGETED = "player_targeted"
    INFO_GIVEN = "info_given"
    DECISION_REQUESTED = "decision_requested"
    DECISION_APPLIED = "decision_applied"
    NOMINATION_STARTED = "nomination_started"
    VOTE_CAST = "vote_cast"
    EXECUTION_RESULT = "execution_result"
    DEATH = "death"
    REVIVAL = "revival"
    TIMER_CHANGED = "timer_changed"
    PIPELINE_ACTION = "pipeline_action"
    CORRECTION = "correction"


class ActionType(StrEnum):
    JOIN = "join"
    READY = "ready"
    START_GAME = "start_game"
    ENTER_PHASE = "enter_phase"
    SUBMIT_NIGHT_ACTION = "submit_night_action"
    GIVE_INFO = "give_info"
    APPLY_CONDITION = "apply_condition"
    NOMINATE = "nominate"
    VOTE = "vote"
    EXECUTE = "execute"
    KILL = "kill"
    REVIVE = "revive"
    EXTEND_TIMER = "extend_timer"
    SET_TIMER = "set_timer"
    PAUSE_PIPELINE = "pause_pipeline"
    RESUME_PIPELINE = "resume_pipeline"


class DecisionType(StrEnum):
    FALSE_INFORMATION = "false_information"
    SETUP_SELECTION = "setup_selection"
    MISREGISTRATION = "misregistration"
    DEATH_REDIRECT = "death_redirect"
    OPTIONAL_DEATH = "optional_death"
    TIMER_ADJUSTMENT = "timer_adjustment"
    NARRATION = "narration"
