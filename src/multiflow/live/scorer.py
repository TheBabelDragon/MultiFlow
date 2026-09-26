"""Candidate scoring interface — ranks admissible candidates only.

Scorers NEVER establish admissibility. The independent Validator is the
sole authority for correctness.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from multiflow.domain.models import CandidateSolution
from multiflow.live.features import FeatureExtractor, ScheduleFeatures
from multiflow.live.snapshot import ScheduleSnapshot
from multiflow.validation.validator import Validator


class CandidateScorer(ABC):
    """Interface for ranking admissible candidates.

    Contract:
        score(features, candidate) -> float

    Higher score is preferred. Implementations must not alter candidate
    admissibility; validation happens outside this interface.
    """

    @abstractmethod
    def score(
        self,
        features: ScheduleFeatures,
        candidate: CandidateSolution,
    ) -> float:
        """Return a numeric preference score for an already-validated candidate."""

    def rank(
        self,
        snapshot: ScheduleSnapshot,
        candidates: list[CandidateSolution],
        validator: Optional[Validator] = None,
        extractor: Optional[FeatureExtractor] = None,
    ) -> list[tuple[CandidateSolution, float]]:
        """Validate candidates, discard inadmissible, score and rank the rest.

        Returns list of (candidate, score) sorted by score descending,
        then by candidate.id for determinism.
        """
        val = validator or Validator()
        ext = extractor or FeatureExtractor(validator=val)
        admissible: list[tuple[CandidateSolution, float]] = []
        problem = snapshot.problem
        for cand in candidates:
            vr = val.validate(problem, cand)
            if not vr.admissible:
                continue
            features = ext.extract(snapshot=snapshot, candidate=cand)
            s = self.score(features, cand)
            admissible.append((cand, s))
        admissible.sort(key=lambda pair: (-pair[1], pair[0].id))
        return admissible


class DeterministicCandidateScorer(CandidateScorer):
    """Deterministic preference scorer using explicit numeric signals.

    Prefers:
      - more assigned tasks
      - lower hard violations (should already be zero for admissible)
      - lower soft penalty
      - lower objective total when minimizing
    """

    def score(
        self,
        features: ScheduleFeatures,
        candidate: CandidateSolution,
    ) -> float:
        # Primary: coverage (more assignments better)
        coverage = float(features.assignment_count)
        # Secondary: minimize soft penalty and objective total
        soft = features.candidate_soft_penalty
        obj = features.candidate_objective_total
        # Prefer lower utilization pressure as a mild tie-breaker
        util_penalty = features.mean_utilization
        # Composite: coverage dominates; penalties subtract
        return coverage * 1000.0 - soft * 10.0 - abs(obj) - util_penalty
