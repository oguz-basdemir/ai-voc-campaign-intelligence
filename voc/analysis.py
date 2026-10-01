"""Offline, deterministic analysis. Every frequency counts distinct feedback records."""

import re
from collections import Counter

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

from voc.taxonomy import (
    HIGH_SEVERITY,
    MEDIUM_SEVERITY,
    NEGATIONS,
    NEGATIVE,
    OBJECTION_PATTERNS,
    POSITIVE,
    THEMES,
)

TOKEN = re.compile(r"[a-z]+(?:'[a-z]+)?")


def tokens(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def sentiment(text: str) -> tuple[str, int]:
    """Negation-aware lexicon baseline; mixed or unrecognized signals resolve to neutral."""
    words = tokens(text)
    score = 0
    boundary = {"but", "however", "although"}
    for i, word in enumerate(words):
        polarity = int(word in POSITIVE) - int(word in NEGATIVE)
        preceding = words[max(0, i - 3) : i]
        for j, prior in enumerate(preceding):
            if prior in boundary:
                preceding = preceding[j + 1 :]
        if any(w in NEGATIONS for w in preceding):
            polarity *= -1
        score += polarity
    return ("positive" if score > 0 else "negative" if score < 0 else "neutral"), score


def match_themes(text: str) -> list[str]:
    lower = text.lower()
    return [
        theme
        for theme, spec in THEMES.items()
        if any(re.search(r"\b" + re.escape(term) + r"\b", lower) for term in spec["terms"])
    ]


def severity(text: str) -> int:
    words = set(tokens(text))
    return 3 if words & HIGH_SEVERITY else 2 if words & MEDIUM_SEVERITY else 1


def example(row: dict) -> dict:
    return {key: row[key] for key in ["record_id", "text", "source", "customer_type", "product", "market"]}


def evidence(rows: list[dict], limit: int = 3, theme: str | None = None) -> list[dict]:
    selected, seen = [], set()

    def relevance(row):
        if not theme:
            return 0
        return sum(
            bool(re.search(r"\b" + re.escape(term) + r"\b", row["text"].lower()))
            for term in THEMES[theme]["terms"]
        )

    for row in sorted(rows, key=lambda x: (-relevance(x), -x["severity"], x["record_id"])):
        # Different excerpts are more useful than repeated templates.
        phrase = row["text"].split(".")[0]
        if phrase not in seen:
            selected.append(example(row))
            seen.add(phrase)
        if len(selected) == limit:
            break
    return selected


def clusters(frame: pd.DataFrame, requested: int) -> list[dict]:
    if len(frame) < 2:
        return []
    vectorizer = TfidfVectorizer(
        stop_words="english", ngram_range=(1, 2), max_features=3000, min_df=1, max_df=1.0, sublinear_tf=True
    )
    try:
        matrix = vectorizer.fit_transform(frame.text)
    except ValueError:
        return []
    # Bound K to unique vocabulary vectors to avoid empty/duplicate clusters.
    unique = len({tuple(zip(matrix[i].indices, matrix[i].data)) for i in range(matrix.shape[0])})
    count = min(requested, len(frame), unique)
    if count < 2:
        return []
    model = KMeans(n_clusters=count, random_state=42, n_init=10)
    labels = model.fit_predict(matrix)
    terms = vectorizer.get_feature_names_out()
    result = []
    for label in sorted(set(labels)):
        idx = [i for i, value in enumerate(labels) if value == label]
        center = model.cluster_centers_[label]
        top = [str(terms[i]) for i in center.argsort()[::-1][:6]]
        result.append(
            {
                "cluster": int(label) + 1,
                "terms": top,
                "frequency": len(idx),
                "evidence_ids": frame.iloc[idx].record_id.tolist()[:10],
                "example": example(frame.iloc[idx[0]].to_dict()),
            }
        )
    return sorted(result, key=lambda x: -x["frequency"])


def language_library(rows: list[dict]) -> list[dict]:
    """Exact contiguous n-grams, counted once per record; quotes remain verbatim."""
    groups = {"problems": [], "benefits": [], "desired outcomes": []}
    for row in rows:
        text = row["text"]
        # Goal clauses take precedence; otherwise use the record's baseline sentiment.
        category = (
            "desired outcomes"
            if re.search(r"\b(?:we want|we need|so we can|i want|i need)\b", text.lower())
            else (
                "benefits"
                if row["sentiment"] == "positive"
                else "problems"
                if row["sentiment"] == "negative"
                else None
            )
        )
        if category:
            groups[category].append(row)
    entries = []
    for category, subset in groups.items():
        occurrences: dict[str, list[dict]] = {}
        for row in subset:
            spans = list(TOKEN.finditer(row["text"].lower()))
            seen = set()
            for size in (3, 4, 5):
                for i in range(len(spans) - size + 1):
                    chunk = spans[i : i + size]
                    words = [x.group() for x in chunk]
                    # Prevent n-grams crossing punctuation/sentence boundaries.
                    phrase = row["text"][chunk[0].start() : chunk[-1].end()].lower()
                    if re.search(r"[.!?;,:]", phrase):
                        continue
                    if words[0] in ENGLISH_STOP_WORDS or words[-1] in ENGLISH_STOP_WORDS:
                        continue
                    if not any(
                        w in POSITIVE | NEGATIVE
                        or w
                        in {
                            "work",
                            "customers",
                            "reporting",
                            "data",
                            "workflow",
                            "pricing",
                            "onboarding",
                            "implementation",
                            "crm",
                            "support",
                            "budget",
                            "information",
                            "clicks",
                            "team",
                            "training",
                        }
                        for w in words
                    ):
                        continue
                    seen.add(phrase)
            for phrase in seen:
                occurrences.setdefault(phrase, []).append(row)
        candidates = sorted(occurrences.items(), key=lambda item: (-len(item[1]), -len(item[0]), item[0]))
        picked = []
        for phrase, matches in candidates:
            if len(matches) < 2 or any(phrase in p or p in phrase for p in picked):
                continue
            picked.append(phrase)
            entries.append(
                {
                    "category": category,
                    "phrase": phrase,
                    "frequency": len(matches),
                    "segments": dict(Counter(r["customer_type"] for r in matches)),
                    "evidence": evidence(matches, 1),
                }
            )
            if len(picked) >= 12:
                break
    return entries


def opportunity_score(
    frequency: int, total: int, average_severity: float, relevance: float, segment_size: int, customers: int
) -> tuple[float, dict]:
    components = {
        "frequency": round(100 * frequency / max(total, 1), 2),
        "severity": round(100 * average_severity / 3, 2),
        "commercial_relevance": round(100 * relevance, 2),
        "segment_size": round(100 * segment_size / max(customers, 1), 2),
    }
    score = sum(
        components[k] * w
        for k, w in [
            ("frequency", 0.35),
            ("severity", 0.30),
            ("commercial_relevance", 0.20),
            ("segment_size", 0.15),
        ]
    )
    return round(score, 1), components


def analyze(frame: pd.DataFrame, requested_clusters: int = 6) -> dict:
    rows = frame.to_dict("records")
    for row in rows:
        row["themes"] = match_themes(row["text"])
        row["sentiment"], row["sentiment_score"] = sentiment(row["text"])
        row["severity"] = severity(row["text"])
        row["is_objection"] = any(re.search(p, row["text"].lower()) for p in OBJECTION_PATTERNS)
        row["is_pain"] = row["sentiment"] == "negative"
    total = len(rows)
    customers = frame.customer_id.nunique() if total else 0
    themes, pain_points, objections, opportunities = [], [], [], []
    for name, spec in THEMES.items():
        mentions = [r for r in rows if name in r["themes"]]
        if not mentions:
            continue
        pains = [r for r in mentions if r["is_pain"]]
        blockers = [r for r in mentions if r["is_objection"]]
        themes.append(
            {
                "theme": name,
                "frequency": len(mentions),
                "share_pct": round(100 * len(mentions) / total, 1),
                "sentiment": dict(Counter(r["sentiment"] for r in mentions)),
                "segments": dict(Counter(r["customer_type"] for r in mentions)),
                "evidence": evidence(mentions, theme=name),
                "evidence_ids": [r["record_id"] for r in mentions],
            }
        )
        if pains:
            pain_points.append(
                {
                    "theme": name,
                    "problem": spec["problem"],
                    "frequency": len(pains),
                    "share_pct": round(100 * len(pains) / total, 1),
                    "severity": round(sum(r["severity"] for r in pains) / len(pains), 2),
                    "segments": dict(Counter(r["customer_type"] for r in pains)),
                    "evidence": evidence(pains, theme=name),
                    "evidence_ids": [r["record_id"] for r in pains],
                }
            )
        if blockers:
            objections.append(
                {
                    "theme": name,
                    "frequency": len(blockers),
                    "segments": dict(Counter(r["customer_type"] for r in blockers)),
                    "recommended_response": spec["response"],
                    "evidence": evidence(blockers, theme=name),
                    "evidence_ids": [r["record_id"] for r in blockers],
                }
            )
        # No opportunity is generated without a negative or objection signal.
        signals = [r for r in mentions if r["is_pain"] or r["is_objection"]]
        if signals:
            affected = Counter(r["customer_type"] for r in signals)
            segment = affected.most_common(1)[0][0]
            segment_size = frame.loc[frame.customer_type == segment, "customer_id"].nunique()
            average = sum(r["severity"] for r in signals) / len(signals)
            score, parts = opportunity_score(
                len(signals), total, average, spec["relevance"], segment_size, customers
            )
            opportunities.append(
                {
                    "theme": name,
                    "observed_pain": spec["problem"],
                    "concept": spec["concept"],
                    "ad_angle": spec["angle"],
                    "content_topic": spec["content"],
                    "landing_page": spec["landing"],
                    "email_idea": spec["email"],
                    "case_study_opportunity": spec["case_study"],
                    "message": spec["response"],
                    "segment": segment,
                    "frequency": len(signals),
                    "score": score,
                    "score_components": parts,
                    "commercial_relevance_basis": "Curated demo assumption; not measured revenue",
                    "evidence": evidence(signals, theme=name),
                    "evidence_ids": [r["record_id"] for r in signals],
                    "validation": "Validate claims with product owners, interview this segment, then test the angle.",
                    "suggested_kpi": "Qualified demo conversion rate; compare against a control",
                }
            )
    segments = []
    for segment, subset in sorted(frame.groupby("customer_type")) if total else []:
        local = [r for r in rows if r["customer_type"] == segment]
        counts = Counter(t for r in local for t in r["themes"])
        top = counts.most_common(3)
        dominant = top[0][0] if top else None
        spec = THEMES[dominant] if dominant else None
        segments.append(
            {
                "segment": segment,
                "profile": spec["persona"] if spec else "Exploratory customer profile",
                "status": "Generated hypothesis based on available synthetic data; validate with interviews",
                "records": len(local),
                "customers": int(subset.customer_id.nunique()),
                "needs": [THEMES[t]["need"] for t, _ in top],
                "themes": dict(top),
                "objections": [o["theme"] for o in objections if segment in o["segments"]],
                "messaging": [THEMES[t]["response"] for t, _ in top],
                "motivations": [THEMES[t]["need"] for t, _ in top],
                "desired_outcomes": [
                    example(r) for r in local if re.search(r"\b(?:want|need).+\bso\b", r["text"].lower())
                ][:3],
                "evidence": evidence(local),
                "confidence": "Limited" if len(local) < 30 else "Directional",
            }
        )
    breakdown = []
    for dimension in ("source", "product", "customer_type", "market"):
        for group in sorted({r[dimension] for r in rows}):
            group_rows = [r for r in rows if r[dimension] == group]
            count = Counter(r["sentiment"] for r in group_rows)
            breakdown.append(
                {
                    "dimension": dimension,
                    "group": group,
                    "records": len(group_rows),
                    **{label: count[label] for label in ["positive", "neutral", "negative"]},
                }
            )
    trend = []
    for month in sorted({r["date"][:7] for r in rows}):
        count = Counter(r["sentiment"] for r in rows if r["date"].startswith(month))
        trend.append(
            {"month": month, **{label: count[label] for label in ["positive", "neutral", "negative"]}}
        )
    return {
        "summary": {
            "records": total,
            "unique_customers": int(customers),
            "theme_count": len(themes),
            "pain_records": sum(r["is_pain"] for r in rows),
            "objection_records": sum(r["is_objection"] for r in rows),
            "unclassified_records": sum(not r["themes"] for r in rows),
            "sentiment": {
                label: sum(r["sentiment"] == label for r in rows)
                for label in ["positive", "neutral", "negative"]
            },
            "date_from": str(frame.date.min()) if total else None,
            "date_to": str(frame.date.max()) if total else None,
        },
        "themes": sorted(themes, key=lambda x: -x["frequency"]),
        "clusters": clusters(frame, requested_clusters) if total else [],
        "pain_points": sorted(pain_points, key=lambda x: (-x["frequency"], -x["severity"])),
        "objections": sorted(objections, key=lambda x: -x["frequency"]),
        "language_library": language_library(rows),
        "segments": segments,
        "opportunities": sorted(opportunities, key=lambda x: -x["score"]),
        "sentiment_breakdown": breakdown,
        "sentiment_trend": trend,
        "records": rows,
        "methodology": {
            "version": "1.0",
            "synthetic_only": True,
            "frequency_unit": "Distinct feedback records; themes can overlap",
            "severity_scale": "1 mild / 2 friction / 3 critical (keyword heuristic)",
            "persona_status": "Hypotheses, not validated personas",
            "score_weights": {
                "frequency": 0.35,
                "severity": 0.30,
                "commercial_relevance": 0.20,
                "segment_size": 0.15,
            },
            "limitations": [
                "English lexicon baseline, not a trained sentiment model",
                "Curated problem and campaign templates, not verified product claims",
                "Synthetic data and sampling bias prevent market-wide conclusions",
                "Customers may appear in multiple segments; sizes are distinct IDs per segment",
            ],
        },
    }
