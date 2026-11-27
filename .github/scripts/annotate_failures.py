"""Turn pytest failures into GitHub Actions annotations.

Annotations appear on the PR page and the run summary, so a failure can be
read without opening (or having access to) the full job log.

    python annotate_failures.py pytest-output.txt test-results.xml
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_TESTS = 8  # GitHub shows at most 10 error annotations per step
MAX_CHARS = 3000
TAIL_LINES = 40


def encode(text: str) -> str:
    """Escape a message for a workflow command."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def annotate(title: str, message: str) -> None:
    message = message.strip()
    if len(message) > MAX_CHARS:
        message = "…" + message[-MAX_CHARS:]
    print(f"::error title={encode(title).replace(',', '%2C')}::{encode(message)}")


def failed_tests(junit: Path) -> list[tuple[str, str]]:
    if not junit.is_file():
        return []
    try:
        root = ET.parse(junit).getroot()
    except ET.ParseError:
        return []
    found = []
    for case in root.iter("testcase"):
        for tag in ("failure", "error"):
            node = case.find(tag)
            if node is not None:
                name = f"{case.get('classname', '')}::{case.get('name', '')}"
                found.append((name, (node.get("message") or "") + "\n" + (node.text or "")))
    return found


def main(output_file: str, junit_file: str) -> int:
    failures = failed_tests(Path(junit_file))
    for name, detail in failures[:MAX_TESTS]:
        annotate(f"Test failed: {name}", detail)

    output = Path(output_file)
    if output.is_file():
        lines = output.read_text(encoding="utf-8", errors="replace").splitlines()
        # The end of the output holds the short summary, or the traceback of a crash.
        annotate("pytest output (last lines)", "\n".join(lines[-TAIL_LINES:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:3]))
