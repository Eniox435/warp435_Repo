# cloud-agent
A starter repository for your new cloud agent project.

## What is included
- `src/` for application code
- `config/routing.example.yaml` for model-routing defaults
- `.env.example` for API key placeholders

## Quick start
1. Copy env vars:
   - `cp .env.example .env`
2. Fill in the keys you want to use.
3. Run a task through the routing/execution slice:
   - `python3 src/main.py --task summary --prompt "Summarize this PR"`
   - `python3 src/main.py --task unknown --prompt "Deep review" --quality-priority 5`
4. Run smoke tests:
   - `python3 -m unittest discover -s tests`

## Suggested routing policy
- Default: local model lane for low-cost tasks
- Escalation: provider-specific models via BYOK
- Heavy tasks: high-capability model only when needed

## Current vertical slice
- `src/routing.py` loads config and selects lane by `use_case` plus priority policy.
- `src/executor.py` executes task in selected lane (local/BYOK/premium) with BYOK fallback and retry/timeout policy.
- `src/provider_adapters.py` contains provider adapters for OpenAI, Anthropic, and Google, each returning a normalized response shape.
- `src/main.py` provides CLI entrypoint with structured JSON output.
- `config/routing.json` is the default runtime config.

## Operating model (enforced)
### Branch and PR governance
- All changes flow through pull requests to `main` (no direct push workflow).
- `main` requires the `lint-and-test` status check and requires branches to be up to date before merge.
- At least 1 approving review is required before merge.
- Conversation resolution is required before merge.
- Admin enforcement is enabled.
- Force pushes and branch deletion on `main` are disabled.

### Merge policy
- Squash merge is the only enabled merge method.
- Merge commits and rebase merges are disabled.
- Feature branches are auto-deleted after merge.

### Daily delivery loop
1. Open a feature branch and implement scoped changes.
2. Run local checks (`compileall` and unit tests) before pushing.
3. Open a PR and wait for `lint-and-test` to pass.
4. Address review comments and resolve all conversations.
5. Merge with squash once review and CI gates are green.

### Recovery path for failing checks
1. Inspect the failing workflow run and identify whether the failure is lint, compile, or tests.
2. Reproduce locally with the same commands used in CI.
3. Push a focused fix commit to the PR branch.
4. Re-run checks and only merge after all required checks pass.
