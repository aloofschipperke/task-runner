#!/bin/bash
# Run once while baking the golden AMI (as root, via the SSM Automation
# document's inner command/patch step). Creates the two isolated service
# users and installs the systemd units / sudoers exception / runner binaries.
set -euo pipefail

# Two unprivileged, non-login system users
useradd -m -s /sbin/nologin user1
useradd -m -s /sbin/nologin user2

# IMPORTANT: never add user2 to adm / systemd-journal / wheel, so a plain
# `journalctl` as user2 fails with "Permission denied".

install -m 0644 systemd/task-runner-user1.service /etc/systemd/system/task-runner-user1.service
install -m 0644 systemd/task-runner-user2.service /etc/systemd/system/task-runner-user2.service

install -m 0440 sudoers.d/task_runners /etc/sudoers.d/task_runners
visudo -cf /etc/sudoers.d/task_runners

install -m 0755 bin/runner1.sh /usr/local/bin/runner1
install -m 0755 bin/runner2.sh /usr/local/bin/runner2

systemctl daemon-reload

echo "bootstrap-golden-image: done. task-runner-user1 will be enabled at boot via cloud-init; task-runner-user2 is left disabled/idle."
