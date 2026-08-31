from __future__ import annotations

import pytest
from core.domain import FinOpsBadge
from services.benchmarks_client import benchmarks_client


def test_19_benchmarks_retrieval_and_evaluations():
    """Vérifie la présence et le détail des 19 métriques Artificial Analysis."""
    benchmarks = benchmarks_client.get_benchmarks()
    assert len(benchmarks) >= 6

    claude = next((b for b in benchmarks if "claude" in b.model_id.lower()), None)
    assert claude is not None
    assert claude.coding_score >= 90.0
    assert "terminal_bench_v2_1" in claude.evaluations
    assert "scicode" in claude.evaluations
    assert "gpqa_diamond" in claude.evaluations


def test_scientific_model_matching_algorithm():
    """Vérifie l'algorithme d'isolation des 3 benchmarks et sélection des 3 profils 1-clic."""
    matches_coding = benchmarks_client.match_best_models_for_role("coding")
    assert FinOpsBadge.TOP_PERFORMANCE in matches_coding
    assert FinOpsBadge.SWEET_SPOT in matches_coding
    assert FinOpsBadge.ULTRA_ECO in matches_coding

    top = matches_coding[FinOpsBadge.TOP_PERFORMANCE]
    assert top.coding_score >= 80.0

    matches_reasoning = benchmarks_client.match_best_models_for_role("reasoning")
    top_reasoning = matches_reasoning[FinOpsBadge.TOP_PERFORMANCE]
    assert top_reasoning.reasoning_score >= 70.0


def test_dynamic_benchmark_introspection_and_sweet_spot_card():
    """Vérifie l'introspection dynamique des clés sans hardcoding et la génération de la carte Action Card."""
    metrics = benchmarks_client.list_available_benchmark_metrics()
    assert isinstance(metrics, list)
    assert len(metrics) > 0

    # Test sur un rôle de rédaction
    card_redac = benchmarks_client.get_model_recommendation_card_data("redacteur_blog_finance")
    assert "sweet_spot" in card_redac
    assert "top_performance" in card_redac
    assert "ultra_eco" in card_redac
    assert card_redac["sweet_spot"]["quality_score"] > 0
    assert card_redac["sweet_spot"]["price_out_usd"] >= 0

    # Test calcul score dynamique
    benchmarks = benchmarks_client.get_benchmarks()
    score = benchmarks_client.compute_dynamic_quality_score(benchmarks[0])
    assert 0.0 <= score <= 100.0
