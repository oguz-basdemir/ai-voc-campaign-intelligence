"""Streamlit strategy workspace backed by the FastAPI service."""

import html
import os
from datetime import date

import altair as alt
import httpx
import pandas as pd
import streamlit as st

from voc.config import ROOT
from voc.report import html_report, markdown_report, opportunities_csv

st.set_page_config(page_title="Signal Studio · Voice of Customer", page_icon="◉", layout="wide")
API = os.getenv("VOC_API_URL", "http://127.0.0.1:8000").rstrip("/")
COLORS = {"positive": "#168675", "neutral": "#B6C3CF", "negative": "#D77557"}
PAGES = [
    "Overview",
    "Themes",
    "Pain Points",
    "Objections",
    "Sentiment",
    "Customer Language",
    "Segments",
    "Campaign Opportunities",
]

st.markdown(
    """<style>
[data-testid="stAppViewContainer"] .main {background:#f7f8fa}
.block-container {padding-top:3.6rem;max-width:1480px}
[data-testid="stSidebar"] {border-right:1px solid #e4e9ec}
[data-testid="stMetric"] {background:white;border:1px solid #e4e9ec;border-radius:12px;padding:18px}
[data-testid="stMetricValue"] {font-size:2.05rem;font-weight:650}
h1 {letter-spacing:-1.1px;font-weight:700!important} h2 {letter-spacing:-.5px}
.eyebrow {font-size:11px;letter-spacing:2px;color:#136f63;font-weight:700;margin-bottom:8px}
.brand {font-size:25px;font-weight:750;letter-spacing:-1px;color:#173c38}
.tag {display:inline-block;background:#e4f2ed;color:#126e61;border-radius:5px;padding:4px 9px;
font-size:11px;font-weight:700;letter-spacing:.5px;margin-right:7px}
.subtle {color:#687b87;font-size:14px;line-height:1.6}
.brief {background:#fff;border:1px solid #dce6e4;border-left:4px solid #136f63;border-radius:10px;
padding:24px;margin:8px 0 18px}
.brief h3 {margin:8px 0 12px;color:#172b36;font-size:24px}
.quote {background:#f0f5f4;border-radius:8px;padding:15px 18px;margin:10px 0;color:#263f45;
font-size:14px;line-height:1.6}
.quote small {color:#647c83;display:block;margin-top:8px;font-size:11px}
</style>""",
    unsafe_allow_html=True,
)


def request(method, path, **kwargs):
    try:
        response = httpx.request(method, API + path, timeout=120, **kwargs)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail", "Request failed")
        except ValueError:
            detail = "Request failed"
        st.error(f"The service could not complete the request: {detail}")
    except httpx.RequestError:
        st.error(
            "The analysis service is unavailable. Start FastAPI on port 8000 using the README instructions."
        )
    return None


def quotes(items):
    for item in items:
        st.markdown(
            f'<div class="quote">“{html.escape(item["text"])}”<small>SYNTHETIC QUOTE · '
            f"{html.escape(item['record_id'])} · {html.escape(item['source'])} · "
            f"{html.escape(item['customer_type'])}</small></div>",
            unsafe_allow_html=True,
        )


def bar_chart(items, label, value="frequency", color="#136f63"):
    if not items:
        st.info("No matching signals in this scope.")
        return
    frame = pd.DataFrame(items)
    chart = (
        alt.Chart(frame)
        .mark_bar(cornerRadiusEnd=4, color=color)
        .encode(
            y=alt.Y(f"{label}:N", sort="-x", title=None, axis=alt.Axis(labelLimit=280)),
            x=alt.X(
                f"{value}:Q", title="Feedback records" if value == "frequency" else "Priority score / 100"
            ),
            tooltip=[alt.Tooltip(label), alt.Tooltip(value)],
        )
        .properties(height=max(160, len(frame) * 37))
    )
    st.altair_chart(chart, width="stretch")


def sentiment_chart(frame, group):
    melted = frame.melt(id_vars=[group], value_vars=list(COLORS), var_name="Sentiment", value_name="Records")
    chart = (
        alt.Chart(melted)
        .mark_bar(cornerRadiusEnd=3)
        .encode(
            y=alt.Y(f"{group}:N", title=None),
            x=alt.X("Records:Q", title="Feedback records"),
            color=alt.Color("Sentiment:N", scale=alt.Scale(domain=list(COLORS), range=list(COLORS.values()))),
            tooltip=[group, "Sentiment", "Records"],
        )
        .properties(height=max(170, len(frame) * 44))
    )
    st.altair_chart(chart, width="stretch")


def exports(result):
    with st.expander("Download the marketing report & campaign backlog"):
        st.caption(
            "Exports preserve this run's filters, evidence IDs, scoring method, and synthetic-data labels."
        )
        a, b, c = st.columns(3)
        a.download_button(
            "↓ Marketing report · Markdown",
            markdown_report(result),
            file_name="voice-of-customer-report.md",
            mime="text/markdown",
            width="stretch",
        )
        b.download_button(
            "↓ Printable report · HTML",
            html_report(result),
            file_name="voice-of-customer-report.html",
            mime="text/html",
            width="stretch",
        )
        c.download_button(
            "↓ Campaign backlog · CSV",
            opportunities_csv(result),
            file_name="campaign-opportunities.csv",
            mime="text/csv",
            width="stretch",
        )


with st.sidebar:
    st.markdown('<div class="brand">◉ Signal Studio</div>', unsafe_allow_html=True)
    st.caption("VOICE OF CUSTOMER / CAMPAIGN INTELLIGENCE")
    st.markdown('<span class="tag">SYNTHETIC DATA ONLY</span>', unsafe_allow_html=True)
    st.divider()
    page = st.radio("Workspace", PAGES, label_visibility="collapsed")
    st.divider()
    with st.expander("Data workspace", expanded=False):
        if st.button("Load synthetic demo", width="stretch"):
            metadata = request("POST", "/api/demo")
            if metadata:
                st.session_state.dataset = metadata
                st.session_state.pop("result", None)
                st.rerun()
        upload = st.file_uploader("Upload synthetic feedback", type="csv")
        synthetic = st.checkbox("I confirm all uploaded feedback is synthetic")
        if st.button("Import CSV", disabled=upload is None or not synthetic, width="stretch"):
            metadata = request(
                "POST",
                "/api/datasets",
                files={"file": (upload.name, upload.getvalue(), "text/csv")},
                data={"synthetic": "true"},
            )
            if metadata:
                st.session_state.dataset = metadata
                st.session_state.pop("result", None)
                st.rerun()
        demo_csv = ROOT / "data" / "synthetic_feedback.csv"
        if demo_csv.exists():
            st.download_button("↓ Example CSV", demo_csv.read_bytes(), file_name="synthetic_feedback.csv")
        if st.button("Browse saved datasets", width="stretch"):
            st.session_state.saved_datasets = request("GET", "/api/datasets") or []
        saved = st.session_state.get("saved_datasets", [])
        if saved:
            selected = st.selectbox(
                "Saved dataset",
                range(len(saved)),
                format_func=lambda i: f"{saved[i]['name']} ({saved[i]['rows']} rows)",
            )
            if st.button("Open dataset"):
                st.session_state.dataset = saved[selected]
                st.session_state.pop("result", None)
                st.rerun()

if "dataset" not in st.session_state:
    with st.spinner("Loading the fictional FlowPilot feedback workspace…"):
        metadata = request("POST", "/api/demo")
    if not metadata:
        st.title("AI Voice-of-Customer & Campaign Intelligence Agent")
        st.info("Start the API, then refresh this page. See the project's README for local and Docker setup.")
        st.stop()
    st.session_state.dataset = metadata

dataset = st.session_state.dataset
with st.sidebar:
    st.caption(f"ACTIVE DATASET · {dataset['rows']:,} RECORDS")
    st.text(dataset["name"])
    with st.form("scope"):
        st.markdown("**Analysis scope**")
        opts = dataset["options"]
        products = st.multiselect("Product", opts["product"])
        segments = st.multiselect("Customer segment", opts["customer_type"])
        markets = st.multiselect("Market", opts["market"])
        sources = st.multiselect("Source", opts["source"])
        period = st.date_input(
            "Date range",
            value=(date.fromisoformat(dataset["date_from"]), date.fromisoformat(dataset["date_to"])),
        )
        count = st.slider("Exploratory clusters", 2, 12, 6)
        enrich = st.checkbox(
            "Add optional LLM creative hypotheses",
            help="Sends a bounded set of synthetic quotes "
            "to the configured provider. Requires server-side credentials. Counts remain deterministic.",
        )
        run = st.form_submit_button("Analyze feedback", type="primary", width="stretch")
    st.caption("Filters apply when you select Analyze feedback. Exports use the displayed run.")

if run or "result" not in st.session_state:
    if len(period) != 2:
        st.warning("Select a start and end date before analyzing.")
        st.stop()
    filters = {
        "sources": sources,
        "products": products,
        "segments": segments,
        "markets": markets,
        "date_from": period[0].isoformat(),
        "date_to": period[1].isoformat(),
    }
    with st.spinner("Connecting feedback signals to marketing opportunities…"):
        result = request(
            "POST",
            "/api/analyses",
            json={"dataset_id": dataset["id"], "filters": filters, "enrich": enrich, "clusters": count},
        )
    if result:
        st.session_state.result = result

if "result" not in st.session_state:
    st.stop()
r = st.session_state.result
s = r["summary"]
st.markdown(
    '<div class="eyebrow">AI VOICE-OF-CUSTOMER & CAMPAIGN INTELLIGENCE AGENT</div>', unsafe_allow_html=True
)
st.title(
    {
        "Overview": "From customer signals to your next move.",
        "Themes": "What keeps coming up?",
        "Pain Points": "Find the friction that matters.",
        "Objections": "Turn hesitation into a better conversation.",
        "Sentiment": "Understand how customers feel.",
        "Customer Language": "Write in your customers’ words.",
        "Segments": "Understand the people behind the signals.",
        "Campaign Opportunities": "Build campaigns with an evidence trail.",
    }[page]
)
st.markdown(
    f'<div class="subtle">{html.escape(dataset["name"])} · '
    f"{s['records']:,} feedback records · {s['date_from'] or 'No dates'} — "
    f"{s['date_to'] or 'No dates'}</div>",
    unsafe_allow_html=True,
)
active = [
    f"{key}: {', '.join(value) if isinstance(value, list) else value}"
    for key, value in r["filters"].items()
    if value
]
st.caption("DISPLAYED SCOPE · " + " | ".join(active))
exports(r)
if not s["records"]:
    st.info("No feedback matches this scope. Broaden the filters and select Analyze feedback.")
    st.stop()

if page == "Overview":
    a, b, c, d = st.columns(4)
    a.metric("Feedback signals", f"{s['records']:,}")
    b.metric("Synthetic customers", f"{s['unique_customers']:,}")
    c.metric("Negative sentiment", f"{100 * s['sentiment']['negative'] / s['records']:.0f}%")
    d.metric("Campaign opportunities", len(r["opportunities"]))
    left, right = st.columns([1.15, 1], gap="large")
    with left:
        st.subheader("The conversation, at a glance")
        st.caption("Records mentioning each theme. One record can mention several themes.")
        bar_chart(r["themes"], "theme")
    with right:
        st.subheader("Your next strategic move")
        if r["opportunities"]:
            top = r["opportunities"][0]
            st.markdown(
                f'<div class="brief"><span class="tag">PRIORITY 01 · {top["score"]}/100</span>'
                f"<h3>{html.escape(top['concept'])}</h3><p>{html.escape(top['observed_pain'])}</p>"
                f'<p class="subtle">{top["frequency"]} supporting records · '
                f"{html.escape(top['segment'])}</p></div>",
                unsafe_allow_html=True,
            )
            st.write(top["message"])
            quotes(top["evidence"][:1])
        else:
            st.info("No pain or objection signals found. Explore positive language for customer stories.")
    st.subheader("Signals to take into your next planning meeting")
    for opp in r["opportunities"][:3]:
        st.write(f"**{opp['concept']}** · {opp['segment']} · priority {opp['score']}/100")
        st.caption(opp["content_topic"] + " → " + opp["validation"])
    with st.expander("Evidence ledger · inspect the source records"):
        st.dataframe(
            pd.DataFrame(r["records"])[
                ["record_id", "source", "customer_type", "market", "product", "text", "themes", "sentiment"]
            ],
            hide_index=True,
            width="stretch",
        )

elif page == "Themes":
    st.subheader("Recurring themes")
    bar_chart(r["themes"], "theme")
    for theme in r["themes"]:
        with st.expander(
            f"{theme['theme'].title()} · {theme['frequency']} records · {theme['share_pct']}% of scope"
        ):
            st.write("Segment mentions:", theme["segments"])
            quotes(theme["evidence"])
    st.subheader("Exploratory topic clusters")
    st.caption(
        "TF-IDF + seeded K-means. Vocabulary groups can surface signals outside the curated taxonomy; "
        "cluster labels are terms, not validated themes."
    )
    if not r["clusters"]:
        st.info("Not enough distinct text vocabulary to form exploratory clusters.")
    for cluster in r["clusters"]:
        with st.expander(
            f"Cluster {cluster['cluster']} · {cluster['frequency']} records · "
            + ", ".join(cluster["terms"][:3])
        ):
            st.write("Top terms:", ", ".join(cluster["terms"]))
            quotes([cluster["example"]])

elif page == "Pain Points":
    st.caption(
        "Negative sentiment is used as a pain signal. Problem labels are curated hypotheses; inspect quotes."
    )
    if not r["pain_points"]:
        st.info("No pain signals in this scope.")
    for pain in r["pain_points"]:
        with st.container(border=True):
            a, b = st.columns([4, 1])
            a.subheader(pain["problem"])
            b.metric("Avg. severity / 3", pain["severity"])
            st.caption(
                f"{pain['frequency']} records · {pain['share_pct']}% of scope · "
                + ", ".join(f"{k}: {v}" for k, v in pain["segments"].items())
            )
            quotes(pain["evidence"][:2])

elif page == "Objections":
    st.caption(
        "Candidate objections come from concern, evaluation-question, and hesitation patterns across all sources."
    )
    if not r["objections"]:
        st.info("No objection candidates in this scope.")
    for objection in r["objections"]:
        with st.container(border=True):
            st.subheader(f"{objection['theme'].title()} · {objection['frequency']} records")
            st.caption("Affected segments: " + ", ".join(objection["segments"]))
            quotes(objection["evidence"][:1])
            st.markdown("**Recommended conversation / message**")
            st.write(objection["recommended_response"])

elif page == "Sentiment":
    st.caption(
        "English lexicon baseline with a three-token negation window. Neutral includes mixed and unrecognized signals."
    )
    a, b, c = st.columns(3)
    for col, label in zip([a, b, c], COLORS):
        col.metric(label.title(), s["sentiment"][label])
    dimension = st.selectbox(
        "Break down by",
        ["source", "product", "customer_type", "market"],
        format_func=lambda x: x.replace("_", " ").title(),
    )
    frame = pd.DataFrame([x for x in r["sentiment_breakdown"] if x["dimension"] == dimension])
    sentiment_chart(frame, "group")
    st.subheader("Monthly sentiment")
    trend = pd.DataFrame(r["sentiment_trend"]).melt(
        id_vars="month", var_name="Sentiment", value_name="Records"
    )
    st.altair_chart(
        alt.Chart(trend)
        .mark_line(point=True)
        .encode(
            x=alt.X("month:N", title="Month"),
            y="Records:Q",
            color=alt.Color("Sentiment:N", scale=alt.Scale(domain=list(COLORS), range=list(COLORS.values()))),
            tooltip=["month", "Sentiment", "Records"],
        )
        .properties(height=260),
        width="stretch",
    )

elif page == "Customer Language":
    st.subheader("Customer Language Library")
    st.caption(
        "Exact recurring phrases of 3–5 words, counted once per record. Use as copy inspiration, then review context."
    )
    category = st.segmented_control(
        "Language intent", ["problems", "benefits", "desired outcomes"], default="problems"
    )
    entries = [x for x in r["language_library"] if x["category"] == category]
    if not entries:
        st.info("No repeated phrases for this intent in the selected scope.")
    for item in entries:
        with st.container(border=True):
            st.subheader(f"“{item['phrase']}”")
            st.caption(f"{item['frequency']} supporting records · " + ", ".join(item["segments"]))
            quotes(item["evidence"])

elif page == "Segments":
    st.info(
        "These personas are generated hypotheses based on available synthetic data. Validate motivations, "
        "needs, and positioning with real research before applying them to a market."
    )
    for segment in r["segments"]:
        with st.container(border=True):
            st.subheader(segment["profile"])
            st.caption(
                f"{segment['segment']} · {segment['records']} records · {segment['customers']} synthetic "
                f"customers · {segment['confidence']} evidence"
            )
            a, b, c = st.columns(3)
            a.markdown("**Needs & motivations**")
            for need in segment["needs"]:
                a.write("• " + need)
            b.markdown("**Objection candidates**")
            b.write(", ".join(segment["objections"]) or "None identified")
            c.markdown("**Messaging to explore**")
            for message in segment["messaging"][:2]:
                c.write(message)
            with st.expander("Desired outcomes in customers' words"):
                quotes(segment["desired_outcomes"])
                if not segment["desired_outcomes"]:
                    st.caption("No explicit goal clause found; do not assume an unstated outcome.")

elif page == "Campaign Opportunities":
    st.caption(
        "Ranked creative starting points. Commercial relevance is a curated demo assumption; "
        "scores represent prioritization, not expected revenue."
    )
    bar_chart(r["opportunities"], "concept", "score")
    for rank, opp in enumerate(r["opportunities"], 1):
        with st.container(border=True):
            st.markdown(f"**PRIORITY {rank:02} · {opp['score']}/100 · {opp['segment']}**")
            st.subheader(opp["concept"])
            st.write("**Observed signal:** " + opp["observed_pain"])
            a, b = st.columns(2)
            for col, keys in [
                (
                    a,
                    [
                        ("Ad angle", "ad_angle"),
                        ("Content topic", "content_topic"),
                        ("Landing-page message", "landing_page"),
                    ],
                ),
                (
                    b,
                    [
                        ("Email idea", "email_idea"),
                        ("Case study to seek", "case_study_opportunity"),
                        ("Success metric", "suggested_kpi"),
                    ],
                ),
            ]:
                for title, key in keys:
                    col.markdown(f"**{title}**")
                    col.write(opp[key])
            st.success("Next action: " + opp["validation"])
            with st.expander("Why this score? · components and customer evidence"):
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Component": k.replace("_", " ").title(),
                                "Normalized / 100": v,
                                "Weight": r["methodology"]["score_weights"][k],
                            }
                            for k, v in opp["score_components"].items()
                        ]
                    ),
                    hide_index=True,
                )
                quotes(opp["evidence"])
    enrich_status = r["enrichment"]["status"]
    if enrich_status == "complete":
        st.subheader("Optional LLM creative hypotheses")
        st.warning(r["enrichment"]["label"])
        for suggestion in r["enrichment"]["suggestions"]:
            st.write(f"**{suggestion['headline']}**")
            st.write(suggestion["rationale"])
            st.caption("Supporting synthetic records: " + ", ".join(suggestion["evidence_ids"]))
    elif enrich_status == "unavailable":
        st.warning(r["enrichment"]["message"])

st.divider()
with st.expander("Methodology, limitations & run history"):
    st.write(
        "All demo feedback is synthetic. Frequency counts records, and themes can overlap. "
        "Campaign claims require product verification. Persona profiles are research hypotheses."
    )
    st.json(r["methodology"])
    st.caption(f"Run {r['id']} · {r['created_at']}")
    if st.button("Load saved run history"):
        st.session_state.run_history = request("GET", f"/api/datasets/{dataset['id']}/analyses") or []
    history = [h for h in st.session_state.get("run_history", []) if h["dataset_id"] == dataset["id"]]
    if history:
        chosen = st.selectbox(
            "Previous analysis",
            range(len(history)),
            format_func=lambda i: f"{history[i]['created_at']} · {history[i]['id'][:16]}",
        )
        if st.button("Restore selected run"):
            restored = request("GET", f"/api/analyses/{history[chosen]['id']}")
            if restored:
                st.session_state.result = restored
                st.rerun()
