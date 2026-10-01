"""Seeded, fictional B2B SaaS feedback. No real people, companies, or quotes."""

import argparse
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from voc.config import ROOT

EXAMPLES = {
    "price": [
        "The price is too expensive for our small team. We need predictable costs as we add seats.",
        "I am worried about pricing before we buy. Extra seat costs make the budget hard to justify.",
        "The pricing is clear and affordable. Consolidating tools made this a useful investment.",
        "We want transparent pricing so we can plan next quarter's budget with confidence.",
    ],
    "onboarding": [
        "The onboarding tutorial is confusing. Our first week was spent asking colleagues for training.",
        "I am concerned about onboarding. Will we need weeks of training before the team is productive?",
        "The onboarding was smooth and the tutorial helpful. We had a useful workflow in our first week.",
        "We need a role-specific onboarding checklist so new teammates can get started independently.",
    ],
    "ease of use": [
        "The interface is confusing. Too many clicks hide the task we do every day.",
        "I am unsure whether the navigation will be easy for our nontechnical colleagues.",
        "The interface is intuitive and easy. The clear navigation makes everyday work faster.",
        "We want fewer clicks and a simple interface so we can finish daily tasks without guidance.",
    ],
    "integrations": [
        "The CRM integration is broken. We are blocked by duplicate data entry and the sync fails.",
        "Does it connect to our existing CRM? I am worried about a missing integration before we commit.",
        "The CRM integration is reliable. The connector saved us from duplicate data entry.",
        "We need a two-way CRM sync so our teams can trust the same customer information.",
    ],
    "customer service": [
        "Support is slow and the ticket response was delayed. We lost a critical deadline waiting for help.",
        "I am concerned about customer service. How long does a support response take for critical issues?",
        "The support agent was excellent and helpful. A responsive service team resolved our question.",
        "We need a clear support route so urgent questions reach the right agent quickly.",
    ],
    "reliability": [
        "An outage blocked our reporting. The crash caused downtime during a critical deadline.",
        "I am worried about reliability. We need proof that the platform is stable before we buy.",
        "The platform is stable and reliable. Reporting runs smoothly and our team feels delighted.",
        "We need reliable performance so we can meet deadlines without worrying about downtime.",
    ],
    "implementation": [
        "The implementation is difficult. A complex migration delayed the rollout and blocked our team.",
        "Implementation seems difficult. I am concerned a migration will disrupt daily work.",
        "The implementation was smooth. A clear rollout plan made the setup simple and easy.",
        "We want a phased implementation so we can migrate without interrupting daily work.",
    ],
    "value": [
        "We spend hours on manual reporting every Monday. It is frustrating to copy numbers between tools.",
        "I am skeptical about the ROI. We need proof of value and time saved before we commit.",
        "The automation saved hours of reporting time. We love spending more time on useful work.",
        "We want to reduce manual work so we can focus on customers instead of spreadsheets.",
    ],
}
CONTEXT = [
    "Our quarterly planning cycle depends on this workflow.",
    "Our distributed team uses this during weekly handoffs.",
    "This came up during our internal tool evaluation.",
    "We discussed this in our latest team retrospective.",
    "This matters when new colleagues join the team.",
    "We compared this with our previous process.",
]
SEGMENTS = ["Operations manager", "Marketing lead", "Founder / SMB", "Revenue operations"]
SOURCES = ["review", "survey", "support_ticket", "sales_note", "interview"]


def generate(rows: int = 640, seed: int = 42) -> pd.DataFrame:
    rng = random.Random(seed)
    records = []
    themes = list(EXAMPLES)
    for i in range(rows):
        theme = rng.choices(themes, weights=[10, 12, 8, 14, 8, 10, 12, 26])[0]
        variant = rng.choices(range(4), weights=[40, 20, 25, 15])[0]
        segment = rng.choice(SEGMENTS)
        if theme == "value" and rng.random() < 0.65:
            segment = "Operations manager"
        source = "sales_note" if variant == 1 else rng.choice(SOURCES)
        records.append(
            {
                "source": source,
                "customer_id": f"SYN-{rng.randrange(max(1, rows // 2)):04d}",
                "date": (date(2026, 4, 1) + timedelta(days=rng.randrange(180))).isoformat(),
                "customer_type": segment,
                "text": EXAMPLES[theme][variant] + " " + rng.choice(CONTEXT),
                "market": rng.choice(["North America", "UK & Ireland", "Nordics", "DACH"]),
                "product": rng.choice(["FlowPilot Core", "FlowPilot Automate"]),
            }
        )
    return pd.DataFrame(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=640)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "synthetic_feedback.csv")
    args = parser.parse_args()
    if not 1 <= args.rows <= 10000:
        parser.error("rows must be between 1 and 10,000")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    generate(args.rows, args.seed).to_csv(args.output, index=False)
    print(f"Wrote {args.rows} synthetic feedback records to {args.output}")


if __name__ == "__main__":
    main()
