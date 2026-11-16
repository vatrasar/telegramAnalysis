"""Deterministic graph and heuristic pre-clustering for candidate entities with conflation risk auditing."""

from collections import defaultdict
from typing import Dict, Any, List, Set, Tuple, Optional

CATEGORY_KEYWORDS = {
    "romantic_ex": [
        "ex", "boyfriend", "bf", "husband", "suitor", "crush", "tinder", "date",
        "lover", "partner", "partnerka", "były", "była", "chłopak", "mąż", "narzeczony"
    ],
    "family": [
        "father", "mother", "mom", "dad", "sister", "brother", "parents", "parent",
        "uncle", "aunt", "cousin", "ojciec", "matka", "mama", "tata", "siostra",
        "brat", "rodzice", "wujek", "ciocia", "kuzyn"
    ],
    "medical_health": [
        "doctor", "dr", "pediatrician", "therapist", "psychiatrist", "psychologist",
        "nurse", "surgeon", "lekarz", "psycholog", "psychiatra", "terapeuta", "doktor"
    ],
    "work_education": [
        "boss", "colleague", "coworker", "manager", "professor", "teacher", "client",
        "student", "classmate", "szef", "kolega", "współpracownik", "kierownik", "profesor"
    ],
    "social_friendship": [
        "friend", "best friend", "acquaintance", "przyjaciel", "przyjaciółka", "znajomy", "znajoma"
    ]
}


def infer_candidate_category(mention: str, roles: List[str]) -> str:
    """Infer relational category based on mention text and extracted roles."""
    text = (mention + " " + " ".join(roles)).lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in kws):
            return cat
    return "social_or_unspecified"


def compute_pairwise_similarity(c1: Dict[str, Any], c2: Dict[str, Any]) -> Tuple[float, int, List[str]]:
    """Compute thread Jaccard overlap, shared thread count, and role/token similarity."""
    t1 = {t["thread_id"] for t in c1.get("threads", []) if "thread_id" in t}
    t2 = {t["thread_id"] for t in c2.get("threads", []) if "thread_id" in t}
    shared_threads = sorted(list(t1 & t2))
    shared_count = len(shared_threads)
    union_count = len(t1 | t2)
    jaccard = (shared_count / union_count) if union_count > 0 else 0.0

    roles1 = {r.lower().strip() for r in c1.get("roles", []) if r.strip()}
    roles2 = {r.lower().strip() for r in c2.get("roles", []) if r.strip()}
    role_match = 1.0 if (roles1 & roles2) else 0.0

    tokens1 = set(c1["mention"].lower().split())
    tokens2 = set(c2["mention"].lower().split())
    lex_match = 1.0 if (tokens1 & tokens2) else 0.0

    # Composite similarity score (0.0 to 1.0)
    score = (0.65 * jaccard) + (0.25 * role_match) + (0.10 * lex_match)
    return round(score, 3), shared_count, shared_threads


def generate_candidate_clusters(
    candidates: List[Dict[str, Any]],
    chat_id: str,
    target_cluster_size: int = 3,
) -> Dict[str, Any]:
    """Generate cohesive 2-3 candidate clusters and flag potential conflation risks."""
    if not candidates:
        return {
            "chat_id": chat_id,
            "total_candidates": 0,
            "total_clusters": 0,
            "clusters": [],
            "high_conflation_risks": []
        }

    n = len(candidates)
    adjacency: Dict[int, List[Tuple[int, float, int, List[str]]]] = defaultdict(list)
    high_conflation_risks: List[Dict[str, Any]] = []

    # Compute pairwise graph edges
    for i in range(n):
        for j in range(i + 1, n):
            c1 = candidates[i]
            c2 = candidates[j]
            score, shared_count, shared_threads = compute_pairwise_similarity(c1, c2)
            
            if score >= 0.15 or shared_count >= 1:
                adjacency[i].append((j, score, shared_count, shared_threads))
                adjacency[j].append((i, score, shared_count, shared_threads))

            # Conflation alert: high co-occurrence or strong role match
            if score >= 0.40 or shared_count >= 3:
                m1 = c1["mention"]
                m2 = c2["mention"]
                risk_level = "CRITICAL" if (score >= 0.60 or shared_count >= 5) else "HIGH"
                high_conflation_risks.append({
                    "pair": [m1, m2],
                    "risk_level": risk_level,
                    "similarity_score": score,
                    "shared_threads_count": shared_count,
                    "shared_threads_sample": shared_threads[:3],
                    "conflation_type": "alias_candidate_or_role_collision",
                    "auditor_note": f"Verify whether '{m1}' and '{m2}' are a single individual with aliases (K=1) or distinct concurrent individuals (K=2)."
                })

    # Sort conflation risks by severity
    high_conflation_risks.sort(key=lambda x: (x["similarity_score"], x["shared_threads_count"]), reverse=True)

    visited: Set[int] = set()
    raw_components: List[List[int]] = []

    # Find connected components with greedy seed expansion
    sorted_indices = sorted(range(n), key=lambda idx: candidates[idx]["count"], reverse=True)

    for root in sorted_indices:
        if root in visited:
            continue
        component = [root]
        visited.add(root)

        # Expand neighbours sorted by edge weight
        neighbours = sorted(adjacency[root], key=lambda x: x[1], reverse=True)
        for neigh, score, _, _ in neighbours:
            if neigh not in visited and len(component) < target_cluster_size + 1:
                component.append(neigh)
                visited.add(neigh)

        raw_components.append(component)

    # Handle isolated figures by grouping them semantically by inferred category
    unconnected_indices = [idx for idx in range(n) if idx not in visited]
    by_category: Dict[str, List[int]] = defaultdict(list)
    for idx in unconnected_indices:
        c = candidates[idx]
        cat = infer_candidate_category(c["mention"], c.get("roles", []))
        by_category[cat].append(idx)

    for cat, idxs in by_category.items():
        for i in range(0, len(idxs), target_cluster_size):
            raw_components.append(idxs[i:i + target_cluster_size])

    # Build final structured cluster objects
    clusters: List[Dict[str, Any]] = []
    cluster_id = 1

    for comp in raw_components:
        comp_candidates = [candidates[idx] for idx in comp]
        names = [c["mention"] for c in comp_candidates]
        all_roles = [r for c in comp_candidates for r in c.get("roles", [])]
        cat = infer_candidate_category(" ".join(names), all_roles)

        # Aggregate unique shared threads across cluster
        cluster_threads: Set[str] = set()
        for c in comp_candidates:
            for t in c.get("threads", []):
                if "thread_id" in t:
                    cluster_threads.add(t["thread_id"])

        max_overlap = 0.0
        relevant_risks = []
        for risk in high_conflation_risks:
            p1, p2 = risk["pair"]
            if p1 in names and p2 in names:
                relevant_risks.append(risk)
                if risk["similarity_score"] > max_overlap:
                    max_overlap = risk["similarity_score"]

        conflation_alert = None
        if relevant_risks:
            conflation_alert = f"⚠️ CONFLATION RISK: {relevant_risks[0]['pair'][0]} vs {relevant_risks[0]['pair'][1]} (Overlap: {relevant_risks[0]['similarity_score']})"

        clusters.append({
            "cluster_id": cluster_id,
            "cluster_label": f"Cluster {cluster_id}: {', '.join(names[:3])}",
            "suggested_category": cat,
            "candidate_names": names,
            "candidate_count": len(comp_candidates),
            "candidates": comp_candidates,
            "threads_count": len(cluster_threads),
            "sample_threads": sorted(list(cluster_threads))[:4],
            "max_pairwise_overlap": max_overlap,
            "conflation_alert": conflation_alert,
            "recommended_action": f"Dispatch `entity-investigator` targeting: {', '.join(names)}"
        })
        cluster_id += 1

    return {
        "chat_id": chat_id,
        "total_candidates": n,
        "total_clusters": len(clusters),
        "target_cluster_size": target_cluster_size,
        "clusters": clusters,
        "high_conflation_risks": high_conflation_risks
    }


def print_suggested_clusters(data: Dict[str, Any], chat_name: Optional[str] = None) -> None:
    """Print ASCII table of suggested candidate clusters and conflation warnings."""
    c_label = f" [Chat: {chat_name or data.get('chat_id', '')}]"
    clusters = data.get("clusters", [])
    conflations = data.get("high_conflation_risks", [])

    print("\n" + "=" * 80)
    print(f"🧩 SUGGESTED CANDIDATE CLUSTERS (HYBRID CO-OCCURRENCE ENGINE){c_label}")
    print(f"   Total Candidates: {data.get('total_candidates', 0)} | Generated Clusters: {len(clusters)}")
    print(f"   High Conflation / Alias Collision Alerts: {len(conflations)}")
    print("=" * 80)

    if not clusters:
        print("No clusters generated. Run triage and candidate extraction first.")
        print("=" * 80)
        return

    print(f"{'ID':<4} {'Category':<18} {'Candidates in Cluster':<32} {'Threads':<9} {'Conflation Alert'}")
    print("-" * 80)
    for cl in clusters:
        cid = str(cl["cluster_id"])
        cat = cl["suggested_category"][:17]
        cands_str = ", ".join(cl["candidate_names"])[:31]
        t_cnt = str(cl["threads_count"])
        alert = "⚠️ " + cl["conflation_alert"][18:38] if cl.get("conflation_alert") else "-"
        print(f"{cid:<4} {cat:<18} {cands_str:<32} {t_cnt:<9} {alert}")

    if conflations:
        print("-" * 80)
        print("🔍 TOP CONFLATION / ALIAS COLLISION RISKS (AUDIT BEFORE MERGING):")
        for risk in conflations[:5]:
            p1, p2 = risk["pair"]
            score = risk["similarity_score"]
            sh_cnt = risk["shared_threads_count"]
            print(f"   • [{risk['risk_level']}] '{p1}' <-> '{m2_safe(p2)}' (Overlap: {score}, Shared Threads: {sh_cnt})")
            print(f"     -> {risk['auditor_note']}")

    print("-" * 80)
    print("💡 SUPERVISOR PROTOCOL:")
    print("   1. Verify top conflation risks: ensure distinct people are NOT merged.")
    print("   2. Dispatch parallel `entity-investigator` subagents for each suggested cluster:")
    print("      `Role: Entity Investigator - <Cluster_Label>`")
    print("=" * 80 + "\n")


def m2_safe(s: str) -> str:
    """Helper to safely format mention."""
    return s[:25]
