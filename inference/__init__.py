"""M6: inference engine. Forward chaining over the knowledge base's rules."""

from .engine import Diagnosis, InferenceEngine, InferenceResult

__all__ = ["InferenceEngine", "Diagnosis", "InferenceResult"]
