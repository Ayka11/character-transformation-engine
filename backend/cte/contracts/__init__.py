"""Canonical CTE runtime contracts."""
from .errors import CTEError, CTEErrorCode
from .state import StateSnapshot, StateDiff, StateDiffEngine
from .transformation import TransformationContract, TransformationResult, validate_transition
