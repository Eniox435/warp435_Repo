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
