from __future__ import annotations

from skill_evolution.validators import validate

ORIGINAL = """---
name: example-docx
description: Create .docx Word documents from user prompts.
---

# example-docx

Body.
"""

IMPROVED = """---
name: example-docx
description: Create .docx Word documents from user prompts, including Korean text.
---

# example-docx

Body with more detail.
"""


def test_valid_change_passes():
    report = validate(
        ORIGINAL,
        IMPROVED,
        max_lines=500,
        description_ratio_min=0.2,
        description_ratio_max=3.0,
    )
    assert report.passed, report.failed_gate


def test_name_change_is_blocked():
    bad = IMPROVED.replace("name: example-docx", "name: renamed-skill")
    report = validate(
        ORIGINAL,
        bad,
        max_lines=500,
        description_ratio_min=0.2,
        description_ratio_max=3.0,
    )
    assert not report.passed
    assert report.failed_gate == "frontmatter"


def test_oversize_is_blocked():
    big = IMPROVED + "\nfiller\n" * 600
    report = validate(
        ORIGINAL,
        big,
        max_lines=500,
        description_ratio_min=0.2,
        description_ratio_max=3.0,
    )
    assert not report.passed
    assert report.failed_gate == "size"


def test_description_bloat_is_blocked():
    bloated = IMPROVED.replace(
        "description: Create .docx Word documents from user prompts, including Korean text.",
        "description: " + ("word " * 200),
    )
    report = validate(
        ORIGINAL,
        bloated,
        max_lines=500,
        description_ratio_min=0.2,
        description_ratio_max=3.0,
    )
    assert not report.passed
    assert report.failed_gate == "description_drift"


def test_missing_frontmatter_is_blocked():
    no_fm = "# example-docx\n\nBody\n"
    report = validate(
        ORIGINAL,
        no_fm,
        max_lines=500,
        description_ratio_min=0.2,
        description_ratio_max=3.0,
    )
    assert not report.passed
    assert report.failed_gate == "frontmatter"
