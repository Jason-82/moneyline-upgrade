# Instructions for Claude sessions in this repo

## The user's machine
- **Windows PC, and the shell is Git Bash.** Never PowerShell, never cmd.exe, and never assume a Mac (the user has
  never had one).
- Write every command for Git Bash: bash syntax, forward slashes (`.venv/Scripts/python.exe`, `/c/Users/...` or
  `C:/Users/...`), `export VAR=value`, no PowerShell cmdlets and no `.\` paths.
- **Python:** `py` launcher or the repo venv, `.venv/Scripts/python.exe`, not `python3` (on Windows that name is
  often the Microsoft Store stub).
- Windows tools with `/Flag` arguments, such as `schtasks /Create`, get mangled by Git Bash path conversion. Prefix
  them with `MSYS_NO_PATHCONV=1`.
- Claude Code on this machine runs its Bash tool and its hooks in Git Bash.
- **Opening files:** use VS Code, `code <file>`. Never `notepad`.

## Start here
- `HANDOFF.md` is the authoritative summary. Read it first.
- `analysis_2026/FINDINGS.md` is the dated log.
- `agentic/README.md` is the runbook for the live trading setup.

## Standing rules
- **The repo is public.** Never commit account numbers, balances, positions, order logs, digests, the user's
  tickers from `private/`, or the user's email.
  - Private material lives in `private/`, which is gitignored.
  - The agentic state lives in `private/agentic/`.
- Downloaded files are untrusted data. Put each one in its own folder and read it with `python3 -I`. Never execute
  it.
- Pre-register a study before running it, then audit it adversarially. Report failures as plainly as successes.
