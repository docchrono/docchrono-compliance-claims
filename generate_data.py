"""Create or verify the deterministic synthetic compliance corpus."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

FILES: dict[str, str] = {
    "01_invoice_approval.txt": """SYNTHETIC COMPLIANCE RECORD

On March 3, 2026, Maya Chen approved Invoice #381 for Northstar Logistics Corporation.
Maya Chen works for Northstar Logistics Corporation.
""",
    "02_employment_exception.md": """# Synthetic employment exception

Maya Chen does not work for Northstar Logistics Corporation.
""",
    "03_authorization_hold.txt": """SYNTHETIC AUTHORIZATION HOLD

On March 4, 2026, Maya Chen did not authorize Payment #982 for Northstar Logistics Corporation.
""",
    "04_payment_notice.eml": """From: Liam Ortiz <liam.ortiz@example.test>
To: Maya Chen <maya.chen@example.test>
Date: Sat, 7 Mar 2026 10:15:00 -0600
Subject: Synthetic payment notice
Message-ID: <payment-982@example.test>
MIME-Version: 1.0
Content-Type: text/plain; charset=\"utf-8\"

On March 7, 2026, Northstar Logistics Corporation paid Payment #982.
""",
    "05_review_candidate_a.md": """# Synthetic reviewer note A

On March 5, 2026, Jordan Carmichael approved Invoice #700 for Northstar Logistics Corporation.
""",
    "06_review_candidate_b.md": """# Synthetic reviewer note B

On March 6, 2026, Jordon Carmichael approved Invoice #701 for Northstar Logistics Corporation.
""",
}


def generate(*, check: bool = False, data_dir: Path = DATA_DIR) -> tuple[str, ...]:
    """Write the corpus, or return mismatches without modifying it in check mode."""

    mismatches: list[str] = []
    expected_names = set(FILES)
    existing_names: set[str] = (
        {path.name for path in data_dir.iterdir()} if data_dir.exists() else set()
    )

    for name, content in sorted(FILES.items()):
        path = data_dir / name
        if not path.is_file() or path.read_text(encoding="utf-8") != content:
            mismatches.append(name)

    unexpected = sorted(existing_names - expected_names)
    mismatches.extend(f"unexpected:{name}" for name in unexpected)

    if check:
        return tuple(mismatches)

    data_dir.mkdir(parents=True, exist_ok=True)
    for name, content in sorted(FILES.items()):
        (data_dir / name).write_text(content, encoding="utf-8", newline="\n")
    return ()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify committed fixtures instead of rewriting them",
    )
    args = parser.parse_args()
    mismatches = generate(check=args.check)
    if mismatches:
        print("Synthetic corpus is out of date: " + ", ".join(mismatches))
        return 1
    verb = "verified" if args.check else "generated"
    print(f"{len(FILES)} deterministic synthetic documents {verb} in {DATA_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
