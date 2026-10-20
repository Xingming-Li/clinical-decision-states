"""Schema validation tests."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from cds import ClinicalEvent, EventType, PatientTimeline, SourceType

CET = timezone(timedelta(hours=1))


def make_event(**overrides) -> ClinicalEvent:
    defaults = dict(
        patient_id="SYNTH-999",
        event_id="e01",
        event_type=EventType.IMAGING_REPORT,
        event_time=datetime(2024, 3, 4, 9, 15, tzinfo=CET),
        available_time=datetime(2024, 3, 4, 14, 40, tzinfo=CET),
        source_type=SourceType.RADIOLOGY_SYSTEM,
        payload={"modality": "mammography"},
    )
    return ClinicalEvent(**{**defaults, **overrides})


class TestTimestamps:
    def test_naive_event_time_is_rejected(self):
        with pytest.raises(ValidationError, match="timezone-aware"):
            make_event(event_time=datetime(2024, 3, 4, 9, 15))

    def test_naive_available_time_is_rejected(self):
        with pytest.raises(ValidationError, match="timezone-aware"):
            make_event(available_time=datetime(2024, 3, 4, 14, 40))

    def test_offset_is_preserved_through_a_json_round_trip(self):
        event = make_event()
        restored = ClinicalEvent.model_validate_json(event.model_dump_json())
        assert restored == event
        assert restored.event_time.utcoffset() == timedelta(hours=1)


class TestTimingSemantics:
    def test_delayed_report_has_positive_lag(self):
        event = make_event(available_time=datetime(2024, 3, 15, 14, 40, tzinfo=CET))
        assert event.information_lag == timedelta(days=11, minutes=325)

    def test_scheduled_event_may_be_available_before_it_occurs(self):
        """A booked surgery is known weeks ahead; negative lag is legal."""
        event = make_event(
            event_type=EventType.PROCEDURE,
            event_time=datetime(2024, 10, 29, 7, 30, tzinfo=CET),
            available_time=datetime(2024, 9, 24, 9, 40, tzinfo=CET),
            source_type=SourceType.EHR_ORDER,
        )
        assert event.information_lag < timedelta(0)

    def test_missing_observation_has_no_lag_and_is_never_available(self):
        event = make_event(available_time=None)
        assert event.information_lag is None
        assert not event.is_available_at(datetime(2099, 1, 1, tzinfo=timezone.utc))

    def test_is_available_at_is_inclusive_of_the_availability_instant(self):
        event = make_event()
        assert event.is_available_at(event.available_time)
        assert not event.is_available_at(event.available_time - timedelta(seconds=1))

    def test_is_available_at_rejects_a_naive_query_time(self):
        with pytest.raises(ValueError, match="timezone-aware"):
            make_event().is_available_at(datetime(2024, 3, 4, 14, 40))


class TestFieldConstraints:
    def test_unknown_fields_are_rejected(self):
        with pytest.raises(ValidationError):
            make_event(clinician_name="Dr Example")

    def test_empty_identifiers_are_rejected(self):
        with pytest.raises(ValidationError):
            make_event(event_id="")

    def test_unknown_event_type_is_rejected(self):
        with pytest.raises(ValidationError):
            make_event(event_type="horoscope")

    def test_payload_and_available_time_are_optional(self):
        event = ClinicalEvent(
            patient_id="SYNTH-999",
            event_id="e01",
            event_type=EventType.CLINICAL_NOTE,
            event_time=datetime(2024, 3, 4, 9, 15, tzinfo=CET),
            source_type=SourceType.EHR_NOTE,
        )
        assert event.payload == {}
        assert event.available_time is None


class TestPatientTimeline:
    def test_duplicate_event_ids_within_a_patient_are_rejected(self):
        with pytest.raises(ValidationError, match="duplicate event_id"):
            PatientTimeline(
                patient_id="SYNTH-999",
                events=[make_event(event_id="e01"), make_event(event_id="e01")],
            )

    def test_same_event_id_in_different_patients_is_allowed(self):
        """Uniqueness is scoped to one timeline, not global."""
        a = PatientTimeline(patient_id="SYNTH-999", events=[make_event(event_id="e01")])
        b = PatientTimeline(
            patient_id="SYNTH-998",
            events=[make_event(event_id="e01", patient_id="SYNTH-998")],
        )
        assert a.events[0].event_id == b.events[0].event_id

    def test_mismatched_patient_id_is_rejected(self):
        with pytest.raises(ValidationError, match="expected 'SYNTH-998'"):
            PatientTimeline(patient_id="SYNTH-998", events=[make_event()])

    def test_events_are_stored_in_event_time_order(self):
        later = make_event(event_id="e02", event_time=datetime(2024, 4, 1, tzinfo=CET))
        earlier = make_event(event_id="e01", event_time=datetime(2024, 3, 1, tzinfo=CET))
        timeline = PatientTimeline(patient_id="SYNTH-999", events=[later, earlier])
        assert [e.event_id for e in timeline.events] == ["e01", "e02"]

    def test_empty_timeline_is_valid(self):
        assert PatientTimeline(patient_id="SYNTH-999").events == []
