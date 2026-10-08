"""Explicit August gates and visibly provisional interpretations.

The published schema and earlier Round 1 rubric are not supplied. Internal
validation and known-gate success must never imply official acceptance.
"""

VERSION = 'assignment-aug2026-provisional-v2'
WALL_RELATIVE_TOLERANCE = {'photos': .08, 'video': .03}
OPENING_WIDTH_TOLERANCE_M = .02
OPENING_SUCCESS_FRACTION = .85
CEILING_TOLERANCE_M = .015
CEILING_REPEAT_TOLERANCE_M = .01
WALL_REPEAT_ABSOLUTE_M = .01
WALL_REPEAT_RELATIVE = .005
PHOTO_FOOTPRINT_RELATIVE = .08
ASSIGNMENT_CONFIDENCE = .90
EXTERNAL_SPECIFICATIONS = [
    'published JSON schema', 'earlier Round 1 gates',
    'LiDAR wall tolerance', 'interval coverage rule',
]
PROVISIONAL_INTERPRETATIONS = {
    'opening_denominator': 'reference opening count plus phantom count',
    'opening_matching': 'room identity, kind and <=30 cm centre distance; never width',
    'room_overlap_epsilon_m2': 1e-4,
    'wall_gate_aggregation': 'every surveyed eligible wall must pass',
    'consumer_tie_epsilon_m': 1e-9,
    'nominal_confidence': ASSIGNMENT_CONFIDENCE,
}
