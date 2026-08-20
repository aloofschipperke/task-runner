# Chained, Isolated Task Runners on SSM-Managed EC2

Implementation of the design captured in `../NOTES.md`: two systemd task
runners on the same instance, `user1` and `user2`, where `user1` triggers
`user2` through a root-brokered `systemctl` call, and `user2` can never see
`user1`'s parameters, network path, or logs -- even under privilege
escalation inside its own sandbox.

## Layout

- `systemd/` — the two unit files (`task-runner-user1.service`,
  `task-runner-user2.service`). Only user1 is enabled at boot; user2 has no
  `[Install]` section and is only ever started via the broker.
- `sudoers.d/task_runners` — the single, narrow `NOPASSWD` exception letting
  `user1` run exactly one command: `systemctl start --wait task-runner-user2.service`.
  `--wait` blocks `runner1.sh` until user2's service actually deactivates,
  rather than returning as soon as the start job is accepted; sudoers matches
  the command line verbatim, so `--wait` has to be whitelisted explicitly.
- `bin/` — placeholder runner executables (`runner1.sh`, `runner2.sh`) showing
  where each service's `ExecStart` points and how user1 triggers user2.
- `scripts/bootstrap-golden-image.sh` — one-time golden-image bake step:
  creates `user1`/`user2` (both `nologin`, neither in `adm`/`systemd-journal`/
  `wheel`), installs the units, sudoers rule, and runner binaries.
- `automation/golden-image-pipeline.yml` — **generated, do not hand-edit.**
  The single custom SSM Automation Document covering the whole golden-image
  pipeline: launch a temp instance from `LaunchTemplateId`/`SourceAmiId` →
  wait for the SSM Agent to register → patch OS packages
  (`AWS-RunPatchBaseline`) → push this repo's `systemd/`, `sudoers.d/`,
  `bin/`, and `scripts/bootstrap-golden-image.sh` onto it inline (via
  heredocs in an `aws:runCommand` step, no S3 round-trip -- everything here
  is small plain text) and run the bootstrap script → snapshot the AMI →
  terminate the temp instance → copy cross-region → wait for availability →
  publish `Parameter Store` pointers in both regions.

  This deliberately does **not** delegate to AWS's `AWS-UpdateLinuxAmi`
  document: that document launches its own instance (ignoring our Launch
  Template), bakes and terminates everything internally, and hands back only
  a patched-only AMI ID -- there's no window in which to run
  `BootstrapTaskRunnerAssets` against it. Owning the launch → patch →
  bootstrap → image → terminate lifecycle directly is what makes injecting
  our own bootstrap step possible.
- `automation/golden-image-pipeline.yml.tmpl` — the actual source for the
  document above. Everything is static except the `BootstrapTaskRunnerAssets`
  commands block, which is rendered in.
- `scripts/generate-golden-image-pipeline.py` — renders `.tmpl` +
  `systemd/`, `sudoers.d/`, `bin/`, `scripts/bootstrap-golden-image.sh` into
  `automation/golden-image-pipeline.yml`. **Run this after editing any of
  those source files**, so the embedded heredoc block can't drift from what
  actually ships on the golden image.
- `automation/launch-worker-with-params.yml` — a smaller Automation document
  that launches a worker from the Launch Template with a `JobId` pushed in
  via User Data (Push method). Its inline `UserData` block writes user1's
  isolated config (`0640`, owned by `user1:user1`), locks down the directory,
  preps user2's private log file, enables only `task-runner-user1.service`
  at boot, and shreds the cloud-init user-data cache afterward so user2
  can't recover secrets from instance metadata history.
- `iam/` — three policies: the Automation Assume Role's trust policy; its
  permissions policy, covering the full `golden-image-pipeline.yml` lifecycle
  (`RunInstances`/`DescribeInstances`/`TerminateInstances` for the temp
  instance, `CreateImage`/`CopyImage`/`DescribeImages` for the AMI,
  `SendCommand`/`GetCommandInvocation`/`ListCommandInvocations` for the
  patch and bootstrap `runCommand` steps, `DescribeInstanceInformation` for
  the managed-instance wait, scoped `iam:PassRole`, and `PutParameter` scoped
  to the actual `/images/golden-ami-latest` path in both regions); and the
  Session Manager policy that allows `SSM-SessionManagerRunShell` while
  denying the port-forwarding documents (gated by
  `ssm:SessionDocumentAccessCheck`).
- `cloudwatch/cloudwatch-agent-config.json` — ships `user2`'s journal output
  to CloudWatch. Only applies if you use the "broad" journald route from the
  notes (`usermod -aG systemd-journal user1`); the shipped unit file instead
  uses the more locked-down `StandardOutput=file:/var/log/runner2.log` option,
  in which case point the CloudWatch agent's `collect_list` at that file path
  instead of `journald://task-runner-user2`.

## Defense layers for user2 -> user1 isolation

1. **Network** — `IPAddressDeny=169.254.169.254` in user2's unit blocks the
   EC2 metadata IP, so user2 can't steal the instance's IAM credentials to
   query Parameter Store directly.
2. **Filesystem (DAC)** — `/etc/task_runner_1/config` is `chmod 640`/`750`,
   owned by `user1:user1`.
3. **Filesystem (systemd namespace)** — `TemporaryFileSystem=/etc/task_runner_1`
   in user2's unit masks that path with an empty overlay, so even a
   privilege-escalated user2 process sees an empty directory.
4. **Process/env** — triggering via `sudo systemctl start` routes through
   root's systemd, which builds user2's process from a clean environment
   rather than inheriting anything from user1's shell.
5. **Logs** — user2 is excluded from `adm`/`systemd-journal`/`wheel` on the
   golden image, and its output is redirected to a file only `user1`/root
   can read.

## Deploying

1. Bake the golden image: run `scripts/bootstrap-golden-image.sh` as root
   inside the Automation document's build step (or as a Command Document,
   per the notes' recommendation to keep image-update logic modular).
2. Point your Launch Template's AMI field at
   `resolve:ssm:/images/golden-ami-latest` and set both regions' Launch
   Templates identically.
3. Attach the `iam/automation-role-*` policies to the Automation Assume Role
   and run `automation/golden-image-pipeline.yml` (passing `SourceAmiId` and
   `SecurityGroupIds` for the temp build instance) to bake, replicate, and
   publish.
4. To launch a job, run `automation/launch-worker-with-params.yml` (or an
   `ec2:RunInstances` call against the Launch Template) with a `JobId`; the
   instance boots, `cloud-init` writes user1's config, and user1's service
   starts and triggers user2 when ready.
