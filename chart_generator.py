from collections import Counter
import json
import re
from itertools import combinations


def normalize_author(name):
    name = name.strip().strip('"').replace(".", "").replace("-", " ")
    name = re.sub(r"[\d()\[\]{}*]", "", name)
    name = " ".join(name.split())
    if "," in name:
        parts = [p.strip() for p in name.split(",", 1)]
        name = f"{parts[1]} {parts[0]}".strip()
    return name.title()


def normalize_authors_list(authors_raw):
    if isinstance(authors_raw, list):
        names = authors_raw
    elif isinstance(authors_raw, str):
        try:
            names = json.loads(authors_raw.replace("'", '"'))
        except:
            names = [n.strip() for n in authors_raw.split(",")]
    else:
        return []
    return [normalize_author(n) for n in names if str(n).strip()]


def author_cooccurrence(metadata_list):
    edges, author_count = Counter(), Counter()

    for meta in metadata_list:
        authors = normalize_authors_list(meta.get("authors", "[]"))
        for a in authors:
            author_count[a] += 1
        for a1, a2 in combinations(sorted(set(authors)), 2):
            edges[(a1, a2)] += 1

    return {
        "edges": [
            {"source": s, "target": t, "weight": w}
            for (s, t), w in edges.most_common(30)
        ],
        "counts": dict(author_count.most_common(20))
    }


def count_by_field(metadata_list, field):
    counter = Counter()
    for meta in metadata_list:
        value = meta.get(field, "Unknown")
        if isinstance(value, str) and value.strip():
            counter[value] += 1
        else:
            counter["Unknown"] += 1
    return dict(counter.most_common(20))


def year_distribution(metadata_list):
    counter = Counter()
    for meta in metadata_list:
        try:
            year = int(meta.get("year", 0))
            if year > 0:
                counter[year] += 1
        except:
            pass
    return dict(sorted(counter.items()))


def _parse_list_field(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value.replace("'", '"'))
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except:
            return [x.strip() for x in value.split(",") if x.strip()]
    return []


def build_keyword_cooccurrence(metadata_list):
    pair_counter = Counter()

    for meta in metadata_list:
        keywords = _parse_list_field(meta.get("keywords", "[]"))
        keywords = sorted(set(keywords))
        for k1, k2 in combinations(keywords, 2):
            pair_counter[(k1, k2)] += 1

    return [
        {"keyword_1": k1, "keyword_2": k2, "count": cnt}
        for (k1, k2), cnt in pair_counter.most_common(30)
    ]


def generate_mermaid_ontology(metadata_list, center_topic="Research"):
    fields = count_by_field(metadata_list, "research_field")
    methods = count_by_field(metadata_list, "methodology")

    keyword_counter = Counter()
    for meta in metadata_list:
        for kw in _parse_list_field(meta.get("keywords", "[]")):
            keyword_counter[kw] += 1

    top_keywords = dict(keyword_counter.most_common(10))

    lines = ["graph TD"]
    lines.append(f'    CENTER["{center_topic}"]')

    for i, field in enumerate(fields.keys()):
        node = f"F{i}"
        lines.append(f'    {node}["Field: {field}"]')
        lines.append(f"    CENTER --> {node}")

    for i, method in enumerate(methods.keys()):
        node = f"M{i}"
        lines.append(f'    {node}["Method: {method}"]')
        lines.append(f"    CENTER --> {node}")

    for i, kw in enumerate(top_keywords.keys()):
        node = f"K{i}"
        lines.append(f'    {node}["Keyword: {kw}"]')
        lines.append(f"    CENTER --> {node}")

    return "\n".join(lines)


def generate_mermaid_author_network(metadata_list):
    data = author_cooccurrence(metadata_list)
    author_to_node = {}

    lines = ["graph LR"]

    for i, (author, cnt) in enumerate(data["counts"].items()):
        node_id = f"A{i}"
        author_to_node[author] = node_id
        lines.append(f'    {node_id}["{author}<br/>{cnt} papers"]')

    for edge in data["edges"]:
        s = edge["source"]
        t = edge["target"]
        w = edge["weight"]
        if s in author_to_node and t in author_to_node:
            lines.append(f"    {author_to_node[s]} ---|{w}| {author_to_node[t]}")

    return "\n".join(lines)