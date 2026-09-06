import argparse
import asyncio
import json
import uuid
from pathlib import Path

from .backends import CorpusBackend, LegacyHybridBackend
from .contracts import ResearchTask
from .experiment import compare, run_experiment


def main():
    parser = argparse.ArgumentParser(description="CreatorPal agent tools and policy experiments")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "compare"):
        sub = commands.add_parser(name)
        sub.add_argument(
            "--adapter", choices=["scripted", "offline-adk", "adk"], default="scripted"
        )
        sub.add_argument("--output", type=Path, default=Path("runs/creatorpal"))
        sub.add_argument("--corpus", type=Path)
        sub.add_argument("--backend", choices=["reference", "legacy"], default="reference")
        sub.add_argument("--rules-corpus", type=Path)
        sub.add_argument("--fast-model")
        sub.add_argument("--strong-model")
        sub.add_argument("--pricing", type=Path)
        if name == "run":
            sub.add_argument("--task", type=Path, required=True)
            sub.add_argument(
                "--policy",
                choices=["eager-fast", "progressive-fast", "progressive-routed"],
                default="progressive-fast",
            )
            sub.add_argument("--sandbox", choices=["restricted", "docker"], default="restricted")
            sub.add_argument("--state", type=Path)
        else:
            sub.add_argument("--cases", type=Path)
            sub.add_argument("--repeats", type=int, default=1)
    args = parser.parse_args()
    if args.adapter == "adk" and not args.fast_model:
        parser.error("Live ADK requires --fast-model and configured Gemini/Vertex authentication")
    if args.command == "compare" and args.adapter == "adk" and not args.strong_model:
        parser.error("Live policy comparisons require --strong-model")
    if (
        args.command == "run"
        and args.policy == "progressive-routed"
        and args.adapter == "adk"
        and not args.strong_model
    ):
        parser.error("Routed policy requires --strong-model")
    backend = CorpusBackend(args.corpus)
    if args.backend == "legacy":
        from src.config import load_settings

        backend = LegacyHybridBackend(load_settings(), args.rules_corpus)
    pricing = json.loads(args.pricing.read_text()) if args.pricing else None
    shared = dict(
        adapter=args.adapter,
        backend=backend,
        fast_model=args.fast_model,
        strong_model=args.strong_model,
        pricing=pricing,
    )
    if args.command == "run":
        task = ResearchTask.model_validate(json.loads(args.task.read_text()))
        result = asyncio.run(
            run_experiment(
                task,
                args.output / (task.id + "-" + uuid.uuid4().hex[:12]),
                policy=args.policy,
                sandbox_backend=args.sandbox,
                state_path=args.state,
                **shared,
            )
        )
        print(
            json.dumps(
                {k: result[k] for k in ("task_id", "completed", "adapter", "receipt")}, indent=2
            )
        )
        return 0 if result["completed"] else 1
    root, results = asyncio.run(
        compare(args.output, cases_path=args.cases, repeats=args.repeats, **shared)
    )
    print(f"Report: {root / 'report.md'}")
    print(f"Completed {sum(r['completed'] for r in results)}/{len(results)} ({args.adapter})")
    return 0 if all(r["completed"] for r in results) else 1
