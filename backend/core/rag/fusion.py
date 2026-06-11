"""Reciprocal Rank Fusion for hybrid retrieval.

RRF(d) = sum_over_rankings( weight / (k + rank(d)) ), rank is 1-indexed.
k=60 follows the original SIGIR 2009 paper.
"""


def rrf_fuse(
    *,
    rankings: dict[str, list],
    weights: dict[str, float],
    k: int = 60,
) -> list:
    """Fuse multiple rankings into one, best first.

    Args:
        rankings: name -> ordered list of hashable keys (best first)
        weights: name -> weight multiplier for that ranking
        k: RRF constant
    """
    scores: dict = {}
    for name, ranked in rankings.items():
        weight = weights.get(name, 1.0)
        for position, key in enumerate(ranked, start=1):
            scores[key] = scores.get(key, 0.0) + weight / (k + position)

    return sorted(scores, key=lambda key: (-scores[key], str(key)))
