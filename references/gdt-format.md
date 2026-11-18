# GDT format reference

## Line anatomy

```
01380006302\r\n
^^^^^^^^^^^^^
│  │   │   └── CRLF (2 bytes)
│  │   └────── value "6302"
│  └────────── field id 8000 (Satzart)
└───────────── 013 = 13 bytes total
```

Calculation: `3` (length prefix) + `4` (field id) + `4` (value) + `2` (CRLF) = `13`.

The length counts **bytes**, not characters. With ISO-8859-1 `Müller` is 6 bytes; with UTF-8 it is 7.

## Records

- A record begins with field `8000`. Every later `8000` starts a new record.
- A file may contain one or many records.
- Field order is not arbitrary: `8000` must be first; the record-length field (`8100`, or `8004`) is usually last in GDT 2.1.
- Repeated field IDs are legal. Typical repeats are `6228` (finding text lines) and result fields.
- Some senders write files without a length prefix. Treat such files as non-conforming, but make parsers tolerant enough to read them for diagnostics.

## Version differences

| Aspect | GDT 2.1 | GDT 3.x (3.1, 3.5) |
|--------|---------|---------------------|
| Version field `9218` | `02.10` | `03.10`, `03.50` |
| Record length | `8100`, 5 digits | `8004` in some implementations; verify |
| Character set field `9206` | Present; `1`/`2`/`3` | Not part of 2.1-style handling; agree on encoding |
| Field length limits | Stricter, often 10/20/40 characters | More variable |
| Contact data | Limited | `3618` mobile, `3619` email in many profiles |
| Examination date `6200` | Often `TTMMJJJJ` | Often `JJJJMMTT` |

Version and date conventions are vendor- and profile-dependent. Parse dates defensively and validate them against the negotiated profile.

## Character sets

| `9206` | Meaning | Python codec |
|--------|---------|--------------|
| `1` | 7 bit | `ascii` |
| `2` | IBM CP437 (some systems CP850) | `cp437` / `cp850` |
| `3` | ISO-8859-1 (some systems CP1252) | `latin-1` / `cp1252` |

Rules:

- Prefer the `9206` value when it is present.
- When `9206` is absent, do not silently assume UTF-8. Agree on the codec with the counterpart; ISO-8859-1 is the traditional default.
- Never write a BOM.
- Validate that the chosen codec can encode every value before writing. Fail loudly instead of substituting characters.

## Validation checklist

1. File is non-empty and every line has at least 7 bytes before the line ending.
2. `LLL` is a three-digit decimal number and equals the actual line length in bytes including the line ending.
3. `FFFF` is four digits.
4. Each record starts with `8000`; its value is a four-digit Satzart.
5. `9218` is present and matches the expected version.
6. `9206`, if present, is `1`, `2`, or `3`.
7. Patient-related records (`6301`, `6302`, `6310`) contain `3000`, `3101`, and `3103`.
8. `6302` contains sender and receiver IDs (`8315`, `8316`).
9. `6310` contains at least one plausible result field (`6228`, `8402`, `8410`, `8420`).
10. `8100`/`8004`, if present, match the computed record length.
11. Values decode without replacement characters in the chosen codec.
12. No line exceeds 999 bytes.

The bundled validator reports errors for structural violations and warnings for semantic or version-dependent observations. Use `--strict` to promote warnings to errors in CI.

## Writing algorithm

1. Encode every value with the negotiated codec.
2. For each field, compute `length = 3 + 4 + len(value_bytes) + len(eol)`.
3. Reject a line if `length > 999`.
4. If a record-length field is used, first write a fixed-width placeholder, sum all line bytes, then replace the placeholder with the zero-padded total.
5. Join lines with `CRLF`.
6. Write to a temporary file in the target directory, flush and `fsync`, then `os.replace` to the final name.

Do not recompute an `8100`/`8004` value by character count. Do not write a record in multiple `write()` calls to the final path.

## Diagnostic patterns

| Symptom | Likely cause |
|---------|--------------|
| Parser reads garbage after an umlaut | Wrong codec, or character instead of byte lengths |
| First field rejected | UTF-8 BOM, or length prefix not updated after editing |
| Everything shifts by one field | Mixed `CRLF`/`LF`, or a line ending counted incorrectly |
| Device ignores the file | Wrong Satzart, missing `8315`/`8316`, or file written non-atomically |
| PVS rejects the result | Missing patient ID, stale `8100`, or unsupported encoding |
| Duplicate findings | Reader processed the same file twice; no processed/ archive |

## Minimal conforming examples

Request (`6302`), ISO-8859-1:

```
01380006302
014810000176
0188315GERAET-01
0158316PVS-01
014921803.50
0153000P-1042
0153101Müller
0153102Jürgen
017310314031978
01031101
017620020261117
01384021234
```

Result (`6310`), ISO-8859-1:

```
01380006310
014810000230
0158315PVS-01
0188316GERAET-01
014921803.50
0153000P-1042
0153101Müller
0153102Jürgen
017310314031978
01031101
017620020261117
0556228Unauffälliger Befund. Kontrolle in 12 Monaten.
0128420128
```

The exact `8100` values depend on the final record length and on whether the sender counts the `8100` line itself. Recompute them with the bundled tool and confirm the convention with the counterpart.
