# Temporal Clinical Decision State Reconstruction

A Python prototype for reconstructing **what information is available at a specific clinical decision time** from longitudinal records. The project focuses on temporal correctness, evidence provenance, and preventing future information leakage in AI evaluation.

**Status:** Initial scaffold. Data schemas, synthetic timelines, and validation tests are implemented. Decision state reconstruction and evaluation are planned.

## Installation

Requires Python 3.11+.

```bash
git clone https://github.com/Xingming-Li/clinical-decision-states.git
cd clinical-decision-states

pip install -e ".[dev]"  # Install dependencies
pytest                   # Run validation tests
```

## Data Model (`src/cds/schema.py`)

`ClinicalEvent` schema includes:

- `patient_id`, `event_id`, `event_type`
- `event_time`: When an event occurred
- `available_time`: When its information became available (`null` if unavailable)
- `source_type`, `payload`

The distinction between event time and availability time is essential. A pathology result may become available days after a biopsy, while a scheduled procedure may be known before it occurs.

`PatientTimeline` validates patient identifiers and event uniqueness. Timestamps include timezone information.

## Synthetic Data

Three entirely fictional breast cancer timelines illustrate:

1. Delayed pathology reporting
2. Prospectively scheduled surgery
3. Missing test results

Fixtures are located in `data/synthetic/`.

```python
from cds import load_synthetic_timelines

for timeline in load_synthetic_timelines():
    print(timeline.patient_id, len(timeline.events))
```

## Direction

Planned development includes:

- Reconstructing decision state snapshots at specified timestamps
- Tracking evidence provenance
- Evaluating temporal leakage and missing evidence
- Creating reproducible benchmark scenarios

The prototype is conceptually related to my repo [probabilistic-ssm](https://github.com/Xingming-Li/probabilistic-ssm), which models evolving physiological states using Kalman filtering. This project instead focuses on information availability and temporal consistency.

## Limitations

All records are synthetic. The current implementation does not perform decision state reconstruction, clinical reasoning, or treatment recommendations. Clinical payloads are not fully verified, and no clinical validity is claimed.
