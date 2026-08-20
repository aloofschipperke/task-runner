#!/bin/bash
# Task Runner Two: runs fully sandboxed (see systemd/task-runner-user2.service).
# Has no access to /etc/task_runner_1, no metadata IP access, and no journal
# read access -- it only ever sees what systemd hands it on ExecStart.
set -euo pipefail

echo "runner2: starting sandboxed work"

# ... user2's own work goes here ...
