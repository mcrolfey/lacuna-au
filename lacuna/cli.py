import argparse

from .agents import AGENTS, plan_questions, run_agent, verify
from .config import load_config
from .index import build_index
from .ingest import ingest
from .llm import LMStudio
from .report import write_report


def main():
    p = argparse.ArgumentParser(prog="lacuna")
    p.add_argument("command", choices=["check", "ingest", "index", "analyse", "all"])
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--agents", default=",".join(AGENTS), help="comma-separated subset")
    args = p.parse_args()

    cfg = load_config(args.config)
    llm = LMStudio(cfg)

    if args.command == "check":
        models = llm.ping()
        print("LM Studio models loaded:", models)
        for key in ("chat_model", "embed_model"):
            name = cfg["lmstudio"][key]
            print(f"  {key}: {name} -> {'OK' if name in models else 'NOT FOUND'}")
        return
    if args.command in ("ingest", "all"):
        ingest(cfg)
    if args.command in ("index", "all"):
        build_index(cfg, llm)
    if args.command in ("analyse", "all"):
        analyse(cfg, llm, args.agents.split(","))


def analyse(cfg: dict, llm: LMStudio, agents: list[str]) -> None:
    questions = plan_questions(llm, cfg["topic"]["name"], cfg["analysis"]["questions_per_topic"])
    findings = []
    for qi, q in enumerate(questions, 1):
        print(f"[{qi}/{len(questions)}] {q}")
        for name in agents:
            for f in run_agent(cfg, llm, name, q):
                findings.append(verify(llm, f))
                print(f"   {name}: {f['title']} -> {f['verdict']}")
    print("report:", write_report(cfg, findings))


if __name__ == "__main__":
    main()
