"""Data models for Habits agent state."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --- Enums ---


class ConversationPhase(str, Enum):
    ONBOARDING_GOAL = "onboarding_goal"
    ONBOARDING_SCHEDULE = "onboarding_schedule"
    PLAN_PROPOSED = "plan_proposed"
    PLAN_CONFIRMED = "plan_confirmed"
    CHECK_IN = "check_in"


class GoalType(str, Enum):
    FITNESS = "fitness"


class GoalStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class SessionType(str, Enum):
    STRENGTH = "strength"
    CARDIO = "cardio"
    FLEXIBILITY = "flexibility"
    MIXED = "mixed"


class SessionStatus(str, Enum):
    UPCOMING = "upcoming"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    PARTIAL = "partial"
    DELETED_BY_USER = "deleted_by_user"
    CANCELLED = "cancelled"


# --- Sub-models ---


class FitnessPreferences(BaseModel):
    likes: list[str] = Field(default_factory=list)
    dislikes: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)


class TimeWindow(BaseModel):
    start: str  # HH:MM format
    end: str  # HH:MM format


class RoutineBlock(BaseModel):
    label: str
    days: list[str]  # e.g. ["monday", "tuesday", ...]
    start: str  # HH:MM format
    end: str  # HH:MM format


# --- Top-level models ---


class User(BaseModel):
    user_id: str = "joe"
    name: str = ""
    timezone: str = "Europe/London"
    conversation_phase: ConversationPhase = ConversationPhase.ONBOARDING_GOAL
    last_conversation_date: Optional[datetime] = None
    write_calendar_id: Optional[str] = None
    read_calendar_ids: list[str] = Field(default_factory=list)


class Goal(BaseModel):
    goal_id: str = "goal_001"
    user_id: str = "joe"
    description: str = ""
    goal_type: GoalType = GoalType.FITNESS
    fitness_level: str = ""
    preferences: FitnessPreferences = Field(default_factory=FitnessPreferences)
    weekly_time_commitment_minutes: Optional[int] = None
    created_at: Optional[datetime] = None
    status: GoalStatus = GoalStatus.ACTIVE


class ScheduleContext(BaseModel):
    user_id: str = "joe"
    sleep_window: Optional[TimeWindow] = None
    routine_blocks: list[RoutineBlock] = Field(default_factory=list)
    preferred_exercise_times: list[str] = Field(default_factory=list)
    excluded_times: list[str] = Field(default_factory=list)


class PlannedSession(BaseModel):
    session_id: str
    goal_id: str = "goal_001"
    gcal_event_id: Optional[str] = None
    title: str
    session_type: SessionType
    duration_minutes: int
    scheduled_date: str  # YYYY-MM-DD
    scheduled_start: str  # HH:MM
    status: SessionStatus = SessionStatus.UPCOMING
    user_feedback: Optional[str] = None


class ConversationLog(BaseModel):
    log_id: str
    user_id: str = "joe"
    conversation_date: datetime
    phase_at_start: ConversationPhase
    phase_at_end: ConversationPhase
    summary: str
    adaptations_made: list[str] = Field(default_factory=list)


# --- Root state ---


class AppState(BaseModel):
    user: User = Field(default_factory=User)
    goal: Optional[Goal] = None
    schedule_context: Optional[ScheduleContext] = None
    planned_sessions: list[PlannedSession] = Field(default_factory=list)
    conversation_logs: list[ConversationLog] = Field(default_factory=list)
