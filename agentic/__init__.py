"""MoneyLine execution for the Robinhood Agentic account (design: AGENTIC_TRADING_PLAN.md, spec: agentic/SPEC.md).

Deterministic Python decides; Claude only operates the Robinhood MCP tools. Runtime state (config with account
numbers, raw tool captures, signals, plans, journal) lives in private/agentic/, which is gitignored: never commit it.
"""
