#!/usr/bin/env python3
"""
Discovered Facts Clustering Tool.

Groups discovered facts semantically using vector embeddings or metadata clustering.
Enforces the 20-fact threshold: when facts for a subtopic exceed 20, clusters them
into bite-sized, coherent groups so subsection drafters avoid prompt flooding.
"""

import os
import sys
import json
import sqlite3
import argparse
from typing import List, Dict, Any, Optional, Tuple

# Add parent directory to path for imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from common.config import get_workspace_root
from common.citation_tracker import get_cited_quotes_map, format_citation_guidance
from vector_engine.client import deserialize_vector, dot_product


def resolve_db_path(override_path: Optional[str] = None) -> str:
    """Resolve database path in workspace root or current directory."""
    if override_path:
        return override_path
    root = get_workspace_root()
    cand = os.path.join(root, "chat.db")
    if os.path.exists(cand):
        return cand
    if os.path.exists("chat.db"):
        return "chat.db"
    return cand


def fetch_facts_and_vectors(
    conn: sqlite3.Connection,
    chat_id: str,
    category: Optional[str] = None,
    sphere_id: Optional[str] = None,
    target_agent: Optional[str] = None,
    target_chapter: Optional[str] = None,
    subtopic_filter: Optional[str] = None,
    subject: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve facts and their corresponding embeddings for clustering."""
    cur = conn.cursor()
    
    # Check tables
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='discovered_facts';")
    if cur.fetchone()[0] == 0:
        return []

    has_embeddings = False
    cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='fact_embeddings';")
    if cur.fetchone()[0] > 0:
        has_embeddings = True

    sql = """
    SELECT f.fact_id, f.chat_id, f.thread_id, f.anchor_msg_id, f.category,
           f.sphere_id, f.target_agent, f.fact_summary, f.verbatim_quote,
           coalesce(f.subject, ''),
           """ + ("fe.embedding" if has_embeddings else "NULL") + """
    FROM discovered_facts f
    """
    if has_embeddings:
        sql += " LEFT JOIN fact_embeddings fe ON f.fact_id = fe.fact_id "

    sql += " WHERE f.chat_id = ? "
    params: List[Any] = [chat_id]

    if category:
        sql += " AND lower(f.category) = lower(?) "
        params.append(category)
    if sphere_id:
        sql += " AND upper(f.sphere_id) = upper(?) "
        params.append(sphere_id)
    if target_agent:
        sql += " AND lower(f.target_agent) = lower(?) "
        params.append(target_agent)
    if subject:
        sql += " AND (lower(f.subject) = lower(?) OR f.subject = '' OR f.subject IS NULL) "
        params.append(subject)
    if subtopic_filter:
        sql += " AND (lower(f.fact_summary) LIKE ? OR lower(f.verbatim_quote) LIKE ?) "
        params.extend([f"%{subtopic_filter.lower()}%", f"%{subtopic_filter.lower()}%"])

    sql += " ORDER BY f.fact_id ASC "
    cur.execute(sql, params)

    citations_map = get_cited_quotes_map(conn, chat_id)

    results = []
    for r in cur.fetchall():
        emb = None
        if r[10] is not None:
            try:
                emb = deserialize_vector(r[10])
            except Exception:
                emb = None
        anchor_id = r[3]
        locs = citations_map.get(anchor_id, [])
        is_cited = len(locs) > 0
        guidance = format_citation_guidance(is_cited, locs)
        results.append({
            "fact_id": r[0],
            "chat_id": r[1],
            "thread_id": r[2],
            "anchor_msg_id": anchor_id,
            "category": r[4],
            "sphere_id": r[5],
            "target_agent": r[6],
            "fact_summary": r[7],
            "verbatim_quote": r[8],
            "subject": r[9],
            "vector": emb,
            "is_cited": is_cited,
            "cited_in": [loc["chapter"] for loc in locs],
            "citation_guidance": guidance,
        })
    return results


def extract_keywords_from_cluster(facts: List[Dict[str, Any]], max_keywords: int = 4) -> List[str]:
    """Extract frequent informative words from fact summaries as cluster labels."""
    stop_words = {
        "i", "w", "z", "na", "do", "o", "to", "że", "się", "jak", "jest", "nie",
        "dla", "oraz", "ale", "po", "za", "ze", "od", "the", "a", "an", "and", "or",
        "of", "to", "in", "is", "that", "it", "with", "as", "for", "on", "podmiot",
        "jego", "jej", "ma", "bada", "przez", "co", "gdy", "przy", "tym", "także"
    }
    word_counts: Dict[str, int] = {}
    for f in facts:
        text = f"{f.get('fact_summary', '')} {f.get('category', '')}"
        words = [w.strip(".,;:()\"'[]!?").lower() for w in text.split()]
        for w in words:
            if len(w) > 3 and w not in stop_words:
                word_counts[w] = word_counts.get(w, 0) + 1

    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    return [w for w, _ in sorted_words[:max_keywords]]


def cluster_facts_hierarchical(
    facts: List[Dict[str, Any]],
    k: int
) -> List[List[Dict[str, Any]]]:
    """Pure Python agglomerative clustering on vectors (or index-fallback)."""
    n = len(facts)
    if k >= n:
        return [[f] for f in facts]

    has_all_vectors = all(f.get("vector") is not None for f in facts)

    if not has_all_vectors:
        # Fallback to chunking
        chunk_size = (n + k - 1) // k
        return [facts[i:i + chunk_size] for i in range(0, n, chunk_size)]

    # Compute pairwise similarity matrix
    sim_matrix: List[List[float]] = [[0.0] * n for _ in range(n)]
    for i in range(n):
        v1 = facts[i]["vector"]
        sim_matrix[i][i] = 1.0
        for j in range(i + 1, n):
            v2 = facts[j]["vector"]
            sim = dot_product(v1, v2) if v1 and v2 else 0.0
            sim_matrix[i][j] = sim
            sim_matrix[j][i] = sim

    # Agglomerative clustering (merge closest clusters until k clusters remain)
    clusters: List[List[int]] = [[i] for i in range(n)]

    while len(clusters) > k:
        best_sim = -9999.0
        best_pair = (0, 1)

        # Average linkage
        for c1_idx in range(len(clusters)):
            for c2_idx in range(c1_idx + 1, len(clusters)):
                c1 = clusters[c1_idx]
                c2 = clusters[c2_idx]
                total_sim = sum(sim_matrix[i][j] for i in c1 for j in c2)
                avg_sim = total_sim / (len(c1) * len(c2))
                if avg_sim > best_sim:
                    best_sim = avg_sim
                    best_pair = (c1_idx, c2_idx)

        # Merge best_pair
        i, j = best_pair
        clusters[i].extend(clusters[j])
        clusters.pop(j)

    return [[facts[idx] for idx in cluster] for cluster in clusters]


def find_medoid_fact(facts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Find the most representative fact in a cluster (highest average similarity)."""
    if len(facts) == 1:
        return facts[0]

    has_all_vectors = all(f.get("vector") is not None for f in facts)
    if not has_all_vectors:
        return facts[0]

    best_score = -9999.0
    medoid = facts[0]

    for f1 in facts:
        v1 = f1.get("vector")
        if not v1:
            continue
        total_sim = sum(dot_product(v1, f2["vector"]) for f2 in facts if f2.get("vector"))
        avg_sim = total_sim / len(facts)
        if avg_sim > best_score:
            best_score = avg_sim
            medoid = f1

    return medoid


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cluster discovered facts semantically to enforce the 20-fact threshold."
    )
    parser.add_argument("-C", "--chat-id", required=True, help="Chat ID to query facts from")
    parser.add_argument("--db-path", default=None, help="Path to SQLite database (default: auto from config)")
    parser.add_argument("--category", default=None, help="Filter by fact category")
    parser.add_argument("--sphere", default=None, help="Filter by life sphere (A-F)")
    parser.add_argument("--target-agent", default=None, help="Filter by target agent")
    parser.add_argument("--subtopic", default=None, help="Keyword filter for subtopic")
    parser.add_argument("--subject", default=None, help="Filter by subject alias")
    parser.add_argument("--threshold", type=int, default=20, help="Fact count threshold triggering clustering (default: 20)")
    parser.add_argument("--max-cluster-size", type=int, default=12, help="Target max facts per cluster (default: 12)")
    parser.add_argument("--k", type=int, default=None, help="Explicit number of clusters (overrides max-cluster-size)")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()
    db_path = resolve_db_path(args.db_path)

    if not os.path.exists(db_path):
        err = {"error": f"Database not found at '{db_path}'"}
        if args.json:
            print(json.dumps(err, indent=2))
        else:
            print(f"[!] {err['error']}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    facts = fetch_facts_and_vectors(
        conn,
        args.chat_id,
        category=args.category,
        sphere_id=args.sphere,
        target_agent=args.target_agent,
        subtopic_filter=args.subtopic,
        subject=args.subject
    )
    conn.close()

    total_facts = len(facts)

    # Check threshold
    if total_facts <= args.threshold:
        facts_summary = [
            {
                "fact_id": f["fact_id"],
                "anchor_msg_id": f["anchor_msg_id"],
                "summary": f["fact_summary"],
                "is_cited": f.get("is_cited", False),
                "cited_in": f.get("cited_in", []),
                "citation_guidance": f.get("citation_guidance", "")
            }
            for f in facts
        ]
        result = {
            "needs_clustering": False,
            "total_facts": total_facts,
            "threshold": args.threshold,
            "message": f"Fact count ({total_facts}) is within the threshold ({args.threshold}). Synthesize directly.",
            "fact_ids": [f["fact_id"] for f in facts],
            "facts": facts_summary
        }
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"\n[✓] Total facts: {total_facts} <= threshold {args.threshold}.")
            print("    Status: NO CLUSTERING REQUIRED. The subsection drafter can synthesize directly.")
            print(f"    Fact IDs: {result['fact_ids']}")
            print("\n  Available Facts & Citation Status (Discovered Database):")
            for f in facts:
                status_icon = "⚠️ CITED" if f.get("is_cited") else "✓ UNCITED"
                print(f"    • Fact #{f['fact_id']} [#{f['anchor_msg_id']}] [{status_icon}]: {f['fact_summary']}")
                if f.get("is_cited"):
                    print(f"      ↳ {f['citation_guidance']}")
            print()
        return

    # Determine K clusters
    if args.k:
        k = max(2, min(args.k, total_facts))
    else:
        k = max(2, (total_facts + args.max_cluster_size - 1) // args.max_cluster_size)

    fact_clusters = cluster_facts_hierarchical(facts, k)

    cluster_outputs = []
    for idx, c_facts in enumerate(fact_clusters, 1):
        medoid = find_medoid_fact(c_facts)
        keywords = extract_keywords_from_cluster(c_facts)
        uncited_in_cluster = sum(1 for f in c_facts if not f.get("is_cited"))
        c_info = {
            "cluster_id": idx,
            "fact_count": len(c_facts),
            "uncited_count": uncited_in_cluster,
            "representative_summary": medoid.get("fact_summary", ""),
            "representative_anchor": f"[#{medoid.get('anchor_msg_id')} | {medoid.get('category')}]",
            "keywords": keywords,
            "fact_ids": [f["fact_id"] for f in c_facts],
            "sample_quotes": [f["verbatim_quote"][:80] + "..." for f in c_facts[:2]]
        }
        cluster_outputs.append(c_info)

    result = {
        "needs_clustering": True,
        "total_facts": total_facts,
        "threshold": args.threshold,
        "cluster_count": len(cluster_outputs),
        "clusters": cluster_outputs
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"\n[!] Total facts: {total_facts} > threshold {args.threshold}.")
        print(f"    Status: CLUSTERING ENFORCED. Partitioned into {len(cluster_outputs)} semantic clusters.\n")
        for c in cluster_outputs:
            print(f"  ● Cluster {c['cluster_id']} ({c['fact_count']} facts, {c['uncited_count']} uncited):")
            print(f"    - Theme/Representative: \"{c['representative_summary']}\"")
            print(f"    - Keywords: {', '.join(c['keywords'])}")
            print(f"    - Fact IDs: {c['fact_ids']}")
            print()


if __name__ == "__main__":
    main()
