import json
from datetime import date
from pathlib import Path

from .pdf import write_pdf

ORDER = {"high": 0, "medium": 1, "low": 2}
TITLES = {"conflict": "Conflicts between levels of law",
          "loophole": "Areas open to gaming",
          "precedent": "Problems exposed by case law",
          "common_law": "Common law vs statute",
          "local_law": "Council local laws"}


def write_report(cfg: dict, findings: list[dict]) -> Path:
    topic = cfg["topic"]["name"]
    out_dir = Path(cfg["paths"]["report_dir"])
    clean = [{k: v for k, v in f.items() if k != "_context"} for f in findings]
    (out_dir / f"{topic}_findings.json").write_text(json.dumps(clean, indent=2), encoding="utf-8")

    kept = [f for f in clean if f.get("verdict") != "rejected"]
    lines = [f"# {topic.replace('_', ' ').title()}: findings",
             f"_Generated {date.today()} by local models. Not legal advice; every item "
             "needs checking by a person against the current law._",
             f"\n{len(kept)} findings kept, {len(clean) - len(kept)} rejected by the verifier.\n"]
    for agent, heading in TITLES.items():
        group = sorted((f for f in kept if f["agent"] == agent),
                       key=lambda f: ORDER.get(f.get("severity"), 3))
        lines.append(f"## {heading} ({len(group)})\n")
        for f in group:
            lines.append(f"### {f['title']}")
            lines.append(f"**Severity:** {f.get('severity')} · **Confidence:** "
                         f"{f.get('confidence')} · **Verifier:** {f['verdict']}\n")
            lines.append(f"{f.get('summary', '')}\n")
            if f.get("provisions"):
                lines.append("**Provisions:** " + "; ".join(map(str, f["provisions"])))
            for s in f.get("sources", []):
                lines.append(f"- [{s['citation']}]({s['url']}) ({s['jurisdiction']})")
            lines.append(f"\n> Verifier: {f['verdict_reason']}\n")
    path = out_dir / f"{topic}_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    ranked = sorted(kept, key=lambda f: ORDER.get(f.get("severity"), 3))
    try:
        pdf = write_pdf(out_dir / f"{topic}_report.pdf", topic, ranked,
                        len(clean) - len(kept), TITLES)
        print("pdf:", pdf)
    except Exception as e:  # never lose the analysis because of a PDF problem
        print(f"PDF failed ({e}); markdown and JSON reports are still saved.")
    return path
