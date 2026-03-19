# Quality Gates for `aureus-nautilus-node`

This runbook defines the minimum quality gate commands for local execution and CI.

## Local Execution (Windows PowerShell)

Run from:
- `d:\AIFramework\aureus\services\aureus-nautilus-node`

Commands:
1. `python -m pip install --upgrade pip`
2. `python -m pip install -r requirements.txt`
3. `python -m pytest -q`
4. `python -m ruff check .`
5. `python -m mypy --explicit-package-bases --ignore-missing-imports --disable-error-code no-redef execution_client.py data_client.py rollout_gates.py`

## CI Execution

Workflow:
- `.github/workflows/aureus-nautilus-node-quality.yml`

The CI job runs the same command sequence and fails immediately on any non-zero exit code.

## Pass / Fail Criteria

- **Pass** when all commands return exit code `0`.
- **Fail** if any of the following happens:
  - tests fail
  - lint violations are reported
  - mypy reports type errors
  - dependency installation fails

## Quick Troubleshooting

- `No module named mypy`:
  - Ensure step `python -m pip install -r requirements.txt` completed successfully.
- `No module named ruff`:
  - Reinstall dependencies and verify active Python environment.
- `pytest` import/runtime failures:
  - Confirm command is run from `services/aureus-nautilus-node` and dependent services/mocks are available.
