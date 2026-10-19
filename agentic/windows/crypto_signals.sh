#!/usr/bin/env bash
# Phase 1 job (agentic/README.md section 3): after the 00:00 UTC daily close, compute the signals of every asset whose
# bars Python can fetch on its own (Coinbase, yfinance, local CSV files; robinhood-feed assets need Claude's captures,
# so they are skipped, not counted as errors) and append everything it prints to private/agentic/cron.log (or
# $AGENTIC_STATE_DIR/cron.log).
#
# Windows: Task Scheduler runs this with Git Bash's bash.exe (set up by schedule_crypto_signals.sh install). To try it
# by hand, from Git Bash in the repo:  bash agentic/windows/crypto_signals.sh
# Interpreter: $AGENTIC_PYTHON if set, else the repo venv (.venv/Scripts/python.exe, or .venv/bin/python).
# Exit code: the signals command's (1 = a signal error for an enabled asset), 2 = cannot start.
set -u

src="${BASH_SOURCE[0]//\\//}"                  # Task Scheduler passes a Windows path: use forward slashes
case "$src" in
  */*) dir="${src%/*}" ;;
  *) dir=. ;;
esac
cd "$dir/../.." || { echo "crypto_signals.sh: cannot cd to the repo root from $dir" >&2; exit 2; }

if [ -n "${AGENTIC_PYTHON:-}" ]; then
  py="$AGENTIC_PYTHON"
elif [ -f .venv/Scripts/python.exe ]; then
  py=.venv/Scripts/python.exe
elif [ -x .venv/bin/python ]; then
  py=.venv/bin/python
else
  echo "crypto_signals.sh: no .venv in $PWD: create it first (agentic/README.md section 1)" >&2
  exit 2
fi

state="${AGENTIC_STATE_DIR:-private/agentic}"
mkdir -p "$state" || exit 2
log="$state/cron.log"
{
  printf '=== %(%Y-%m-%d %H:%M:%S %z)T signals --skip-feed robinhood\n' -1
  "$py" -m agentic signals --skip-feed robinhood
  rc=$?
  printf '=== exit %s\n' "$rc"
} >>"$log" 2>&1
if [ "$rc" -ne 0 ]; then
  echo "moneyline signals failed (exit $rc): see $log" >&2
fi
exit "$rc"
