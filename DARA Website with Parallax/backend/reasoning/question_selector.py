from __future__ import annotations

from dataclasses import dataclass, field
from math import log2
from typing import Any, Iterable, Mapping, Sequence

from .scoring import compute_entropy


@dataclass(frozen=True)
class QuestionOption:
    id: str
    text: str
    feature: str
    answer_distributions: dict[str, dict[str, float]] = field(default_factory=dict)
    weight: float = 1.0

    def has_distributions(self) -> bool:
        return bool(self.answer_distributions)


class QuestionSelector:
    """Select the next question by expected information gain when possible.

    If answer distributions are available, the selector computes the expected
    reduction in entropy for each candidate question, i.e. EIG(question) =
    H(current) - Σ P(answer) * H(after answer). This is the only true
    information-gain formulation in this implementation.

    When the knowledge base does not provide answer distributions, the selector
    falls back to a weighted-information heuristic that ranks questions by
    uncertainty reduction potential using normalized likelihood spread and
    feature relevance, rather than pretending to know a full EIG distribution.
    """

    def __init__(
        self,
        config: Mapping[str, float] | None = None,
    ) -> None:
        self.config = {
            "min_question_weight": 0.0,
            "default_question_weight": 1.0,
        }
        if config:
            self.config.update(config)

    def select_question(
        self,
        score_results: Sequence[Mapping[str, Any]],
        questions: Iterable[QuestionOption],
    ) -> QuestionOption | None:
        candidate_questions = list(questions)
        if not candidate_questions:
            return None

        current_distribution = self._probability_distribution(score_results)
        current_entropy = compute_entropy(list(current_distribution.values()))

        if not current_distribution or current_entropy <= 0.0:
            return self._highest_priority_question(candidate_questions)

        eig_candidates: list[tuple[float, QuestionOption]] = []
        for question in candidate_questions:
            if question.has_distributions():
                eig = self._expected_information_gain(question, current_distribution)
            else:
                eig = self._weighted_information_heuristic(question, current_distribution)
            eig_candidates.append((float(eig), question))

        if not eig_candidates:
            return self._highest_priority_question(candidate_questions)

        _, best_question = max(eig_candidates, key=lambda item: (item[0], item[1].weight))
        return best_question

    def _probability_distribution(self, score_results: Sequence[Mapping[str, Any]]) -> dict[str, float]:
        if not score_results:
            return {}

        values = {
            str(item.get("cause_id", index)): float(item.get("normalized_likelihood", 0.0))
            for index, item in enumerate(score_results)
        }
        total = sum(max(v, 0.0) for v in values.values())
        if total <= 0.0:
            return {cause_id: 0.0 for cause_id in values}
        return {cause_id: max(0.0, value) / total for cause_id, value in values.items()}

    def _expected_information_gain(
        self,
        question: QuestionOption,
        current_distribution: Mapping[str, float],
    ) -> float:
        current_entropy = compute_entropy(list(current_distribution.values()))
        if current_entropy <= 0.0:
            return 0.0

        total_expected = 0.0
        for answer, conditional in question.answer_distributions.items():
            if not conditional:
                continue
            answer_probability = self._answer_probability(conditional, current_distribution)
            if answer_probability <= 0.0:
                continue
            post_answer_distribution = self._posterior_distribution(conditional, current_distribution)
            total_expected += answer_probability * compute_entropy(post_answer_distribution)

        return max(0.0, current_entropy - total_expected)

    def _answer_probability(
        self,
        conditional: Mapping[str, float],
        current_distribution: Mapping[str, float],
    ) -> float:
        if not current_distribution or sum(current_distribution.values()) <= 0.0:
            return 0.0
        return sum(
            float(current_weight) * max(0.0, float(conditional.get(cause_id, 0.0)))
            for cause_id, current_weight in current_distribution.items()
        )

    def _posterior_distribution(
        self,
        conditional: Mapping[str, float],
        current_distribution: Mapping[str, float],
    ) -> list[float]:
        unnormalized = [
            float(prior) * max(0.0, float(conditional.get(cause_id, 0.0)))
            for cause_id, prior in current_distribution.items()
        ]
        return self._normalize_distribution(unnormalized)

    def _weighted_information_heuristic(
        self,
        question: QuestionOption,
        current_distribution: Mapping[str, float],
    ) -> float:
        probabilities = list(current_distribution.values())
        uncertainty_mass = sum(float(p) for p in probabilities if 0.0 < float(p) < 1.0)
        spread = max(0.0, 1.0 - max(probabilities, default=0.0))
        feature_relevance = 1.0 + min(1.0, (len(probabilities) - 1) / 10.0)
        base_score = (uncertainty_mass * 0.7) + (spread * 0.3)
        return float(question.weight) * float(base_score) * feature_relevance

    def _highest_priority_question(self, questions: Sequence[QuestionOption]) -> QuestionOption | None:
        if not questions:
            return None
        return max(questions, key=lambda q: q.weight)

    def _normalize_distribution(self, values: Mapping[str, float] | Sequence[float]) -> list[float]:
        if isinstance(values, Mapping):
            items = [float(v) for v in values.values()]
        else:
            items = [float(v) for v in values]

        total = sum(max(v, 0.0) for v in items)
        if total <= 0.0:
            return [0.0 for _ in items]
        return [max(0.0, v) / total for v in items]