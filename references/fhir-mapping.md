# GDT to FHIR R4 mapping

There is no official, normative mapping from GDT to FHIR. Treat every mapping as a local integration contract and validate it with the receiving system. FHIR R4 is used here because it is the common target for modern PVS and research interfaces.

## Resource mapping

| GDT source | FHIR target | Mapping notes |
|------------|-------------|---------------|
| `3000` | `Patient.identifier` | Use a local identifier system URI agreed with the receiver; keep leading zeros as a string |
| `3101`, `3102` | `Patient.name.family`, `Patient.name.given` | Do not split compound names automatically |
| `3103` | `Patient.birthDate` | Convert `TTMMJJJJ` to `YYYY-MM-DD`; reject invalid dates |
| `3110` | `Patient.gender` | `1` → `male`, `2` → `female`, else `unknown` |
| `3105` | `Patient.identifier` | Separate identifier system for the insurance number |
| `3106`, `3107` | `Patient.address.city`, `Patient.address.line` | Postal code vs. city depends on the profile |
| `3618`, `3619` | `Patient.telecom` | `phone` and `email` systems |
| `3622`, `3623` | `Observation` (body height/weight) | Requires LOINC codes and units; only map when the device profile defines them |
| `6302` | `ServiceRequest` | `code` from `8402` in a local code system; `authoredOn` from `6200` |
| `8316` (sender) | `ServiceRequest.requester` / `Provenance.agent` | Model as a `Practitioner` or `Device` depending on the counterpart |
| `8315` (receiver) | `ServiceRequest.performer` / `DiagnosticReport.performer` | Same decision as above |
| `6310` | `DiagnosticReport` | `effectiveDateTime` from `6200`; `conclusion` from `6228` |
| `6228` | `DiagnosticReport.conclusion`, `Observation.valueString`, or `Annotation` | Choose one representation per profile; do not duplicate the text everywhere |
| `8420` | `Observation.valueQuantity` | Unit and decimal separator must come from the device profile; never guess |
| `8402` | `Observation.code` / `ServiceRequest.code` | Local code system plus optional text |
| `9218` | `Provenance` / `Meta.tag` | Useful for audit and troubleshooting, not a clinical code |

## Bundle structure

```text
Bundle (type=transaction or collection)
├── Patient            (from 3000, 3101, 3102, 3103, 3110, ...)
├── ServiceRequest     (from 6302; optional when only results are imported)
├── DiagnosticReport   (from 6310)
│   ├── Observation    (from 8420, one per measured value)
│   └── Observation    (from 6228, optional narrative)
└── Provenance         (sender 8316, receiver 8315, GDT version 9218)
```

## Pseudocode

```python
patient = Patient(
    identifier=[Identifier(system=LOCAL_PATIENT_SYSTEM, value=record.get("3000"))],
    name=[HumanName(family=record.get("3101"), given=[record.get("3102")])],
    birthDate=parse_gdt_date(record.get("3103")),
    gender={"1": "male", "2": "female"}.get(record.get("3110"), "unknown"),
)

report = DiagnosticReport(
    status="final",
    subject=Reference(patient),
    effectiveDateTime=parse_gdt_date(record.get("6200")),
    conclusion="\n".join(record.get_all("6228")) or None,
    performer=[Reference(device_from(record.get("8316")))],
)

observations = [
    Observation(
        status="final",
        subject=Reference(patient),
        code=local_code(record.get("8402")),
        valueQuantity=Quantity(value=parse_number(value), unit=UNIT_FROM_PROFILE),
    )
    for value in record.get_all("8420")
]
```

## Pitfalls

- **Date formats**: `3103` and `6200` may use different conventions in the same file. Parse each field separately.
- **Decimal separator**: `128,5` and `128.5` both occur. Normalize explicitly; do not rely on the runtime locale.
- **Unknown units**: A bare number without a unit is not a valid `Quantity`. Leave the unit empty only if the target profile allows it; otherwise refuse the mapping.
- **Gender codes**: Any value other than `1` or `2` must not be coerced to male/female.
- **Duplicate findings**: Joining `6228` values with a newline is a local decision. Preserve the order and do not merge separate observations.
- **Identifiers**: Never invent an OID or a URL for a local identifier system. Agree on it with the receiver.
- **Provenance**: Keep sender, receiver, GDT version, and source file hash for audit.
- **Terminology**: `8402` is not a LOINC code. Map it to a local code system and add a human-readable text.

## Validation

- Validate the resulting resources against the target profile (for example ISiK or MII profiles) before sending.
- Test with synthetic data from `assets/` and with a real device profile in a test environment.
- Keep a mapping table under version control; review it when the device firmware or PVS version changes.
