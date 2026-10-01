import html
import io
import json

import pandas as pd


def md_text(value) -> str:
    # Escape synthetic/uploaded text so quotes cannot introduce report markup or links.
    text = str(value).replace("\n", " ").replace("\r", " ")
    for char in "\\`*_{}[]<>#|":
        text = text.replace(char, "\\" + char)
    return text


def markdown_report(result: dict) -> str:
    s = result["summary"]
    lines = [
        "# Voice of Customer Marketing Report",
        "",
        "**All demo customer data is synthetic.**",
        "Personas and campaign concepts are generated hypotheses, not validated market findings.",
        "",
        f"Run: `{result['id']}` | Dataset: `{result['dataset_id']}`",
        f"Created: {result['created_at']} | Method: {result['methodology']['version']}",
        "",
        f"Scope: {s['records']} records from {s['unique_customers']} distinct synthetic customer IDs.",
        f"Period: {s['date_from']} to {s['date_to']}",
        "Filters: " + md_text(json.dumps(result.get("filters", {}))),
        "",
        "## Top findings",
        "",
    ]
    for t in result["themes"][:5]:
        lines.append(
            f"- **{md_text(t['theme'].title())}**: {t['frequency']} records ({t['share_pct']}% of scope)."
        )
    if not result["themes"]:
        lines.append(
            "No taxonomy themes matched in this scope. Review the source text and exploratory clusters."
        )
    lines += ["", "## Pain points and synthetic customer quotes", ""]
    for pain in result["pain_points"][:5]:
        lines += [
            f"### {md_text(pain['problem'])}",
            f"{pain['frequency']} records; severity {pain['severity']}/3; segments: "
            + md_text(", ".join(pain["segments"])),
            "",
        ]
        for quote in pain["evidence"][:2]:
            lines += [
                "> " + md_text(quote["text"]),
                "",
                f"Synthetic quote · `{quote['record_id']}` · {md_text(quote['customer_type'])}",
                "",
            ]
    lines += ["## Objections and messaging recommendations", ""]
    for objection in result["objections"][:5]:
        lines += [
            f"- **{md_text(objection['theme'].title())}** ({objection['frequency']} records): "
            + md_text(objection["recommended_response"])
        ]
    lines += ["", "## Campaign recommendations and priority actions", ""]
    for rank, opp in enumerate(result["opportunities"][:5], 1):
        lines += [
            f"### {rank}. {md_text(opp['concept'])} — {opp['score']}/100",
            "",
            f"- Observed signal: {md_text(opp['observed_pain'])} ({opp['frequency']} records).",
            f"- Target hypothesis: {md_text(opp['segment'])}.",
            f"- Ad angle: {md_text(opp['ad_angle'])}",
            f"- Content: {md_text(opp['content_topic'])}",
            f"- Landing page: {md_text(opp['landing_page'])}",
            f"- Email: {md_text(opp['email_idea'])}",
            f"- Case study to seek: {md_text(opp['case_study_opportunity'])}",
            f"- Next action: {md_text(opp['validation'])}",
            f"- Success metric: {md_text(opp['suggested_kpi'])}",
            "",
        ]
    lines += ["## Customer Language Library", ""]
    for phrase in result["language_library"][:12]:
        lines += [
            f"- {md_text(phrase['category'])}: “{md_text(phrase['phrase'])}” ({phrase['frequency']} records)."
        ]
    lines += ["", "## Persona hypotheses", ""]
    for segment in result["segments"]:
        lines += [
            f"- **{md_text(segment['profile'])}** / {md_text(segment['segment'])}: "
            + md_text("; ".join(segment["needs"]))
            + f". {md_text(segment['status'])}."
        ]
    if result.get("enrichment", {}).get("status") == "complete":
        lines += ["", "## Optional LLM creative hypotheses", ""]
        for suggestion in result["enrichment"]["suggestions"]:
            lines += [f"- {md_text(suggestion['headline'])}: {md_text(suggestion['rationale'])}"]
    lines += [
        "",
        "## Methodology and limitations",
        "",
        (
            "Frequency counts distinct feedback records, not customers. Themes can overlap. "
            "Negative sentiment is a proxy for pain; questions and concerns are objection candidates."
        ),
        (
            "Priority = 35% frequency + 30% severity + 20% commercial relevance + 15% segment size. "
            "Components are normalized to 0–100; severity uses a 1–3 scale. "
            "Commercial relevance is a curated assumption, not revenue evidence. "
            "Segment size counts distinct customer IDs in the largest affected segment."
        ),
        "",
    ]
    lines.extend("- " + item for item in result["methodology"]["limitations"])
    return "\n".join(lines) + "\n"


def html_report(result: dict) -> str:
    def escape(value):
        return html.escape(str(value))

    s = result["summary"]
    sections = [
        '<div class="eyebrow">SIGNAL STUDIO / STRATEGY BRIEF</div>',
        "<h1>Voice of Customer<br>Marketing Report</h1>",
        '<p class="badge">ALL DEMO CUSTOMER DATA IS SYNTHETIC</p>',
        "<p>Personas and campaigns are generated hypotheses. Validate with interviews and product evidence.</p>",
        f'<p class="meta">Run {escape(result["id"])} · {escape(result["created_at"])}</p>',
        (
            f'<p class="meta">Dataset {escape(result["dataset_id"])} · '
            f"{escape(s['date_from'])} — {escape(s['date_to'])}</p>"
        ),
        f'<p class="meta">Filters: {escape(json.dumps(result.get("filters", {})))}</p>',
        (
            f'<div class="metrics"><div><strong>{s["records"]}</strong>Feedback records</div>'
            f"<div><strong>{s['unique_customers']}</strong>Synthetic customers</div>"
            f"<div><strong>{len(result['opportunities'])}</strong>Campaign opportunities</div></div>"
        ),
        "<h2>01 / Top findings</h2><table><tr><th>Theme</th><th>Records</th><th>Share of scope</th></tr>",
    ]
    for t in result["themes"][:5]:
        sections.append(
            f"<tr><td>{escape(t['theme'].title())}</td><td>{t['frequency']}</td>"
            f"<td>{t['share_pct']}%</td></tr>"
        )
    sections.append("</table><h2>02 / Pain points &amp; customer evidence</h2>")
    for pain in result["pain_points"][:5]:
        sections.append(
            f"<article><h3>{escape(pain['problem'])}</h3><p>{pain['frequency']} records · "
            f"Severity {pain['severity']}/3 · {escape(', '.join(pain['segments']))}</p>"
        )
        for quote in pain["evidence"][:2]:
            sections.append(
                f"<blockquote>{escape(quote['text'])}<footer>SYNTHETIC QUOTE · "
                f"{escape(quote['record_id'])} · {escape(quote['customer_type'])}</footer></blockquote>"
            )
        sections.append("</article>")
    sections.append("<h2>03 / Objections &amp; messaging</h2>")
    for obj in result["objections"][:5]:
        sections.append(
            f"<p><b>{escape(obj['theme'].title())}</b> · {obj['frequency']} records<br>"
            f"{escape(obj['recommended_response'])}</p>"
        )
    sections.append("<h2>04 / Campaign recommendations &amp; priority actions</h2>")
    for rank, opp in enumerate(result["opportunities"][:5], 1):
        sections.append(
            f'<article class="campaign"><p class="badge">PRIORITY {rank:02} · '
            f"{opp['score']}/100</p><h3>{escape(opp['concept'])}</h3>"
            f"<p>{escape(opp['observed_pain'])} · {opp['frequency']} records · "
            f"{escape(opp['segment'])}</p><dl>"
        )
        for label, key in [
            ("Ad angle", "ad_angle"),
            ("Content topic", "content_topic"),
            ("Landing-page message", "landing_page"),
            ("Email", "email_idea"),
            ("Case study to seek", "case_study_opportunity"),
            ("Next action", "validation"),
            ("Success metric", "suggested_kpi"),
        ]:
            sections.append(f"<dt>{label}</dt><dd>{escape(opp[key])}</dd>")
        sections.append("</dl></article>")
    sections.append("<h2>05 / Customer language &amp; persona hypotheses</h2><ul>")
    for item in result["language_library"][:12]:
        sections.append(
            f"<li>{escape(item['category'])}: <b>“{escape(item['phrase'])}”</b> "
            f"({item['frequency']} records)</li>"
        )
    sections.append("</ul>")
    for segment in result["segments"]:
        sections.append(
            f"<p><b>{escape(segment['profile'])}</b> / {escape(segment['segment'])}<br>"
            f"{escape('; '.join(segment['needs']))}<br><small>{escape(segment['status'])}</small></p>"
        )
    if result.get("enrichment", {}).get("status") == "complete":
        sections.append("<h2>06 / Optional LLM creative hypotheses</h2>")
        for item in result["enrichment"]["suggestions"]:
            sections.append(f"<p><b>{escape(item['headline'])}</b><br>{escape(item['rationale'])}</p>")
    sections.append(
        "<h2>Methodology &amp; limitations</h2><p>Frequency counts distinct feedback records; "
        "themes can overlap. Severity: 1 mild, 2 friction, 3 critical. "
        "Priority = 35% frequency + 30% severity + 20% curated commercial relevance + 15% "
        "segment size, each normalized to 0–100. Segment size uses distinct customer IDs in "
        "the largest affected segment. Commercial relevance is an assumption, not measured revenue.</p><ul>"
    )
    sections.extend(f"<li>{escape(item)}</li>" for item in result["methodology"]["limitations"])
    sections.append("</ul>")
    body = "\n".join(sections)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Voice of Customer Marketing Report</title><style>
body{{max-width:900px;margin:40px auto;padding:32px;color:#172b36;background:#fff;font:15px/1.65 system-ui}}
h1{{font-size:46px;line-height:1.12;letter-spacing:-1.5px}}h2{{margin-top:48px;color:#136f63;font-size:21px}}
h3{{font-size:23px;margin:12px 0}}.eyebrow{{letter-spacing:2px;font-size:11px;color:#136f63;font-weight:700}}
.badge{{display:inline-block;padding:4px 10px;border-radius:4px;background:#e5f2ed;color:#136f63;font-size:11px;
font-weight:700}}.meta,small,footer{{color:#6b7d86;font-size:12px}}.metrics{{display:flex;gap:48px;margin:32px 0}}
.metrics strong{{display:block;font-size:36px}}table{{width:100%;border-collapse:collapse;text-align:left}}
th,td{{padding:10px;border-bottom:1px solid #e4e9ec}}blockquote{{margin:18px 0;background:#f0f5f4;padding:18px;
border-left:3px solid #136f63}}footer{{margin-top:10px}}article{{break-inside:avoid}}
.campaign{{border:1px solid #dce6e4;border-radius:10px;padding:24px;margin:20px 0}}
dt{{font-weight:650;color:#136f63}}dd{{margin:0 0 12px}}@media print{{body{{margin:0;padding:12px}}
h1{{font-size:36px}}h2{{break-after:avoid}}}}@media(max-width:600px){{body{{padding:20px}}h1{{font-size:34px}}
.metrics{{gap:20px;font-size:11px}}}}
</style></head><body>{body}</body></html>"""


def opportunities_csv(result: dict) -> str:
    columns = [
        "theme",
        "concept",
        "segment",
        "frequency",
        "score",
        "ad_angle",
        "content_topic",
        "landing_page",
        "email_idea",
        "case_study_opportunity",
        "message",
        "validation",
    ]
    frame = pd.DataFrame(result["opportunities"], columns=columns)
    # Prevent spreadsheet formula injection on exported metadata.
    for column in frame.columns:
        frame[column] = frame[column].map(
            lambda x: "'" + x if isinstance(x, str) and x.lstrip().startswith(("=", "+", "-", "@")) else x
        )
    buffer = io.StringIO()
    frame.to_csv(buffer, index=False, lineterminator="\n")
    return buffer.getvalue()
