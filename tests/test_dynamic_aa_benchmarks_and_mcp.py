from __future__ import annotations

import pytest
from services.benchmarks_client import benchmarks_client
from services.mcp_hub import mcp_hub
from storage.repository import aa_benchmarks_repo


def test_aa_benchmarks_repository_crud_and_metrics():
    models = [
        {
            'id': 'google/gemini-3.7-flash',
            'slug': 'gemini-3-7-flash',
            'name': 'Gemini 3.7 Flash (high)',
            'creator_name': 'Google',
            'coding_index': 76.1,
            'intelligence_index': 56.0,
            'terminalbench_v2_1': 0.8576,
            'gpqa_diamond': 0.945,
            'scicode': 0.568,
            'price_in_usd': 0.375,
            'price_out_usd': 1.875,
            'evaluations': {
                'artificial_analysis_coding_index': 76.1,
                'terminalbench_v2_1': 0.8576,
                'gpqa': 0.945,
            },
        },
        {
            'id': 'z-ai/glm-5.3-flash',
            'slug': 'glm-5-3-flash',
            'name': 'GLM-5.3-Flash',
            'creator_name': 'Z AI',
            'coding_index': 71.5,
            'intelligence_index': 57.5,
            'terminalbench_v2_1': 0.8427,
            'gpqa_diamond': 0.912,
            'scicode': 0.461,
            'price_in_usd': 0.075,
            'price_out_usd': 0.25,
            'evaluations': {
                'artificial_analysis_coding_index': 71.5,
                'terminalbench_v2_1': 0.8427,
                'gpqa': 0.912,
            },
        },
    ]

    count = aa_benchmarks_repo.upsert_all(models)
    assert count == 2

    gemini = aa_benchmarks_repo.find_by_slug('gemini-3-7-flash')
    assert gemini is not None
    assert gemini['coding_index'] == 76.1
    assert gemini['terminalbench_v2_1'] == 0.8576

    keys = aa_benchmarks_repo.get_available_metric_keys()
    assert 'artificial_analysis_coding_index' in keys
    assert 'terminalbench_v2_1' in keys


def test_mcp_tool_get_catalog_capabilities():
    res = mcp_hub.execute_tool('get_catalog_capabilities', {})
    assert res['status'] == 'success'
    assert res['total_models'] >= 2
    assert isinstance(res['available_benchmark_metrics'], list)


def test_mcp_tool_search_models_catalog_with_dynamic_filters():
    res_text = mcp_hub.execute_tool('search_models_catalog', {'q': 'gemini', 'limit': 2})
    assert res_text['status'] == 'success'
    assert len(res_text['models']) > 0
    assert 'gemini' in res_text['models'][0]['slug'].lower()

    res_bench = mcp_hub.execute_tool(
        'search_models_catalog',
        {
            'benchmark_filters': {'terminalbench': 0.85},
            'max_price_out_usd': 3.0,
            'limit': 5,
        },
    )
    assert res_bench['status'] == 'success'
    for m in res_bench['models']:
        assert m['price_out_usd'] <= 3.0
        assert (m['terminalbench_v2_1'] or 0.0) >= 0.85


def test_benchmarks_client_sync_status_and_scheduler():
    status = benchmarks_client.get_sync_status()
    assert 'total_models' in status
    assert 'next_scheduled_sync' in status
    assert status['total_models'] > 0


def test_mcp_web_search_live_and_untrusted_capsule():
    res = mcp_hub.execute_tool('web_search', {'query': 'Artificial Analysis AI benchmarks', 'max_results': 2})
    assert res['status'] == 'success'
    assert 'results' in res
    assert '<external_untrusted_data>' in res['results']
    assert '</external_untrusted_data>' in res['results']
