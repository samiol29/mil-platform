# GitHub Actions workflows

## `ci.yml`

Runs on every push and pull request to `main`/`master`. Gate order: ruff
lint, ruff format check, mypy, pytest (`tests/unit` + `tests/providers`),
then `python -m compileall`. All five must pass for CI to succeed.

`tests/integration` and `tests/contract` are not run in this workflow — they
require live infrastructure (PostgreSQL, Redis, MinIO, a running API
process; see `make docker-up`) that is not provisioned on the runner. Run
them locally or from a deployment pipeline that provisions that
infrastructure first (`make docker-up && make migrate && make test-integration`).
