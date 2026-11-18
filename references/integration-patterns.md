# Integration patterns for GDT import and export

GDT is a file-drop interface, not a network protocol. Correctness depends on directory conventions and on never exposing partially written files.

## Role model

| Role | Writes | Reads |
|------|--------|-------|
| PVS / practice software | `6302` into the export directory | `6310` from the import directory |
| Device / module | `6310` into the result directory | `6302` from the export directory |

Names and paths are configured per installation. Common layouts are `C:\GDT\EXPORT` and `C:\GDT\IMPORT`, often per device. Never hard-code a customer path; read it from configuration and show it in diagnostics.

## Directory contract

Agree on all of the following in writing with the counterpart:

1. Absolute paths for request and result directories.
2. File extension (`.gdt` is common, `.txt` also occurs).
3. File name pattern, including whether the Satzart or patient ID is part of the name.
4. Whether a file contains one record or several.
5. Character encoding and whether `9206` is written.
6. Who deletes or archives a file after processing, and after how long.
7. Polling interval or event trigger.
8. Behaviour on invalid files (quarantine vs. delete vs. alert).
9. Test-mode convention and separate test directories.

Do not share one directory between unrelated devices. Use one directory pair per device or per integration.

## Reading files safely

A reader must never process a file that is still being written.

```text
loop every 1-5 s:
  for each candidate file in inbox:
    skip names starting with "." or ending in ".tmp", ".part", "~"
    skip size == 0
    if size or mtime changed since last poll: continue
    if file does not end with LF: continue
    open with shared read/write/delete access
    read all bytes
    parse and validate
    on success: hand to business logic, then archive/delete
    on permanent error: move to quarantine with a reason file
```

Additional rules:

- Require the size and modification time to be stable for at least one full poll interval. Antivirus scanners and network shares delay writes.
- Check that the last byte is `\n`; a truncated record often lacks it.
- On Windows, open with `FileShare.ReadWrite | FileShare.Delete` so the writer can rename or delete concurrently.
- Use a single consumer per directory. A lock file or an in-process mutex prevents double processing.
- Never trust the file name for routing; read `8000` from the content.

## Writing files safely

```python
handle, temp = tempfile.mkstemp(dir=target_dir, prefix=name + ".", suffix=".tmp")
with os.fdopen(handle, "wb") as stream:
    stream.write(payload)
    stream.flush()
    os.fsync(stream.fileno())
os.replace(temp, target_path)
```

- Build the entire payload in memory first. Never write field by field to the final path.
- Write the temporary file in the same directory as the target so the rename is atomic.
- Use a unique final name. Include a timestamp and a short random suffix when the counterpart permits it.
- Do not reuse a name that was already processed; the reader may ignore it as a duplicate.
- Keep the previous file only if the counterpart requires it; otherwise archive.

## Idempotency and duplicates

- Derive an idempotency key from `3000` + Satzart + `6200` + a vendor order ID if available.
- Record processed keys with a timestamp and a hash of the payload.
- Treat a repeated identical payload as a duplicate; log it and acknowledge instead of writing twice.
- Treat a repeated key with a different payload as a conflict; quarantine and surface it.
- Make the business operation idempotent where possible (upsert by patient + examination).

## Errors and retries

Classify failures:

| Class | Examples | Action |
|-------|----------|--------|
| Transient | File locked, share unavailable, disk full | Retry with backoff; keep the file |
| Permanent | Invalid length, unsupported Satzart, unknown patient | Quarantine; alert; do not loop |
| Semantic | Missing mandatory field, implausible date | Reject with a precise reason; alert |
| Business | Patient not found, order cancelled | Surface to the PVS/user; keep an audit record |

- Retry transient errors with exponential backoff and a maximum attempt count.
- Move exhausted files to a dead-letter directory; never delete evidence silently.
- Write a sidecar reason file (`<name>.error.txt`) with field IDs and error codes, never with patient values.
- Alert on the first permanent error; repeated invalid files usually indicate a configuration mismatch.

## Stale files and timeouts

- Quarantine files older than an agreed threshold (for example 15 minutes) that were never successfully processed.
- Expire quarantined files according to the retention policy; patient data must not accumulate indefinitely.
- Alert when no result arrives within the expected examination window.

## Monitoring

Track at minimum:

- Last successful import and export timestamp.
- Queue depth and age of the oldest unprocessed file.
- Counts by error class.
- Encoding actually detected per sender.
- Version (`9218`) and Satzart distribution.

Expose these as metrics or a status endpoint. A silent GDT directory is indistinguishable from a broken integration without them.

## Test mode

- Use dedicated test directories and synthetic patients.
- Never import test results into a production patient record.
- Mark synthetic files clearly in the file name and in the payload if the profile provides a test flag.
- Keep a small regression corpus of conforming and non-conforming files. The bundled `sample` command creates a starting point.

## Windows and network shares

- Prefer local directories. UNC shares add latency, locking differences, and reconnect failures.
- Grant write access only to the service account that needs it; do not use a world-writable share.
- Exclude GDT directories from on-access antivirus scanning where policy allows, or account for scan delays in the stability check.
- Keep paths short and free of umlauts; some legacy device software handles neither.
- Handle `ERROR_SHARING_VIOLATION` and `ERROR_LOCK_VIOLATION` as transient.

## Security and privacy

- Restrict directory ACLs to the integration service accounts.
- Do not copy GDT files to tickets, chat, or logs.
- Encrypt at rest where the storage leaves the controlled environment.
- Define retention and deletion for inbox, archive, quarantine, and dead-letter directories.
- Log field IDs and counts, not values.
