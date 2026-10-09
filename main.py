"""
AI Resume Screening & Ranking System — CLI entry point.

Usage:
    python main.py --input ./resumes --output ./output/results.json
    python main.py --input ./resumes --output ./output/results.json --no-llm
    python main.py --input ./resumes --output ./output/results.json --verbose
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Load .env file if python-dotenv is available (graceful if not installed)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    pass

from src.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="AI Resume Screening & Ranking System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--input",
        type=Path,
        default=Path("./resumes"),
        metavar="DIR",
        help="Directory containing resume files (default: ./resumes)",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("./output/results.json"),
        metavar="FILE",
        help="Output JSON path (default: ./output/results.json)",
    )
    p.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM calls and use deterministic fallback only",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging",
    )
    return p


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quiet noisy third-party loggers unless verbose
    if not verbose:
        for lib in ("httpx", "httpcore", "urllib3", "openai", "google"):
            logging.getLogger(lib).setLevel(logging.WARNING)


def main() -> int:
    args = build_parser().parse_args()
    configure_logging(args.verbose)

    try:
        run_pipeline(
            input_dir=args.input,
            output_path=args.output,
            use_llm=not args.no_llm,
        )
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        return 1
    except Exception as exc:
        logging.getLogger(__name__).exception("Unexpected error: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
