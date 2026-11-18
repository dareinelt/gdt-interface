# gdt-interface

An agent skill for handling German **GDT** (Gerätedatenträger / Gerätedatentransfer) interface data — the xDT file format used to exchange patient data, examination requests, and findings between practice management systems (PVS) and medical devices.

## What it covers

- Byte-exact parsing and writing of `LLLFFFFvalue<CRLF>` records
- Satzarten `6300` / `6301` / `6302` / `6310` / `6311`
- Field IDs `8000`, `8100`/`8004`, `8315`, `8316`, `9206`, `9218`, `3000`, `3101`–`3110`, `6200`, `6228`, `8402`, `8410`, `8420`, …
- Character sets: 7-bit, IBM CP437, ISO-8859-1, CP1252, UTF-8
- Robust directory-based import/export (atomic writes, polling, locking, retries, quarantine)
- Mapping to FHIR R4
- Regulatory and privacy context (QMS, GDPR, MDR boundaries)

## Layout

| Path | Purpose |
|------|---------|
| `SKILL.md` | Main instructions and workflow |
| `scripts/gdt_tool.py` | Reader, validator, writer, sample generator (stdlib only) |
| `references/gdt-format.md` | Record structure, version differences, validation checklist |
| `references/field-catalog.md` | Common field IDs and mapping rules |
| `references/integration-patterns.md` | Import/export directories, locking, retries, monitoring |
| `references/fhir-mapping.md` | GDT → FHIR R4 mapping with pitfalls |
| `references/regulatory.md` | QMS terms, GDT vs. LDT/KVDT, privacy, MDR |
| `assets/*.gdt` | Synthetic ISO-8859-1 test files (6302 request, 6310 result) |

## Tool usage

Python 3.10+, no third-party dependencies.

```bash
python scripts/gdt_tool.py dump     incoming.gdt
python scripts/gdt_tool.py validate incoming.gdt --strict
python scripts/gdt_tool.py build    spec.json -o out.gdt --add-8100
python scripts/gdt_tool.py sample   -o assets
```

`validate` exits with code 1 on structural errors, so it can gate CI.

## Install as a skill

Copy or symlink the repository into your skills directory, e.g.:

```
~/.copilot/skills/gdt-interface
```

## Scope and caveats

GDT is maintained by the Qualitätsring Medizinische Software (QMS) e.V. GDT 3.5 is the current stable version; 2.1 and 3.1 remain widespread. This skill summarizes common practice — the QMS specification for the version you actually negotiate is authoritative, and vendor-specific field semantics must be confirmed with the manufacturer.

All sample files use synthetic data. Never commit real patient data.

## License

MIT — see [LICENSE](LICENSE).

Note that the GDT specification itself is published by the QMS e.V. under its
own terms of use; this repository only contains an independent implementation
and documentation summary.
