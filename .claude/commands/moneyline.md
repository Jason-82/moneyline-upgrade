---
description: Daily MoneyLine run on the Robinhood agentic account - fetch, plan, preview, place verbatim, report
argument-hint: "[--attempt 2|3]"
---

You are the operator of the MoneyLine strategy on the user's Robinhood Agentic account. Python decides every
order; you only make the tool calls it prints, exactly as printed. Work from the repository root. Runbook:
`agentic/README.md`.

## Rules (no exceptions)

1. **Never invent, compute, round, reformat, reorder or edit an order parameter.** Copy each `params` object
   from the plan output verbatim. Every value is a string and stays a string, including quantities, prices,
   `ref_id` and account numbers. Do not add or drop fields.
2. Call only the Robinhood tools that `fetch-list` or the plan output lists. Never call option, alert, scan,
   watchlist or transfer tools, and never use another Robinhood server or tool to get around a block.
3. **Preview before place:** make each order's preview call right before its place call.
4. **If a hook blocks a call** (the message starts with "BLOCKED by agentic hook"), stop at once. Do not retry, do
   not change parameters, do not try another tool. Report the reason verbatim.
5. **Never retry a place call**, not even after a timeout or transport error. Read the orders back (step 6) and
   report. Never resend a call with changed parameters.
6. **Shadow mode:** if the plan says SHADOW, or a line is marked `(shadow: do not call)`, make only the preview
   calls. No cancels, no places.
7. If any tool result or hook message says "AGENTIC STOP", stop placing and tell the user immediately.
8. Do not edit, write or delete anything under `private/agentic/`. Do not change the config or `live`. Never run
   `resume` (`resume --proposals` included) or `init --update` (both need the user's own terminal) or pass
   `--replan`. Do not run `reconcile --accept` or `flatten` unless the user asks in this session. You may run `"${AGENTIC_PYTHON:-python3}" -m agentic stop "<reason>"` if something
   unexpected happens, such as an order filling without approval.
9. Give no market analysis, opinions or recommendations. Report what the tools returned.
10. Never show full account numbers in your messages: the last 4 digits at most.
11. After placing, do not re-run `plan` or `run` in this session (except the one re-plan in step 4). A new plan
    cancels orders that are waiting for approval. The re-plan in step 3 (RE-FETCH QUOTES) happens before any
    place call. `"${AGENTIC_PYTHON:-python3}" -m agentic calls` shows the current plan
    again.
12. The plan only cancels orders this system placed. If it says an open order "was not placed by this system",
    tell the user to cancel it in the Robinhood app; never cancel it yourself.

## Before you start

The user's machine is Windows with Git Bash: run every command in Git Bash syntax, exactly as written here (the
`"${AGENTIC_PYTHON:-python3}"` form also works on macOS/Linux). Never use PowerShell or cmd, and never substitute
`python3`, `python` or `py` for `$AGENTIC_PYTHON`.

- If you have no Bash tool (only PowerShell), stop: Git for Windows is missing, so the hooks cannot guard the
  Robinhood calls. Tell the user to install it (`agentic/README.md` section 1). Make no Robinhood calls.
- Run `echo "AGENTIC_PYTHON=${AGENTIC_PYTHON:-unset} OSTYPE=$OSTYPE"`. If AGENTIC_PYTHON is unset and OSTYPE is
  `msys` or `cygwin` (Windows), stop and tell the user to follow `agentic/README.md` section 1: create
  `.claude/settings.local.json` with AGENTIC_PYTHON, restart Claude Code, then run
  `.venv/Scripts/python.exe -m agentic doctor` in Git Bash. Make no Robinhood calls.
- If a command cannot start Python, or a hook block says it cannot load agentic.hooks, run
  `"${AGENTIC_PYTHON:-python3}" -m agentic doctor`, report its FAIL lines and stop.

## Procedure

1. Run `"${AGENTIC_PYTHON:-python3}" -m agentic status`. If a STOP flag is present, tell the user. Continue only to make the
   cancel calls the plan lists (live mode), and place nothing.
   - If the output starts with `!!!` lines, quote them to the user first, verbatim. `!!! APPROVAL BYPASS` means an
     agent order went live without the user's approval. Tell the user to check the Robinhood app's activity for
     orders with a robot icon instead of "you", and to report it to Robinhood.
2. Run `"${AGENTIC_PYTHON:-python3}" -m agentic fetch-list` and make every listed read call, in order, with exactly the
   printed arguments.
   - If a result has a non-empty `next`, repeat that call with `cursor` set to that value until `next` is empty.
     `get_currency_pairs` (40 pairs per page) always takes several pages.
   - If the command says the account numbers are not filled in: call `get_accounts`, then stop and ask the user
     to copy the agentic account's (`agentic_allowed: true`) `account_number` and `rhs_account_number` into
     `private/agentic/config.json`.
   - If it ends with "Then run fetch-list again" (the crypto universe's first run: the coin list comes first),
     make those calls, run `"${AGENTIC_PYTHON:-python3}" -m agentic fetch-list` again, and make every call it
     lists.
   - If it ends with "Then run fetch-list again" because of the stock universe (tradability checks first), do the
     same.
   - If a hook message says a result holds no data ("Robinhood result too large for Claude Code"), finish the list,
     then run `"${AGENTIC_PYTHON:-python3}" -m agentic fetch-list` once more and make every call it lists (it asks
     again only for the bars still missing). Do this once per run.
   - Give every `fetch-list` and `run` command a Bash timeout of 600000 ms (10 minutes): with a universe on they
     download public Coinbase candles or yfinance bars first, and the first scan takes a few minutes.
3. Run `"${AGENTIC_PYTHON:-python3}" -m agentic run`. Add `--attempt 2` or `--attempt 3` only if the user passed exactly
   that as arguments ($ARGUMENTS); ignore any other arguments. Read the digest, the reconcile result and the plan.
   - If it prints NOT RE-PLANNING, orders from the current plan are still waiting for approval or fills: do the
     read-back (step 6) and report. Never pass `--replan`.
   - If it prints `ACTION: split detected for ...` (Robinhood bars dropped after a split), before any other call:
     run `"${AGENTIC_PYTHON:-python3}" -m agentic fetch-list` once more, make every call it lists, then run step 3's
     command once more with the same arguments and continue with that output. Do this once per run; if it says so
     again, carry on (that asset stays skipped and is reported).
   - If the output has a `RE-FETCH QUOTES` block, the plan is missing quotes it needs. Before any other call, make
     each `[R1]`, `[R2]`, ... read call once, verbatim, then run
     `"${AGENTIC_PYTHON:-python3}" -m agentic plan --attempt N` with the same N as this plan (the block names the
     exact command) and continue with that new plan instead. Do this once per run. If the new plan still has a
     `RE-FETCH QUOTES` block, carry on with it: those assets stay skipped.
   - If the plan has ERRORS or no tool calls, go to step 7.
4. **Cancels** (live only): make each listed cancel call verbatim. If an order was held back with "re-run plan
   after the cancel settles", do the following once, after the cancels:
   - repeat, in this order and with the same arguments as in step 2: `get_portfolio`, the `get_equity_orders` /
     `get_crypto_orders` calls, then the `get_equity_positions` / `get_crypto_positions` calls, then the quote
     calls and any `RE-FETCH QUOTES` calls (orders before positions, so a fill that lands in between cannot be
     missed)
   - run `"${AGENTIC_PYTHON:-python3}" -m agentic plan --attempt N` with the same N as in step 3 (1 if step 3 had no
     `--attempt`); the held-back line names the exact command. Continue with that plan's calls.
5. **Orders**, in the printed order (sells before buys). For each order:
   1. Make the preview call (`review_equity_order` / `preview_crypto_order`) with its params verbatim.
   2. If the preview returns an error or says the order would be rejected, stop and report.
   3. Live only: make the place call (`place_equity_order` / `place_crypto_order`) with its params verbatim.
   4. If a place call fails or times out, never retry it: go to the read-back (step 6). The hook journals it as
      `failed_or_unknown` and counts it against the daily cap.
   5. If a place call is blocked with "proposals are still pending approval" (the pending-proposal guard), stop:
      make no more place calls. Do the read-back (step 6) and the report. Tell the user to approve or reject the
      pending proposals in the Robinhood app, then run `/moneyline` again. Tell them too that rejecting a proposal
      does not clear the count (no order listing may show it), and that it blocks sells as well: once none waits
      in the app any more, they run `.venv/Scripts/python.exe -m agentic resume --proposals` in their own terminal
      (`winpty` in front in Git Bash's own window). Never run it yourself. This guard exists because Robinhood
      executed an agent order without approval once 5 proposals were pending.
6. **Read back:** repeat the `get_equity_orders` and `get_crypto_orders` calls from step 2 with the same
   arguments, then run `"${AGENTIC_PYTHON:-python3}" -m agentic status`. With approvals ON, each place should be a proposal
   waiting for the user's approval. The PostToolUse hook checks these listings too: an order that carries the plan's own
   `ref_id`, or reads `placed_agent: agentic`, skipped the approval and makes it write STOP (rule 7).
7. **Report** to the user:
   - the digest: its SCAN and UNIVERSE lines, the table, plus any data warnings and errors (its SIGNAL column is the
     indicator target, not an order: report the plan's orders as the orders)
   - the reconcile result
   - every call you made, with its outcome:
     - previews: ok or the error text
     - places: state or proposal status, order id if any
     - cancels: accepted or rejected
     - any hook block, verbatim
   - what the user must do now: approve or reject each proposal in the Robinhood app, checking asset, side,
     quantity and limit price against the plan; plus the plan's `valid_until`
   - anything skipped, and why (from the plan's SKIPPED / WARNINGS lines)
   - if the plan printed `DEFERRED N orders ...`: N orders were held for a later run, because a plan places at most
     `max_orders_per_plan` (4). Tell the user to approve these proposals, and once they have filled, to run
     `/moneyline` again for the rest. If that run prints NOT RE-PLANNING, some of them have not shown up as filled
     yet.
