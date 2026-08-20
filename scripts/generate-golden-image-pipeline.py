#!/usr/bin/env python3
"""Regenerate automation/golden-image-pipeline.yml from
automation/golden-image-pipeline.yml.tmpl plus the live source files under
systemd/, sudoers.d/, bin/, and scripts/bootstrap-golden-image.sh.

Run this after editing any of those source files, or after editing the
.tmpl, so the embedded heredoc block in BootstrapTaskRunnerAssets can't
drift from the actual files. Do not hand-edit the generated .yml.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "automation" / "golden-image-pipeline.yml.tmpl"
OUTPUT = ROOT / "automation" / "golden-image-pipeline.yml"
PLACEHOLDER = "__BOOTSTRAP_COMMANDS__"
INDENT = " " * 12

# (heredoc delimiter, source file, destination path on the build instance)
ASSETS = [
    ("EOF_UNIT1", "systemd/task-runner-user1.service",
     "/tmp/task-runner-assets/systemd/task-runner-user1.service"),
    ("EOF_UNIT2", "systemd/task-runner-user2.service",
     "/tmp/task-runner-assets/systemd/task-runner-user2.service"),
    ("EOF_SUDOERS", "sudoers.d/task_runners",
     "/tmp/task-runner-assets/sudoers.d/task_runners"),
    ("EOF_RUNNER1", "bin/runner1.sh",
     "/tmp/task-runner-assets/bin/runner1.sh"),
    ("EOF_RUNNER2", "bin/runner2.sh",
     "/tmp/task-runner-assets/bin/runner2.sh"),
    ("EOF_BOOTSTRAP", "scripts/bootstrap-golden-image.sh",
     "/tmp/task-runner-assets/scripts/bootstrap-golden-image.sh"),
    ("EOF_CLOUDWATCH", "cloudwatch/cloudwatch-agent-config.json",
     "/tmp/task-runner-assets/cloudwatch/cloudwatch-agent-config.json"),
]


def build_commands_script() -> str:
    lines = [
        "set -euo pipefail",
        "mkdir -p /tmp/task-runner-assets/systemd /tmp/task-runner-assets/sudoers.d "
        "/tmp/task-runner-assets/bin /tmp/task-runner-assets/scripts /tmp/task-runner-assets/cloudwatch",
        "",
    ]
    for delimiter, src, dest in ASSETS:
        content = (ROOT / src).read_text().rstrip("\n")
        lines.append(f"cat <<'{delimiter}' > {dest}")
        lines.extend(content.split("\n"))
        lines.append(delimiter)
        lines.append("")
    lines += [
        "chmod +x /tmp/task-runner-assets/bin/*.sh /tmp/task-runner-assets/scripts/bootstrap-golden-image.sh",
        "cd /tmp/task-runner-assets && bash scripts/bootstrap-golden-image.sh",
        "rm -rf /tmp/task-runner-assets",
    ]
    return "\n".join(lines)


def indent_block(text: str) -> str:
    return "\n".join(INDENT + line if line else "" for line in text.split("\n"))


def main() -> None:
    template = TEMPLATE.read_text()
    if PLACEHOLDER not in template:
        sys.exit(f"error: placeholder {PLACEHOLDER!r} not found in {TEMPLATE}")

    commands_block = indent_block(build_commands_script())
    rendered = template.replace(PLACEHOLDER, commands_block)

    banner = (
        "# GENERATED FILE -- do not hand-edit.\n"
        "# Source: golden-image-pipeline.yml.tmpl + systemd/, sudoers.d/, bin/,\n"
        "# scripts/bootstrap-golden-image.sh. Regenerate with:\n"
        "#   scripts/generate-golden-image-pipeline.py\n"
    )
    OUTPUT.write_text(banner + rendered)
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
