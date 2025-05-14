"""
Deduplicate and cluster similar skill titles and underpinning knowledge statements in role_skill_mapping.json.

Usage:
    python deduplicate_skills.py

Requirements:
    pip install fuzzywuzzy python-Levenshtein

Outputs:
    role_skill_mapping_deduped.json (in the same directory as the input file)
"""
import json
import os
from fuzzywuzzy import fuzz
from collections import defaultdict

# Configurable similarity threshold (0-100)
TITLE_SIMILARITY_THRESHOLD = 90
KNOWLEDGE_SIMILARITY_THRESHOLD = 75

INPUT_PATH = os.path.join(os.path.dirname(__file__), '../data/roles/sample_role_skill_mapping.json')
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '../data/roles/sample_role_skill_mapping_deduped.json')

def cluster_similar(items, threshold):
    clusters = []
    for item in items:
        found = False
        for cluster in clusters:
            if fuzz.token_set_ratio(item, cluster[0]) >= threshold:
                cluster.append(item)
                found = True
                break
        if not found:
            clusters.append([item])
    # Use the first item in each cluster as the canonical version
    canonical_map = {}
    for cluster in clusters:
        canonical = cluster[0]
        for item in cluster:
            canonical_map[item] = canonical
    return canonical_map

def main():
    print("[INFO] Starting deduplication process...")
    with open(INPUT_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"[INFO] Loaded input file: {INPUT_PATH}")

    # Gather all unique skill titles and knowledge statements
    all_titles = set()
    all_knowledge = set()
    for role in data:
        for skill in role.get('functional_skills', []):
            title = skill.get('title')
            if title:
                all_titles.add(title)
            for uk in skill.get('underpinning_knowledge', []):
                all_knowledge.add(uk)
    print(f"[INFO] Found {len(all_titles)} unique skill titles and {len(all_knowledge)} unique underpinning knowledge statements.")

    # Cluster similar titles and knowledge
    print("[INFO] Clustering similar skill titles...")
    title_map = cluster_similar(list(all_titles), TITLE_SIMILARITY_THRESHOLD)
    print(f"[INFO] Reduced to {len(set(title_map.values()))} canonical skill titles.")
    print("[INFO] Clustering similar underpinning knowledge statements...")
    knowledge_map = cluster_similar(list(all_knowledge), KNOWLEDGE_SIMILARITY_THRESHOLD)
    print(f"[INFO] Reduced to {len(set(knowledge_map.values()))} canonical underpinning knowledge statements.")

    # Replace with canonical versions
    print("[INFO] Replacing with canonical versions...")
    for role in data:
        for skill in role.get('functional_skills', []):
            if 'title' in skill:
                skill['title'] = title_map.get(skill['title'], skill['title'])
            if 'underpinning_knowledge' in skill:
                skill['underpinning_knowledge'] = [knowledge_map.get(uk, uk) for uk in skill['underpinning_knowledge']]

    # Save deduplicated file
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[INFO] Deduplicated file written to {OUTPUT_PATH}")

if __name__ == '__main__':
    main()
