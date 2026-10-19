#!/usr/bin/env bash
# Register the phase 1 crypto-signals job with Windows Task Scheduler, from Git Bash (agentic/README.md section 3).
#
#   bash agentic/windows/schedule_crypto_signals.sh install [--time HH:MM] [--name NAME] [--dry-run]
#   bash agentic/windows/schedule_crypto_signals.sh status  [--name NAME] [--dry-run]
#   bash agentic/windows/schedule_crypto_signals.sh remove  [--name NAME] [--dry-run]
#
# install: a daily task (default name moneyline-crypto-signals) that runs crypto_signals.sh with Git Bash's bash.exe.
#   Without --time it runs at the local clock time of 00:15 UTC under the PC time zone's daylight-saving offset, read
#   with the venv's Python (agentic.calendar.job_time): US Central 19:15, US Eastern 20:15, US Pacific 17:15, UTC
#   00:15. That is 00:15 UTC in summer and 01:15 UTC in winter, after the 00:00 UTC crypto close both times. --time
#   HH:MM (local) overrides it. Re-running install replaces the task.
# status: the task's settings and last result, then the end of cron.log. remove: deletes the task.
# --dry-run prints the schtasks command instead of running it.
# Git Bash would turn schtasks' /Flags into paths, so every call runs with MSYS_NO_PATHCONV=1.
set -u

usage() {
  echo "usage: bash agentic/windows/schedule_crypto_signals.sh install|status|remove [--time HH:MM] [--name NAME] [--dry-run]" >&2
  exit 2
}

[ $# -ge 1 ] || usage
action="$1"
shift
name=moneyline-crypto-signals
at=
dry=0
while [ $# -gt 0 ]; do
  case "$1" in
    --time) [ $# -ge 2 ] || usage; at="$2"; shift 2 ;;
    --name) [ $# -ge 2 ] || usage; name="$2"; shift 2 ;;
    --dry-run) dry=1; shift ;;
    *) usage ;;
  esac
done
if [ -n "$at" ] && ! [[ "$at" =~ ^([01][0-9]|2[0-3]):[0-5][0-9]$ ]]; then
  echo "--time must be HH:MM (24-hour), got '$at'" >&2
  exit 2
fi
if ! [[ "$name" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "--name may use letters, digits, '.', '_' and '-' only" >&2
  exit 2
fi

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
job="$here/crypto_signals.sh"
repo="$(cd "$here/../.." && pwd)"

venv_python() {                                # as crypto_signals.sh: $AGENTIC_PYTHON, else the repo venv
  if [ -n "${AGENTIC_PYTHON:-}" ]; then
    printf '%s\n' "$AGENTIC_PYTHON"
  elif [ -f "$repo/.venv/Scripts/python.exe" ]; then
    printf '%s\n' "$repo/.venv/Scripts/python.exe"
  elif [ -x "$repo/.venv/bin/python" ]; then
    printf '%s\n' "$repo/.venv/bin/python"
  else
    return 1
  fi
}

auto_time() {                                  # two lines: HH:MM, then why (agentic.calendar.job_time)
  local py
  py="$(venv_python)" || { echo "no .venv in $repo to read the PC's time zone: pass --time HH:MM" >&2; return 2; }
  (
    case "${OSTYPE:-}" in
      msys*|cygwin*) unset TZ ;;               # Windows Python: the system time zone, not an MSYS TZ value
    esac
    "$py" -I -c 'import sys; sys.path.insert(0, sys.argv[1]); from agentic.calendar import job_time; t, why = job_time(); print(t); print(why)' "$repo" 2>/dev/null
  ) || { echo "cannot run $py to read the PC's time zone: pass --time HH:MM" >&2; return 2; }
}

win_path() {                                   # the Windows form of a path, for Task Scheduler
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$1"
  else
    printf '%s\n' "$1"
  fi
}

git_bash() {                                   # Git Bash's bash.exe, as a Windows path
  if [ -n "${CLAUDE_CODE_GIT_BASH_PATH:-}" ]; then
    win_path "$CLAUDE_CODE_GIT_BASH_PATH"
    return
  fi
  if command -v cygpath >/dev/null 2>&1; then
    local root
    root="$(cygpath -m /)"                     # e.g. C:/Program Files/Git/
    root="${root%/}"
    if [ -f "$root/bin/bash.exe" ]; then
      cygpath -w "$root/bin/bash.exe"
    else
      cygpath -w "$(command -v bash)"
    fi
    return
  fi
  printf '%s\n' 'C:\Program Files\Git\bin\bash.exe'
}

show() {                                       # print a command so it can be pasted into Git Bash
  local out="" a
  for a in "$@"; do
    if [[ "$a" =~ ^[A-Za-z0-9_/.:=,+-]+$ ]]; then
      out+=" $a"
    else
      out+=" '${a//\'/\'\\\'\'}'"
    fi
  done
  printf '%s\n' "${out# }"
}

run_schtasks() {
  if [ "$dry" = 1 ]; then
    show MSYS_NO_PATHCONV=1 schtasks "$@"
    return 0
  fi
  if ! command -v schtasks >/dev/null 2>&1; then
    echo "schtasks not found: run this in Git Bash on Windows (macOS/Linux: use cron, README section 3)" >&2
    return 2
  fi
  MSYS_NO_PATHCONV=1 schtasks "$@"
}

case "$action" in
  install)
    [ -f "$job" ] || { echo "missing $job" >&2; exit 2; }
    if [ -z "$at" ]; then
      auto="$(auto_time)" || exit 2
      at="$(printf '%s\n' "$auto" | sed -n 1p)"
      why="$(printf '%s\n' "$auto" | sed -n 2p)"
      if ! [[ "$at" =~ ^([01][0-9]|2[0-3]):[0-5][0-9]$ ]]; then
        echo "could not read a time from the PC's time zone (got '$at'): pass --time HH:MM" >&2
        exit 2
      fi
      msg="time $at chosen from this PC's time zone: $why. --time HH:MM overrides it."
    else
      msg="time $at local (--time)"
    fi
    if [ "$dry" = 1 ]; then
      printf '# %s\n' "$msg"
    else
      echo "$msg"
    fi
    bash_exe="$(git_bash)"
    job_w="$(win_path "$job")"
    # -l: a login shell sets up Git Bash's PATH; the job finds the repo from its own location.
    tr="\"$bash_exe\" -l \"$job_w\""
    if [ "${#tr}" -gt 261 ]; then
      echo "the task command is ${#tr} characters; schtasks allows 261. Move the repo to a shorter path." >&2
      exit 2
    fi
    run_schtasks /Create /F /SC DAILY /ST "$at" /TN "$name" /TR "$tr" || exit $?
    if [ "$dry" = 0 ]; then
      echo "Task '$name' runs daily at $at local time: $tr"
      echo "Output goes to private/agentic/cron.log. Check it with: bash agentic/windows/schedule_crypto_signals.sh status"
    fi
    ;;
  status)
    run_schtasks /Query /TN "$name" /V /FO LIST || exit $?
    if [ "$dry" = 0 ]; then
      log="$here/../../${AGENTIC_STATE_DIR:-private/agentic}/cron.log"
      case "${AGENTIC_STATE_DIR:-}" in
        /*|[A-Za-z]:*) log="$AGENTIC_STATE_DIR/cron.log" ;;
      esac
      if [ -f "$log" ]; then
        echo "--- last lines of cron.log"
        tail -n 15 "$log"
      else
        echo "--- no cron.log yet"
      fi
    fi
    ;;
  remove)
    run_schtasks /Delete /TN "$name" /F || exit $?
    ;;
  *)
    usage
    ;;
esac
