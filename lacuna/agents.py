"""Critic agents. Each one reads retrieved sources and returns structured findings."""
from .index import format_sources, retrieve
from .llm import LMStudio

FINDING_SCHEMA = """Return a JSON list. Each item:
{"title": str, "summary": str,
 "provisions": [str],            // e.g. "Residential Tenancies Act 2010 (NSW) s 41"
 "source_ids": [str],            // e.g. ["S2","S5"] - ONLY sources shown to you
 "severity": "low"|"medium"|"high",
 "confidence": "low"|"medium"|"high"}
Return [] if the sources do not support any finding. Never invent sections or cases."""

BASE = ("You are a careful Australian legal analyst. Work only from the numbered sources "
        "provided. Cite source ids for every claim. ")

AGENTS = {
    "conflict": {
        "role": BASE + (
            "Find misalignments between levels of law: the Commonwealth Constitution, "
            "Commonwealth Acts and regulations, and State law. Look for direct and indirect "
            "inconsistency (s 109), covering-the-field problems, gaps where neither level "
            "regulates, duplicated or contradictory obligations, and definitions that differ."),
        "filter": None,
    },
    "loophole": {
        "role": BASE + (
            "Find ways the law could be gamed or avoided: definitional gaps, thresholds that "
            "invite structuring, missing anti-avoidance rules, weak enforcement or penalties, "
            "jurisdictional arbitrage between States, and timing tricks. Describe the "
            "weakness and why it matters for law reform; do not write step-by-step "
            "instructions for misconduct."),
        "filter": None,
    },
    "precedent": {
        "role": BASE + (
            "Using court decisions, identify where courts have exposed problems with the "
            "legislation: provisions read down or found invalid, ambiguous wording that "
            "produced conflicting decisions, judicial criticism of drafting, and outcomes "
            "that defeat the apparent purpose of the law."),
        "filter": {"type": "decision"},
    },
    "common_law": {
        "role": BASE + (
            "Analyse the common law (judge-made law) on this subject and how it interacts "
            "with legislation. Identify: common law rules that statute has abrogated, "
            "modified or codified incompletely; gaps where only the common law applies and "
            "is uncertain; conflicting lines of authority between State courts or between "
            "intermediate courts and the High Court; equitable doctrines or implied terms "
            "that cut across the statutory scheme; and common law rules that can be "
            "exploited to avoid a statutory obligation. State the principle and the case "
            "it comes from for every claim."),
        # Half court decisions (where the common law lives), half legislation to compare it with.
        "filter": "mixed",
    },
}


def plan_questions(llm: LMStudio, topic: str, n: int) -> list[str]:
    out = llm.chat_json(
        "You design research agendas for Australian law reform.",
        f"Topic: {topic.replace('_', ' ')}.\nWrite {n} specific research questions that would "
        "reveal conflicts between Constitution, federal and state law, loopholes, or problems "
        "revealed by case law, or tensions between the common law and statute. Return a JSON list of strings.")
    return [q for q in (out or []) if isinstance(q, str)][:n] or [f"Problems with {topic} law"]


def run_agent(cfg: dict, llm: LMStudio, name: str, question: str) -> list[dict]:
    spec = AGENTS[name]
    k = cfg["analysis"]["retrieve_k"]
    if spec["filter"] == "mixed":
        chunks = (retrieve(cfg, llm, question, (k + 1) // 2, {"type": "decision"})
                  + retrieve(cfg, llm, question, k // 2, {"type": {"$ne": "decision"}}))
    else:
        chunks = retrieve(cfg, llm, question, k, spec["filter"])
    if not chunks:
        return []
    sources = format_sources(chunks)
    out = llm.chat_json(spec["role"] + "\n\n" + FINDING_SCHEMA,
                        f"Question: {question}\n\nSOURCES:\n{sources}")
    findings = []
    for f in out if isinstance(out, list) else []:
        if not isinstance(f, dict) or not f.get("title"):
            continue
        f["agent"], f["question"] = name, question
        f["sources"] = _resolve(f.get("source_ids", []), chunks)
        f["_context"] = sources
        findings.append(f)
    return findings


def verify(llm: LMStudio, finding: dict) -> dict:
    """Skeptical second pass: is the finding actually supported by its sources?"""
    verdict = llm.chat_json(
        "You are a skeptical senior barrister reviewing a junior's claim. Check it strictly "
        "against the sources. Reject anything not directly supported, any cited provision "
        "that does not appear in the sources, and any overstated conclusion.\n"
        'Return {"verdict": "supported"|"partly_supported"|"rejected", "reason": str}',
        f"CLAIM:\n{finding['title']}\n{finding.get('summary','')}\n"
        f"Provisions: {finding.get('provisions')}\nCited: {finding.get('source_ids')}\n\n"
        f"SOURCES:\n{finding['_context']}",
        model=llm.verifier_model)
    verdict = verdict if isinstance(verdict, dict) else {}
    finding["verdict"] = verdict.get("verdict", "rejected")
    finding["verdict_reason"] = verdict.get("reason", "verifier returned no usable answer")
    return finding


def _resolve(ids: list, chunks: list[dict]) -> list[dict]:
    out = []
    for sid in ids:
        try:
            c = chunks[int(str(sid).strip("[]S")) - 1]
        except (ValueError, IndexError):
            continue
        out.append({"citation": c["citation"], "url": c["url"], "jurisdiction": c["jurisdiction"]})
    return out
