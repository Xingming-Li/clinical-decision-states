"""Temporal Clinical Decision-State Reconstruction.

Schema and synthetic fixtures for reasoning about what clinical information
was available at a given decision time. Synthetic data only; see README.
"""

from .loader import SYNTHETIC_DATA_DIR, load_synthetic_timelines, load_timeline
from .schema import ClinicalEvent, EventType, PatientTimeline, SourceType

__version__ = "0.1.0"

__all__ = [
    "ClinicalEvent",
    "EventType",
    "PatientTimeline",
    "SourceType",
    "SYNTHETIC_DATA_DIR",
    "load_synthetic_timelines",
    "load_timeline",
    "__version__",
]
