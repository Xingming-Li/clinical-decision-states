"""Tests that the synthetic fixtures parse and cover the intended edge cases."""

from datetime import timedelta

import pytest

from clinical_decision_states import (
    SYNTHETIC_DATA_DIR,
    EventType,
    load_synthetic_timelines,
)

EXPECTED_PATIENT_IDS = ["SYNTH-001", "SYNTH-002", "SYNTH-003"]


@pytest.fixture(scope="module")
def timelines():
    return load_synthetic_timelines()


def test_fixture_directory_exists():
    assert SYNTHETIC_DATA_DIR.is_dir(), SYNTHETIC_DATA_DIR


def test_all_fixtures_load_and_validate(timelines):
    assert [t.patient_id for t in timelines] == EXPECTED_PATIENT_IDS
    assert all(len(t.events) >= 4 for t in timelines)


def test_every_event_is_timezone_aware(timelines):
    for timeline in timelines:
        for event in timeline.events:
            assert event.event_time.utcoffset() is not None
            if event.available_time is not None:
                assert event.available_time.utcoffset() is not None


def test_every_timeline_contains_a_decision_event(timelines):
    for timeline in timelines:
        types = {e.event_type for e in timeline.events}
        assert EventType.DECISION in types, timeline.patient_id


def test_imaging_pathology_and_notes_are_represented(timelines):
    types = {e.event_type for t in timelines for e in t.events}
    assert {
        EventType.IMAGING_REPORT,
        EventType.PATHOLOGY_REPORT,
        EventType.CLINICAL_NOTE,
        EventType.DECISION,
    } <= types


def test_fixtures_include_a_delayed_report(timelines):
    delayed = [
        e
        for t in timelines
        for e in t.events
        if e.information_lag is not None and e.information_lag > timedelta(days=7)
    ]
    assert delayed, "expected at least one report delayed by more than a week"


def test_fixtures_include_a_missing_observation(timelines):
    missing = [e for t in timelines for e in t.events if e.available_time is None]
    assert len(missing) == 1
    assert missing[0].event_id == "e03"
    assert missing[0].patient_id == "SYNTH-003"


def test_fixtures_include_a_prospectively_scheduled_event(timelines):
    early = [
        e
        for t in timelines
        for e in t.events
        if e.information_lag is not None and e.information_lag < timedelta(0)
    ]
    assert len(early) == 1
    assert early[0].event_type == EventType.PROCEDURE


def test_a_decision_precedes_availability_of_its_own_evidence(timelines):
    """SYNTH-001: the consult note at e04 is written before pathology e03 lands."""
    timeline = next(t for t in timelines if t.patient_id == "SYNTH-001")
    events = {e.event_id: e for e in timeline.events}
    assert not events["e03"].is_available_at(events["e04"].event_time)
    assert events["e03"].is_available_at(events["e05"].event_time)
