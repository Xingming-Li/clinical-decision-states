# Temporal Clinical Decision-State Reconstruction

A small research prototype for reconstructing **what information was actually available at a
given clinical decision time**, from longitudinal records in which events and the availability
of information about those events are two different things.

**Status: scaffold.** This repository currently contains only the data schema, synthetic
fixtures, and their validation tests. The reconstruction method and the evaluation pipeline
are not implemented yet.

## Research objective

Retrospective clinical datasets are usually read as if the record were complete and
instantaneous: every result that eventually landed in the chart is treated as if it had been
on the table when the decision was made. It was not. Reports are signed days after the
specimen is taken, some ordered tests never result at all, and some future events (a booked
operation) are known long before they happen.

This project asks two questions over synthetic breast cancer timelines:

1. **Temporal correctness** — given a decision time `T`, can we reconstruct the subset of the
   record that was genuinely available at `T`, without leaking information that arrived later?
2. **Evidence provenance** — for a recorded decision, which specific events could have
   supported it, and which cited evidence was in fact still unavailable?

The target of reconstruction is a *decision state*: a latent, time-indexed summary of what the
care team knew. Only the information-availability structure is modelled here; the project makes
no attempt to model clinical reasoning.

### Relation to prior work

This is an independent project, but it shares a conceptual frame with
[probabilistic-ssm](https://github.com/Xingming-Li/probabilistic-ssm), which uses linear
Gaussian state-space models and Kalman filtering for longitudinal physiological modelling.
Both treat an unobserved, time-evolving state as the object of inference, recovered from
irregular observations. The difference is what obscures the state. In a state-space model the
obstacle is measurement noise, and the filtering recursion is the natural tool. Here the
obstacle is *information latency and absence* — the observation may be exact but arrive eleven
days late, or never — so the discipline needed is bookkeeping over availability times rather
than a Gaussian noise model. No state-space machinery is used or assumed in this repository.

## Installation

Requires Python ≥ 3.11.

```bash
git clone https://github.com/Xingming-Li/clinical-decision-states.git
cd clinical-decision-states
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

The only runtime dependency is `pydantic>=2.7`; `pytest` is the only development dependency.

Run the tests:

```bash
pytest
```

The pytest configuration puts `src/` on the import path, so the suite also runs from a plain
checkout without installing the package.

## Schema

Defined in [src/clinical_decision_states/schema.py](src/clinical_decision_states/schema.py).

### `ClinicalEvent`

| Field | Type | Notes |
| --- | --- | --- |
| `patient_id` | `str` | Non-empty synthetic identifier |
| `event_id` | `str` | Unique **within one patient timeline**, not globally |
| `event_type` | enum | `imaging_report`, `pathology_report`, `lab_result`, `clinical_note`, `procedure`, `decision` |
| `event_time` | aware `datetime` | When the event occurred |
| `available_time` | aware `datetime \| None` | When its information became available; `None` = never |
| `source_type` | enum | `radiology_system`, `pathology_lab`, `ehr_note`, `ehr_order`, `mdt_conference`, `external_referral` |
| `payload` | `dict[str, Any]` | Structured, event-type-specific content; not schema-validated |

Models are frozen and reject unknown fields. Naive (offset-less) timestamps are rejected
outright, since an unanchored timestamp cannot be ordered against another.

### `PatientTimeline`

Holds a `patient_id` and its `events`, and validates that every event carries the matching
`patient_id` and that no `event_id` repeats. Events are stored in `event_time` order — which is
deliberately *not* the same as their `available_time` order.

### Temporal semantics: `event_time` vs `available_time`

`event_time` is when something happened in the world. `available_time` is when a clinician
could have acted on it. The gap between them is the subject of the project, and it is **not
constrained to be positive**:

- **`available_time > event_time`** — the ordinary retrospective case. An image is acquired,
  the report is signed later. A large positive lag is a *delayed report*.
- **`available_time < event_time`** — a *prospectively scheduled* event. A surgery booked at a
  multidisciplinary meeting is known to the team from the moment it is booked, weeks before it
  takes place. A validator enforcing `available_time >= event_time` would make this case
  unrepresentable, so none is imposed.
- **`available_time is None`** — a *missing observation*. The event is known to have been
  ordered or to have occurred, but no information about it entered the record within the
  observation window. This is distinct from a late result, and distinct from a result that is
  present but null.

Two helpers follow from this: `event.information_lag` (a `timedelta`, possibly negative, or
`None`) and `event.is_available_at(t)`, which is inclusive of the availability instant and
false for missing observations.

## Synthetic data

> **Disclaimer.** All data in [data/synthetic/](data/synthetic/) is entirely fictional and was
> written by hand to exercise the schema. It is not derived from, sampled from, or de-identified
> from any real patient record, registry, or clinical dataset. The patients do not exist. The
> clinical content is plausible in shape only and should not be read as representative of real
> disease trajectories, timings, or care pathways.

Three timelines, five events each:

| File | Illustrates |
| --- | --- |
| `patient_synth_001.json` | Delayed pathology report (11 days); a consult note written while it was still pending |
| `patient_synth_002.json` | Prospectively scheduled surgery (`available_time` ~35 days before `event_time`), crossing a CEST→CET transition |
| `patient_synth_003.json` | Missing observation (`available_time: null`) for a reflex test that never resulted |

Timestamps use Stockholm offsets (`+01:00`/`+02:00`) to keep daylight-saving transitions in view.

Two conventions live in the free-form `payload` of decision events rather than in the typed
schema: `evidence_event_ids` and `unavailable_evidence_event_ids`, which record which events a
fictional decision was based on. These exist to give a future evaluation stage something to
score against. They are fixture conventions, not part of the schema, and may change.

```python
from clinical_decision_states import load_synthetic_timelines

for timeline in load_synthetic_timelines():
    print(timeline.patient_id, len(timeline.events))
```

## Limitations

- **No clinical validity is claimed.** This is a methods prototype on invented data. Nothing
  here has been validated against real records or reviewed by clinicians, and no result from it
  should inform patient care.
- **It produces no clinical recommendations** and is not designed to. Decision events in the
  fixtures are *data describing fictional past decisions*; the software does not suggest,
  rank, or evaluate treatment options.
- **Three hand-written timelines cannot support statistical claims.** They are schema
  exercises, not a sample.
- **Availability is modelled as a single instant per event.** Real information becomes
  available in stages — preliminary then final, amended, verbally communicated before being
  filed — and partially, to some members of a team but not others. None of that is captured.
- **Free-form clinical text is out of scope.** Payloads are already-structured fields; no text
  extraction is performed, and no LLM is used anywhere in this project.
- **No external clinical systems.** Nothing here reads from a clinical API, EHR, or registry.
- **`payload` is unvalidated** beyond being a JSON object, so inconsistencies within it are not
  caught by the schema.

## Not yet implemented

The reconstruction algorithm, the evaluation pipeline (temporal-correctness and
provenance metrics), notebooks, and any interface.

## License

MIT — see [LICENSE](LICENSE).
