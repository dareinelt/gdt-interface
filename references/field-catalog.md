# Field catalog (common subset)

The QMS GDT specification and the device manufacturer's profile define the binding field set. This catalog covers fields that appear in most PVS-device integrations and is intended for triage, not as a substitute for the spec.

Legend: **stability** = how consistently the meaning is used across vendors.

## Administrative fields

| FK | Name | Notes | Stability |
|----|------|-------|-----------|
| `8000` | Satzart | First field of every record; four digits | High |
| `8004` | Satzlänge / record length | Used by some GDT 3.x implementations; verify width and scope | Medium |
| `8100` | Satzlänge / record length | GDT 2.1; five digits in common profiles | High |
| `8315` | GDT-ID Empfänger | Receiver identifier configured in both systems | High |
| `8316` | GDT-ID Sender | Sender identifier configured in both systems | High |
| `9206` | Zeichensatz | GDT 2.1 only: `1` = 7 bit, `2` = IBM CP437, `3` = ISO-8859-1 | High |
| `9218` | GDT-Version | `02.10`, `03.10`, `03.50`, … | High |

## Patient fields

| FK | Name | Notes | Stability |
|----|------|-------|-----------|
| `3000` | Patientennummer | Primary join key to the PVS record; length limits differ between 2.1 and 3.x | High |
| `3101` | Nachname | Includes name affixes in some PVS exports | High |
| `3102` | Vorname | | High |
| `3103` | Geburtsdatum | Usually `TTMMJJJJ`; validate, do not assume | High |
| `3104` | Titel | Academic title | Medium |
| `3105` | Versichertennummer | Health insurance number | High |
| `3106` | Wohnort | City / postal code depending on profile | Medium |
| `3107` | Straße | Street and number | Medium |
| `3108` | Versichertenstatus | `1` = member, `3` = family member, `5` = retired (common coding) | Medium |
| `3110` | Geschlecht | `1` = male, `2` = female; other values are vendor-specific | High |
| `3618` | Mobiltelefon | GDT 3.x profiles | Medium |
| `3619` | E-Mail | GDT 3.x profiles | Medium |
| `3622` | Körpergröße | Numeric, unit usually cm | Medium |
| `3623` | Körpergewicht | Numeric, unit usually kg | Medium |
| `3628` | Muttersprache | | Low |

## Examination and result fields

| FK | Name | Notes | Stability |
|----|------|-------|-----------|
| `6200` | Untersuchungsdatum | `TTMMJJJJ` in 2.1, often `JJJJMMTT` in 3.x; parse defensively | High |
| `6228` | Befund / finding text | May repeat; one line per field; preserve order | High |
| `8402` | Verfahren / procedure key | Vendor- or PVS-defined code; map via the device profile | Medium |
| `8410` | Testkennzeichen | Used as a test/flag field by several vendors; semantics are not uniform | Low |
| `8420` | Messwert | Numeric result; decimal separator and unit are vendor-dependent | Medium |

## Mapping rules

1. Join records on `3000` plus the examination context. Never join on name and birth date alone.
2. Convert dates only after identifying the source convention; reject impossible dates instead of coercing them.
3. Preserve every occurrence of `6228` and result fields. Do not collapse them into one value unless the target format requires it.
4. Keep unknown fields. Pass them through when round-tripping; drop them only with an explicit decision.
5. Refuse to invent units, reference ranges, or procedure codes. If the device profile does not define them, leave them empty and surface the gap.
6. Treat `8410` as a test flag only after the vendor confirms it. Do not use it as a production/quality marker otherwise.
7. Normalize decimal separators explicitly (`128,5` vs `128.5`); never rely on locale defaults.
8. Map `3110` conservatively: `1` → male, `2` → female, everything else → unknown until confirmed.

## Field-level validation

- Reject control characters other than the line terminator.
- Trim trailing spaces only when the profile allows it; leading zeros in identifiers are significant.
- Enforce the maximum length per field from the negotiated profile, not from this table.
- Keep field values as strings until the target schema requires typed values. Numeric parsing can destroy leading zeros and decimal formatting.
