#!/usr/bin/env python3
"""
RAG 功能验收脚本

用法：python scripts/rag/verify_rag.py
"""
import sys
import os
import time

backend_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'backend')
sys.path.insert(0, os.path.abspath(backend_dir))

import sqlite3
from core.database import get_db_connection
from services.radar_service.vector_store import (
    retrieve_similar_cases,
    batch_index_ai_results,
    get_collection_stats,
    _post_id_to_qdrant_id,
)
from services.radar_service.db_manager import save_ai_result


def step1_data_integrity():
    """1. 数据完整性"""
    print("\n" + "=" * 50)
    print("[CHECK 1] Data Integrity")
    print("=" * 50)

    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM ai_results')
        sqlite_count = cur.fetchone()[0]

    stats = get_collection_stats()
    qdrant_count = stats.get('vectors_count') or stats.get('points_count')

    print(f"  SQLite ai_results: {sqlite_count}")
    print(f"  Qdrant points:     {qdrant_count}")

    if sqlite_count == qdrant_count:
        print("  [PASS] Counts match")
        return True
    else:
        print(f"  [FAIL] Mismatch, diff={abs(sqlite_count - qdrant_count)}")
        return False


def step2_retrieval_functional():
    """2. 检索功能验证"""
    print("\n" + "=" * 50)
    print("[CHECK 2] Retrieval Function")
    print("=" * 50)

    keyword = "北京银行"
    query = "银行服务态度恶劣"
    cases = retrieve_similar_cases(keyword, query, top_k=3)

    print(f"  Query: keyword={keyword}, text='{query}'")
    print(f"  Returned {len(cases)} results:")

    for i, c in enumerate(cases, 1):
        score = c.get("score", 0)
        level = c.get("risk_level", "?")
        issue = c.get("core_issue", "?")
        title = c.get("title", "?")[:20]
        print(f"    {i}. score={score:.3f} | level={level} | issue={issue}")
        print(f"       title={title}")

    all_pass = True
    if len(cases) == 0:
        print("  [FAIL] No results returned")
        all_pass = False
    elif all(c.get("score", 0) < 0.3 for c in cases):
        print("  [WARN] All scores too low")
        all_pass = False
    else:
        print("  [PASS] Retrieval works")

    return all_pass


def step3_keyword_isolation():
    """3. Keyword 隔离验证"""
    print("\n" + "=" * 50)
    print("[CHECK 3] Keyword Isolation")
    print("=" * 50)

    bank_cases = retrieve_similar_cases("北京银行", "银行被投诉", top_k=3)
    huawei_cases = retrieve_similar_cases("华为", "手机坏了", top_k=3)

    bank_ok = all(c.get("keyword") == "北京银行" for c in bank_cases) if bank_cases else False
    huawei_ok = all(c.get("keyword") == "华为" for c in huawei_cases) if huawei_cases else False

    print(f"  北京银行: {len(bank_cases)} results, all keyword=北京银行: {bank_ok}")
    print(f"  华为:     {len(huawei_cases)} results, all keyword=华为: {huawei_ok}")

    if bank_ok and huawei_ok:
        print("  [PASS] Keyword filtering works")
        return True
    else:
        print("  [FAIL] Cross-keyword contamination detected")
        return False


def step4_async_index():
    """4. 异步索引验证"""
    print("\n" + "=" * 50)
    print("[CHECK 4] Async Indexing")
    print("=" * 50)

    test_id = f"TEST_RAG_{int(time.time())}"
    save_ai_result(
        post_id=test_id,
        platform="wb",
        keyword="验收测试",
        title="验收测试标题",
        content="这是验收测试的正文内容",
        url="http://test.com",
        risk_level="2",
        core_issue="测试问题",
        report="测试报告",
        publish_time="2026-03-29"
    )
    print(f"  Wrote test record post_id={test_id}, waiting 3s for async index...")

    time.sleep(3)

    cases = retrieve_similar_cases("验收测试", "验收测试正文", top_k=1)
    found = any(c.get("post_id") == test_id for c in cases)

    if found:
        print(f"  [PASS] New record found via RAG retrieval")
        return True
    else:
        print(f"  [WARN] Not yet indexed (async thread may need more time)")
        return None


def main():
    print("\n" + "=" * 50)
    print("  MediaRadar RAG Verification")
    print("=" * 50)

    results = {}
    results["Data Integrity"] = step1_data_integrity()
    results["Retrieval"] = step2_retrieval_functional()
    results["Keyword Isolation"] = step3_keyword_isolation()
    results["Async Index"] = step4_async_index()

    print("\n" + "=" * 50)
    print("  Summary")
    print("=" * 50)

    for name, result in results.items():
        if result is True:
            status = "[PASS]"
        elif result is False:
            status = "[FAIL]"
        else:
            status = "[WARN]"
        print(f"  {name}: {status}")

    all_pass = all(r is True for r in results.values())
    print()
    if all_pass:
        print("All checks passed. RAG is ready.")
    else:
        print("Some checks failed. Please review.")


if __name__ == "__main__":
    main()
