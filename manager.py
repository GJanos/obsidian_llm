#!/usr/bin/env python3
"""
LAIWM — Local AI Workflow Manager
Usage: python manager.py --prompt "your request here"
"""
import argparse
import sys

import config
import classifier
from workflows import run_workflow


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LAIWM — Local AI Workflow Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               '  python manager.py --prompt "summarize my March 2026 notes"\n'
               '  python manager.py --prompt "search for meeting notes about project X"',
    )
    parser.add_argument("--prompt", required=True, help="Your request in natural language")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.debug:
        config.DEBUG = True

    print("[LAIWM] Classifying request...")

    try:
        routing = classifier.classify(args.prompt)
    except Exception as e:
        print(f"[LAIWM] Failed to classify request: {e}")
        sys.exit(1)

    config.dbg(f"Routing result: mode={routing.mode} confidence={routing.confidence:.0%} params={routing.params} missing={routing.missing}")

    if not routing.mode or routing.confidence < 0.4:
        print(f"[LAIWM] Could not confidently match your request to a workflow (confidence: {routing.confidence:.0%}).")
        sys.exit(1)

    print(f"[LAIWM] Mode: {routing.mode} (confidence: {routing.confidence:.0%})")

    missing = [p for p in routing.missing if p not in classifier.PATH_PARAMS]
    for key in classifier.PATH_PARAMS:
        if key in routing.missing and key not in routing.params:
            routing.params[key] = ""

    params = classifier.collect_missing_params(missing, routing.params)
    params = classifier.prepend_vault_path(params)
    config.dbg(f"Final params: {params}")

    run_workflow(routing.mode, params)


if __name__ == "__main__":
    main()
