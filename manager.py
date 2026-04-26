#!/usr/bin/env python3
"""
LAIWM — Local AI Workflow Manager
Usage: python manager.py --prompt "your request here"
"""
import argparse
import sys

import config
from config import log
import classifier
from workflows import run_workflow


def _check_connection() -> None:
    """Verify the Ollama server is reachable; exit with a friendly message if not."""
    try:
        config.client.list()
    except Exception:
        log(f"Cannot reach Ollama at {config.SERVER_API_HOST} — is the server running?")
        sys.exit(1)


def main() -> None:
    """Parse CLI args, classify the prompt, resolve missing params, and dispatch to the matching workflow."""
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

    log(f"LAIWM — {config.MODEL_NAME} @ {config.SERVER_API_HOST}")
    _check_connection()
    log("Classifying request...")

    try:
        routing = classifier.classify(args.prompt)
    except Exception as e:
        log(f"Failed to classify request: {e}")
        sys.exit(1)

    config.dbg(f"Routing result: mode={routing.mode} confidence={routing.confidence:.0%} params={routing.params} missing={routing.missing}")

    if not routing.mode or routing.confidence < 0.4:
        log(f"Could not confidently match your request to a workflow (confidence: {routing.confidence:.0%}).")
        sys.exit(1)

    log(f"Mode: {routing.mode} (confidence: {routing.confidence:.0%})")

    params = classifier.resolve(routing, args.prompt)
    config.dbg(f"Final params: {params}")

    run_workflow(routing.mode, params)


if __name__ == "__main__":
    main()