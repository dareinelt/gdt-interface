# Regulatory and organizational context

This file is orientation, not legal advice. Confirm obligations with the manufacturer's regulatory affairs and data protection officers.

## Standard ownership and versions

- GDT is published and maintained by the **Qualitätsring Medizinische Software (QMS) e.V.**
- **GDT 3.5** is the current stable version. GDT **2.1** and **3.1** remain in active use.
- The QMS provides the 3.5 starter package (record description, annex, best practice), a test module, and sample files. Older versions are available to QMS members.
- Use of the specifications is subject to the QMS terms of use. They disclaim warranty and place responsibility for correct implementation and fitness for the environment on the implementer.
- Download the specification for the version actually negotiated with the counterpart. Do not implement from summaries alone.

## The xDT family

GDT shares its line syntax with other German xDT formats but not their field catalogs:

| Format | Scope | Maintainer / context |
|--------|-------|----------------------|
| GDT | Device and module data exchange with PVS | QMS |
| LDT | Laboratory data exchange | KBV |
| KVDT | Billing data exchange | KBV |

Do not reuse LDT or KVDT field semantics in a GDT implementation. The syntax is similar; the content is not.

## Privacy and data protection

GDT files routinely contain names, birth dates, insurance numbers, and findings. Treat them as health data under GDPR Article 9.

- Minimize data: transfer only the fields the examination requires.
- Restrict directory permissions to the integration service accounts.
- Do not copy files into tickets, chat, source control, or CI artifacts.
- Log field IDs and counts, never field values.
- Define retention for inbox, archive, quarantine, and dead-letter directories, and delete on schedule.
- Encrypt at rest when files leave the controlled environment.
- Document the legal basis and the data processing agreement with the PVS vendor where required.
- In Germany, § 203 StGB imposes additional confidentiality duties on certain professions and their service providers.

## Medical device regulation

- Integration software can be a medical device or an accessory depending on its function and claims. Displaying, interpreting, or converting findings for diagnostic decisions is different from transporting bytes.
- Clarify the classification before shipping. Do not claim CE marking or MDR compliance based on this skill.
- Keep the intended purpose, risk analysis, and validation evidence aligned with the actual functionality.
- Device manufacturers remain responsible for the correctness of the values they emit.

## Interface documentation

Maintain a short interface description per integration:

1. GDT version and reference to the QMS document.
2. Satzarten and field subset, including vendor-specific fields.
3. Character encoding and `9206` handling.
4. Directory paths, naming, and file lifecycle.
5. Test-mode convention.
6. Error handling and escalation contacts.
7. Version history of the interface.

Review it whenever the PVS version, device firmware, or field mapping changes.

## Test data

- Use synthetic patients only. Never copy production files into a repository or test suite.
- Keep a regression corpus of conforming and non-conforming files with expected validation results.
- Re-run the corpus after codec, parser, or version changes.
