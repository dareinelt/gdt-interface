---
name: gdt-interface
description: Parse, validate, and generate German GDT (Gerätedatenträger/Gerätedatentransfer) xDT interface files exchanged between practice management systems (PVS) and medical devices. Use when working with .gdt files, Satzarten 6300/6301/6302/6310/6311, field IDs such as 8000/8100/8315/8316/9218/3000/3101, character set 9206, directory-based import/export, test data, or GDT-to-FHIR mapping.
---

# GDT Interface (Gerätedatentransfer)

Handle German GDT exchange files: parse them byte-exactly, validate lengths and mandatory fields, generate conforming files, and integrate import/export directories into PVS or device software.

GDT is maintained by the Qualitätsring Medizinische Software (QMS) e.V. GDT 3.5 is the current stable version; GDT 2.1 and 3.1 remain widespread in the field. This skill summarizes common practice. The QMS specification for the negotiated version is authoritative.

## Operating rules

1. Treat the format as byte-oriented. Compute all lengths in bytes, never in characters.
2. Read and write raw bytes. Do not let editors, CSV/JSON round-trips, or git settings normalize line endings or re-encode content.
3. Preserve source files. Write results to new files and replace them atomically.
4. Treat every file as patient data. Never log field values; log field IDs, counts, and file names.
5. Do not guess vendor semantics for ambiguous result fields. Confirm them with the device manufacturer.

## File anatomy

A GDT file is a sequence of records ("Sätze"). Each record is a sequence of lines ("Felder"):

```
LLLFFFFvalue<CRLF>
```

| Part | Width | Meaning |
|------|-------|---------|
| `LLL` | 3 digits | Total line length in bytes, including `LLL` and the line ending |
| `FFFF` | 4 digits | Field identifier (Feldkennung) |
| `value` | variable | Field content in the negotiated character set |

- A record starts with field `8000` (Satzart). A file may contain several records.
- `8100` carries the record length in GDT 2.1. Some GDT 3.x implementations use `8004` instead; verify both against the spec.
- `9218` carries the version, for example `02.10`, `03.10`, or `03.50`.
- `9206` carries the character set in GDT 2.1: `1` = 7 bit, `2` = IBM CP437, `3` = ISO-8859-1. When present, it takes precedence over application settings.
- A line must not exceed 999 bytes including its prefix and line ending.

## Workflow

1. Determine the direction and Satzart. PVS-to-device is typically `6302` (examination request); device-to-PVS is typically `6310` (result).
2. Dump the file with the bundled tool to inspect fields and the detected encoding.
3. Validate the file. Fix length, encoding, or mandatory-field errors before mapping anything.
4. Map values using `references/field-catalog.md`. Confirm ambiguous fields with the vendor.
5. Generate output with the bundled tool so lengths and line endings are recalculated.
6. Wire the directories using `references/integration-patterns.md`.

## Bundled tool

Use `scripts/gdt_tool.py` (Python 3.10+, standard library only). It never modifies input files.

```bash
# Inspect
python scripts/gdt_tool.py dump incoming.gdt
python scripts/gdt_tool.py dump incoming.gdt --json

# Validate (exit code 1 on errors)
python scripts/gdt_tool.py validate incoming.gdt --strict

# Build from JSON (line endings and 8100 recalculated)
python scripts/gdt_tool.py build spec.json -o out.gdt --add-8100

# Create synthetic 6302/6310 test files
python scripts/gdt_tool.py sample -o assets
```

Spec format for `build`:

```json
{
  "encoding": "latin-1",
  "records": [
    {"fields": [["8000", "6302"], ["8100", ""], ["8315", "DEVICE-1"], ["9218", "03.50"], ["3000", "P-1"]]}
  ]
}
```

Field order is preserved. Use `""` for `8100`/`8004`; the tool recalculates the value. Supported encodings: `auto`, `latin-1`, `cp1252`, `cp437`, `utf-8`.

## Typical Satzarten

| Satzart | Direction | Purpose |
|---------|-----------|---------|
| `6300` | Device → PVS | Request master data |
| `6301` | PVS → device | Transmit master/patient data |
| `6302` | PVS → device | Request an examination, including patient data |
| `6310` | Device → PVS | Transmit examination results / findings |
| `6311` | Device → PVS | Show data of an examination |

Satzart semantics differ between spec versions and vendors. Verify against the QMS documentation for the installed version.

## Common failures

- **Length off by the line ending**: `LLL` includes `CRLF` (2 bytes) or `LF` (1 byte). Mixed line endings break parsers.
- **Character count instead of byte count**: `Müller` is 6 bytes in ISO-8859-1 but 7 in UTF-8.
- **Wrong codec**: ISO-8859-1, CP1252, CP437, and UTF-8 produce different bytes for umlauts. Prefer the declared `9206` value; otherwise agree on a codec explicitly.
- **BOM or re-encoded files**: A UTF-8 BOM or an editor rewrite changes the first line length.
- **Duplicate field IDs**: Fields such as `6228` (finding text) or `8420` (measured value) may repeat. Preserve every occurrence and its order.
- **Stale `8100`/`8004` value**: Recompute the record length after any change.
- **Partial files**: Readers may see a file while it is still being written. Require a stable size and use atomic rename.

## References

- `references/gdt-format.md` — detailed record structure, versions, encoding, validation checklist.
- `references/field-catalog.md` — commonly used field IDs and mapping notes.
- `references/integration-patterns.md` — robust import/export directories, locking, retries, monitoring.
- `references/fhir-mapping.md` — mapping to FHIR R4 with caveats.
- `references/regulatory.md` — QMS terms, GDT vs. LDT/KVDT, privacy and medical-device boundaries.
- `assets/sample-6302.gdt`, `assets/sample-6310.gdt` — synthetic ISO-8859-1 test files.
