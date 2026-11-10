"""Task state machine.

Legal lifecycle:
draft -> published -> assigned -> accepted -> in_progress -> submitted -> verified -> completed
Side states: rejected, expired, failed, cancelled, reassigned.
"""

from __future__ import annotations

from dataclasses import dataclass


class TaskStateError(ValueError):
    """Raised when a transition is illegal or the actor lacks permission."""


TRANSITIONS: dict[str, set[str]] = {
    "draft": {"published", "cancelled"},
    "published": {"assigned", "cancelled", "expired"},
    "assigned": {"accepted", "rejected", "expired", "cancelled", "reassigned"},
    "reassigned": {"assigned", "failed", "cancelled"},
    "accepted": {"in_progress", "failed", "expired", "cancelled"},
    "in_progress": {"submitted", "failed", "expired"},
    "submitted": {"verified", "rejected"},
    "verified": {"completed"},
    "rejected": {"published", "failed", "cancelled"},
    "failed": {"published"},
    "expired": set(),
    "completed": set(),
    "cancelled": set(),
}

# admin is listed explicitly so the permission table is auditable.
ROLE_PERMISSIONS: dict[tuple[str, str], set[str]] = {
    ("draft", "published"): {"publisher", "admin"},
    ("draft", "cancelled"): {"publisher", "admin"},
    ("published", "assigned"): {"publisher", "admin", "system"},
    ("published", "cancelled"): {"publisher", "admin"},
    ("published", "expired"): {"admin", "system"},
    ("assigned", "accepted"): {"collector", "admin", "system"},
    ("assigned", "rejected"): {"collector", "admin", "system"},
    ("assigned", "expired"): {"admin", "system"},
    ("assigned", "cancelled"): {"publisher", "admin"},
    ("assigned", "reassigned"): {"publisher", "admin", "system"},
    ("reassigned", "assigned"): {"publisher", "admin", "system"},
    ("reassigned", "failed"): {"admin", "system"},
    ("reassigned", "cancelled"): {"publisher", "admin"},
    ("accepted", "in_progress"): {"collector", "admin", "system"},
    ("accepted", "failed"): {"collector", "admin", "system"},
    ("accepted", "expired"): {"admin", "system"},
    ("accepted", "cancelled"): {"publisher", "admin"},
    ("in_progress", "submitted"): {"collector", "admin", "system"},
    ("in_progress", "failed"): {"collector", "admin", "system"},
    ("in_progress", "expired"): {"admin", "system"},
    ("submitted", "verified"): {"publisher", "admin", "system"},
    ("submitted", "rejected"): {"publisher", "admin"},
    ("verified", "completed"): {"publisher", "admin", "system"},
    ("rejected", "published"): {"publisher", "admin"},
    ("rejected", "failed"): {"admin", "system"},
    ("rejected", "cancelled"): {"publisher", "admin"},
    ("failed", "published"): {"admin"},
}

TERMINAL_STATES = {"completed", "cancelled", "expired"}


@dataclass(frozen=True)
class TransitionContext:
    role: str
    now_slot: int | None = None
    slot_end: int | None = None
    has_measurement: bool = False
    assignee_matches: bool = True


def check_transition(src: str, dst: str, ctx: TransitionContext) -> None:
    if src not in TRANSITIONS:
        raise TaskStateError(f"unknown state: {src}")
    if dst not in TRANSITIONS[src]:
        raise TaskStateError(f"illegal transition {src} -> {dst}")
    allowed = ROLE_PERMISSIONS.get((src, dst), set())
    if ctx.role not in allowed:
        raise TaskStateError(f"role '{ctx.role}' cannot perform {src} -> {dst}")
    if dst == "expired":
        if ctx.now_slot is None or ctx.slot_end is None or ctx.now_slot <= ctx.slot_end:
            raise TaskStateError("time window has not expired")
    if dst == "submitted" and not ctx.has_measurement:
        raise TaskStateError("submission requires a measurement")
    if ctx.role == "collector" and dst in {"accepted", "rejected", "in_progress", "submitted", "failed"}:
        if not ctx.assignee_matches:
            raise TaskStateError("collector can only act on an assigned task")


def legal_targets(src: str, ctx: TransitionContext) -> list[str]:
    targets = []
    for dst in sorted(TRANSITIONS.get(src, set())):
        try:
            check_transition(src, dst, ctx)
        except TaskStateError:
            continue
        targets.append(dst)
    return targets
