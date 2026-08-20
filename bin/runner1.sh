#!/bin/bash
# Task Runner One: reads its isolated job config, does its work, then
# triggers Task Runner Two through the systemd broker (never execs it
# directly, so user2 never inherits user1's environment).
set -euo pipefail

JOB_ID="${1:-${JOB_ID:-}}"
if [[ "$1" == "--id" ]]; then
    JOB_ID="$2"
fi

echo "runner1: starting job ${JOB_ID}"

# ... user1's own work goes here ...

echo "runner1: querying task-runner-user2 status prior to execution"
prev_invocation="$(systemctl show task-runner-user2.service -p InvocationID --value)"

echo "runner1: triggering task-runner-user2 via broker (blocking until it finishes)"
sudo /usr/bin/systemctl start --wait task-runner-user2.service || true

curr_invocation="$(systemctl show task-runner-user2.service -p InvocationID --value)"

if [[ -z "${curr_invocation}" || "${curr_invocation}" == "${prev_invocation}" ]]; then
    echo "runner1: error: task-runner-user2.service failed to initiate" >&2
    exit 255
fi

# Query the precise exit code of the execution
runner2_exit="$(systemctl show task-runner-user2.service -p ExecMainStatus --value)"
echo "runner1: task-runner-user2 finished with exit code ${runner2_exit}"

if [[ "${runner2_exit}" -ne 0 ]]; then
    echo "runner1: task-runner-user2 failed" >&2
    exit "${runner2_exit}"
fi
