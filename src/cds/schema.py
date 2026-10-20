"""Typed schema for synthetic longitudinal clinical event records.

The schema separates two clocks that are usually collapsed into one in
retrospective datasets:

``event_time``
    When the event itself happened in the world (image acquired, specimen
    taken, meeting held).

``available_time``
    When the information about that event became usable by a clinician -
    report signed, result released to the record, note filed.

Keeping both is what makes it possible to ask "what was knowable at time T?"
rather than "what is in the record now?".
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EventType(str, Enum):
    """Kind of clinical event recorded on a timeline."""

    IMAGING_REPORT = "imaging_report"
    PATHOLOGY_REPORT = "pathology_report"
    LAB_RESULT = "lab_result"
    CLINICAL_NOTE = "clinical_note"
    PROCEDURE = "procedure"
    DECISION = "decision"


class SourceType(str, Enum):
    """System or setting the event originated from (evidence provenance)."""

    RADIOLOGY_SYSTEM = "radiology_system"
    PATHOLOGY_LAB = "pathology_lab"
    EHR_NOTE = "ehr_note"
    EHR_ORDER = "ehr_order"
    MDT_CONFERENCE = "mdt_conference"
    EXTERNAL_REFERRAL = "external_referral"


def _require_aware(value: datetime | None, field_name: str) -> datetime | None:
    """Reject naive datetimes; a timestamp without an offset is unorderable."""
    if value is not None and value.utcoffset() is None:
        raise ValueError(
            f"{field_name} must be timezone-aware "
            "(e.g. '2024-03-04T09:15:00+01:00'), got a naive datetime"
        )
    return value


class ClinicalEvent(BaseModel):
    """A single timestamped item of clinical information.

    Timing semantics
    ----------------
    ``available_time`` is deliberately *not* constrained to be later than
    ``event_time``, because both orderings occur in real records:

    * ``available_time > event_time`` - the usual retrospective case. An
      imaging study is performed, the report is signed hours or days later.
      A large positive lag is a *delayed report*.
    * ``available_time < event_time`` - a prospectively scheduled event. A
      surgery booked at a multidisciplinary meeting is known to the care team
      from the moment it is booked, weeks before it takes place. Enforcing an
      ordering constraint would make such events unrepresentable.
    * ``available_time is None`` - a *missing observation*. The event is known
      to have been ordered or to have occurred, but its information never
      entered the record within the observation window. This is distinct from
      a late result, and distinct from a result that is present but null.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    patient_id: str = Field(min_length=1)
    event_id: str = Field(min_length=1, description="Unique within one patient timeline")
    event_type: EventType
    event_time: datetime = Field(description="When the event occurred")
    available_time: datetime | None = Field(
        default=None,
        description="When the information became available; None means never observed",
    )
    source_type: SourceType
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured, event-type-specific content; not validated here",
    )

    @field_validator("event_time")
    @classmethod
    def _event_time_aware(cls, value: datetime) -> datetime:
        return _require_aware(value, "event_time")  # type: ignore[return-value]

    @field_validator("available_time")
    @classmethod
    def _available_time_aware(cls, value: datetime | None) -> datetime | None:
        return _require_aware(value, "available_time")

    @property
    def information_lag(self) -> timedelta | None:
        """``available_time - event_time``; None if never available.

        Negative values are legitimate and mark prospectively known events.
        """
        if self.available_time is None:
            return None
        return self.available_time - self.event_time

    def is_available_at(self, when: datetime) -> bool:
        """Whether this event's information was in hand at ``when``."""
        _require_aware(when, "when")
        return self.available_time is not None and self.available_time <= when


class PatientTimeline(BaseModel):
    """All recorded events for one synthetic patient.

    Events are held in ``event_time`` order. Note that this is not necessarily
    their ``available_time`` order - the divergence between the two is the
    phenomenon this project studies.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    patient_id: str = Field(min_length=1)
    events: list[ClinicalEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_and_order(self) -> "PatientTimeline":
        seen: set[str] = set()
        for event in self.events:
            if event.patient_id != self.patient_id:
                raise ValueError(
                    f"event {event.event_id!r} has patient_id "
                    f"{event.patient_id!r}, expected {self.patient_id!r}"
                )
            if event.event_id in seen:
                raise ValueError(
                    f"duplicate event_id {event.event_id!r} in timeline "
                    f"{self.patient_id!r}; event IDs must be unique per patient"
                )
            seen.add(event.event_id)

        self.events.sort(key=lambda e: (e.event_time, e.event_id))
        return self
