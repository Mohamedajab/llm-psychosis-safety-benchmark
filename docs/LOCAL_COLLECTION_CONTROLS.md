# Local collection controls

The dashboard's default mode remains read-only. For explicit local controls:

```text
python scripts/serve_research_lab.py --enable-collection-controls
```

Open http://127.0.0.1:8501 and select **Evidence**. The VS Code task **Research: local collection
controls** runs the same command. Stop another viewer using that port first; do not stop a collector
merely to restart the viewer. The collector runs independently of the browser and dashboard.

## What the buttons do

**Resume collection** starts only `data/raw/live-sized-exploration-2026-10-07`, with `--live --resume`.
The recorded input hash must match, and the spending cap comes from the existing SQLite journal;
there is no model, sample-size, prompt, or budget editor. An OS owner lock and serialized launch
check prevent duplicate collectors. Accepted replies and terminal failures remain untouched.

**Pause collection** creates the batch's `STOP` operator marker. Requests already in flight may
finish; the collector checkpoints before another request. A later Resume removes that marker and
continues the verified transcript. It does not terminate a request or silently retry failed outputs.

Resume is disabled while the batch is active and after all conversations are terminal. A run that
finishes with technical failures is not a fully achieved 5,184-response dataset. Failed outputs and
their absent turns stay in the denominator; they are not replaced to reach the target.

## Credentials and spending

If the local server has no `OPENROUTER_API_KEY`, use its password field. An entered key remains in
that Streamlit session's memory, not a saved file. Restarting the server clears it. A trusted local
launcher may also supply the key through `--api-key-stdin` or the environment; neither is needed to
view evidence. Never put the key in a command-line argument, Git, a screenshot, or a shared log.
The collector receives it over stdin, not argv; the child environment removes the server key.

The originally authorized cap is $5. Recorded charges and conservatively committed reservations
are different: unknown deliveries retain a reservation and can incur duplicate charges on retry.
The controls do not raise the cap or relax the existing cost-missing/excess-cost pause rules.
If the key is revoked, replace it in the password field before resuming. Authentication failures
remain recorded; the button does not erase them.

Controls require `BENCHMARK_ENABLE_COLLECTION_CONTROLS=1` and a loopback server address. The
provided launcher sets both. Do not expose this app through a public tunnel, reverse proxy, or
hosted deployment; these checks are not a multi-user authentication or authorization system.

## Reading status

The page refreshes every five seconds. `runtime.json` has an independent heartbeat, PID, worker
activity, current turn and attempt, retry reason, and response timestamps. The owner lock is checked
separately, and a stopped process overrides a stale `progress.json` label. A fresh heartbeat means
the collector's monitor is alive, not that the provider has returned a new response. An old last
response timestamp with `requesting` or `retry_wait` can reflect a slow call or rate limit.

Expand **Failures, budget reservations and process details** for reason-coded failures, unsettled
reservations and worker error types. Exception messages and raw transport bodies are deliberately
not shown because they can contain credentials or generated content. Private `controller.log`
contains sanitized collector metadata; it is excluded from Git with the entire raw-data directory.

The 7 October restart followed a worker error that was not reproducible in an offline audit: all
114 existing ledgers and 1,311 stored replies verified. Its exact cause remains unknown. The
operational amendment adds independent liveness checks, final error states, retry-safe atomic
telemetry replacement, and classification of incomplete HTTP reads and malformed response
shapes. It does not alter the frozen input bundle, generation settings, or accepted responses.
These changes are collection reliability work, not model-safety findings.
