#!/usr/bin/env python3
"""GDT/xDT reader, validator and writer.

Reads and writes German GDT exchange files (Gerätedatentransfer /
Gerätedatenträger). Standard library only.

Format: every line is  LLL  +  FFFF  +  value  +  CRLF
  LLL  = three decimal digits, total byte length including LLL and CRLF
  FFFF = four decimal digits, field id (Feldkennung)
A record ("Satz") starts with field 8000 (Satzart).

Usage:
  python gdt_tool.py dump     FILE [--encoding auto|latin-1|cp1252|cp437|utf-8] [--json]
  python gdt_tool.py validate FILE [--encoding ...] [--strict] [--json]
  python gdt_tool.py build    SPEC.json -o OUT.gdt [--add-8100] [--encoding ...]
  python gdt_tool.py sample   -o DIR
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

MAX_LINE_BYTES = 999
CRLF = b"\r\n"

FIELD_LABELS = {
    "8000": "Satzart",
    "8004": "Satzlänge (GDT 3.x, implementationsabhängig)",
    "8100": "Satzlänge (GDT 2.1)",
    "8315": "GDT-ID Empfänger",
    "8316": "GDT-ID Sender",
    "9206": "Zeichensatz (nur GDT 2.1)",
    "9218": "GDT-Versionsnummer",
    "3000": "Patientennummer",
    "3101": "Nachname",
    "3102": "Vorname",
    "3103": "Geburtsdatum",
    "3105": "Versichertennummer",
    "3106": "Wohnort",
    "3107": "Straße",
    "3108": "Versichertenstatus",
    "3110": "Geschlecht",
    "3618": "Mobiltelefon",
    "3619": "E-Mail",
    "3622": "Körpergröße",
    "3623": "Körpergewicht",
    "3628": "Muttersprache",
    "6200": "Untersuchungsdatum",
    "6228": "Befund (Langtext)",
    "8402": "Verfahren / Kennfeld",
    "8410": "Testkennzeichen (häufig, herstellerspezifisch)",
    "8420": "Messwert",
}

PATIENT_RECORD_TYPES = {"6301", "6302", "6310"}


@dataclass
class Field:
    fk: str
    value: str
    raw_len: int | None = None
    line_no: int = 0


@dataclass
class Record:
    fields: list[Field] = field(default_factory=list)
    line_no: int = 0

    def get(self, fk: str, default: str = "") -> str:
        for item in self.fields:
            if item.fk == fk:
                return item.value
        return default

    def get_all(self, fk: str) -> list[str]:
        return [item.value for item in self.fields if item.fk == fk]

    @property
    def satzart(self) -> str:
        return self.get("8000")


@dataclass
class Issue:
    severity: str
    message: str
    line_no: int | None = None
    fk: str | None = None

    def as_dict(self) -> dict:
        return {
            "severity": self.severity,
            "message": self.message,
            "line": self.line_no,
            "field": self.fk,
        }


def decode_bytes(raw: bytes, encoding: str) -> tuple[str, bool]:
    try:
        return raw.decode(encoding), True
    except UnicodeDecodeError:
        return raw.decode(encoding, errors="replace"), False


def detect_encoding(fields: list[tuple[bytes, bytes]], requested: str) -> tuple[str, list[str]]:
    """Return (encoding, notes). `requested` is auto or an explicit codec."""
    notes: list[str] = []
    if requested != "auto":
        return requested, notes

    for fk, value in fields:
        if fk == b"9206":
            code = value.strip().decode("ascii", "ignore")
            mapping = {"1": "ascii", "2": "cp437", "3": "latin-1"}
            if code in mapping:
                notes.append(f"Zeichensatz aus Feld 9206: {code} -> {mapping[code]}")
                return mapping[code], notes
            notes.append(f"Unbekannter Wert in Feld 9206: {code!r}; Fallback latin-1")

    non_ascii = any(byte > 0x7F for _, value in fields for byte in value)
    if non_ascii:
        try:
            for _, value in fields:
                value.decode("utf-8")
        except UnicodeDecodeError:
            pass
        else:
            notes.append("Kein 9206, Bytes sind gültiges UTF-8 -> utf-8 (Heuristik)")
            return "utf-8", notes

    return "latin-1", notes


def split_raw_lines(data: bytes):
    """Yield (content_bytes, eol_bytes, line_no) without the EOL in content."""
    pos = 0
    line_no = 0
    while pos < len(data):
        newline = data.find(b"\n", pos)
        if newline == -1:
            content = data[pos:]
            eol = b""
            pos = len(data)
        else:
            if newline > pos and data[newline - 1:newline] == b"\r":
                content = data[pos:newline - 1]
                eol = CRLF
            else:
                content = data[pos:newline]
                eol = b"\n"
            pos = newline + 1
        line_no += 1
        if not content and not eol:
            continue
        yield content, eol, line_no


def parse_bytes(data: bytes, requested_encoding: str = "auto", lenient: bool = False):
    raw_fields: list[tuple[bytes, bytes, int, int]] = []
    issues: list[Issue] = []

    if not data:
        issues.append(Issue("error", "Datei ist leer"))
        return [], issues, "latin-1"

    for content, eol, line_no in split_raw_lines(data):
        actual_len = len(content) + len(eol)
        if len(content) < 7 or not content[:3].isdigit():
            issues.append(Issue("error", "Kein 3-stelliges Längenpräfix", line_no))
            declared = None
        else:
            declared = int(content[:3])
            if declared != actual_len:
                severity = "warning" if lenient else "error"
                issues.append(Issue(
                    severity,
                    f"Längenangabe {declared:03d} passt nicht zur tatsächlichen Zeilenlänge {actual_len:03d}",
                    line_no,
                ))
        fk_bytes = content[3:7]
        if len(fk_bytes) != 4 or not fk_bytes.isdigit():
            issues.append(Issue("error", f"Ungültige Feldkennung {fk_bytes!r}", line_no))
            continue
        raw_fields.append((fk_bytes, content[7:], line_no, actual_len))

    if not raw_fields:
        issues.append(Issue("error", "Keine auswertbaren GDT-Zeilen gefunden"))
        return [], issues, "latin-1"

    encoding, notes = detect_encoding([(fk, value) for fk, value, _, _ in raw_fields], requested_encoding)
    for note in notes:
        issues.append(Issue("info", note))

    records: list[Record] = []
    current: Record | None = None
    for fk_bytes, value_bytes, line_no, raw_len in raw_fields:
        fk = fk_bytes.decode("ascii")
        value, ok = decode_bytes(value_bytes, encoding)
        if not ok:
            issues.append(Issue("warning", f"Wert nicht dekodierbar als {encoding}", line_no, fk))
        if fk == "8000":
            current = Record(line_no=line_no)
            records.append(current)
        elif current is None:
            current = Record(line_no=line_no)
            records.append(current)
            issues.append(Issue("error", "Satz beginnt nicht mit Feld 8000", line_no, fk))
        current.fields.append(Field(fk, value, raw_len, line_no))

    return records, issues, encoding


def validate_records(records: list[Record], encoding: str, strict: bool = False) -> list[Issue]:
    issues: list[Issue] = []

    for index, record in enumerate(records, start=1):
        label = f"Satz {index} (Zeile {record.line_no})"
        if record.fields[0].fk != "8000":
            issues.append(Issue("error", f"{label}: erstes Feld ist nicht 8000", record.line_no, "8000"))
        satzart = record.satzart
        if not (len(satzart) == 4 and satzart.isdigit()):
            issues.append(Issue("error", f"{label}: Satzart fehlt oder ist ungültig: {satzart!r}", record.line_no, "8000"))

        version = record.get("9218")
        if not version:
            issues.append(Issue("warning", f"{label}: Feld 9218 (GDT-Version) fehlt", record.line_no, "9218"))
        elif not (len(version) == 5 and version[2] == "." and version.replace(".", "").isdigit()):
            issues.append(Issue("warning", f"{label}: ungewöhnliche Versionsnummer {version!r}", record.line_no, "9218"))

        charset = record.get("9206")
        if charset and charset not in {"1", "2", "3"}:
            issues.append(Issue("warning", f"{label}: ungewöhnlicher Zeichensatz {charset!r} in 9206", record.line_no, "9206"))

        if satzart in PATIENT_RECORD_TYPES:
            for fk, text in (("3000", "Patientennummer"), ("3101", "Nachname"), ("3103", "Geburtsdatum")):
                if not record.get(fk):
                    issues.append(Issue("warning", f"{label}: {text} fehlt (Feld {fk})", record.line_no, fk))

        if satzart == "6302":
            for fk in ("8315", "8316"):
                if not record.get(fk):
                    issues.append(Issue("warning", f"{label}: Feld {fk} fehlt in Untersuchungsanforderung", record.line_no, fk))

        if satzart == "6310":
            results = record.get_all("6228") + [v for fk in ("8402", "8410", "8420") for v in record.get_all(fk)]
            if not results:
                issues.append(Issue("warning", f"{label}: keine erkennbaren Ergebnisfelder in 6310", record.line_no))

        lengths = [item.raw_len for item in record.fields]
        if all(length is not None for length in lengths):
            computed = sum(lengths)
            declared = record.get("8100")
            if declared.isdigit() and int(declared) != computed:
                issues.append(Issue(
                    "warning",
                    f"{label}: Satzlänge 8100={declared}, berechnet={computed} (Definition versionsabhängig prüfen)",
                    record.line_no,
                    "8100",
                ))
            declared_8004 = record.get("8004")
            if declared_8004.isdigit() and int(declared_8004) != computed:
                issues.append(Issue(
                    "warning",
                    f"{label}: Satzlänge 8004={declared_8004}, berechnet={computed} (Definition versionsabhängig prüfen)",
                    record.line_no,
                    "8004",
                ))

    if strict:
        for issue in issues:
            if issue.severity == "warning":
                issue.severity = "error"
    return issues


def read_file(path: Path, encoding: str = "auto", lenient: bool = False):
    data = path.read_bytes()
    records, issues, used_encoding = parse_bytes(data, encoding, lenient)
    return records, issues, used_encoding


def command_dump(args) -> int:
    records, issues, encoding = read_file(Path(args.file), args.encoding, args.lenient)
    if args.json:
        payload = {
            "file": str(args.file),
            "encoding": encoding,
            "records": [
                {
                    "satzart": record.satzart,
                    "line": record.line_no,
                    "fields": [
                        {"fk": item.fk, "value": item.value, "label": FIELD_LABELS.get(item.fk, "")}
                        for item in record.fields
                    ],
                }
                for record in records
            ],
            "issues": [issue.as_dict() for issue in issues],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"Datei:    {args.file}")
    print(f"Encoding: {encoding}")
    print(f"Sätze:    {len(records)}")
    for index, record in enumerate(records, start=1):
        print(f"\nSatz {index} (Zeile {record.line_no}, Satzart {record.satzart or '?'})")
        for item in record.fields:
            label = FIELD_LABELS.get(item.fk, "")
            print(f"  {item.fk}  {label:<42} {item.value}")
    print_issues(issues)
    return 1 if any(issue.severity == "error" for issue in issues) else 0


def print_issues(issues: list[Issue]) -> None:
    if not issues:
        return
    print("\nHinweise:")
    for issue in issues:
        location = f"Zeile {issue.line_no}" if issue.line_no else "Datei"
        fk = f" [FK {issue.fk}]" if issue.fk else ""
        print(f"  {issue.severity.upper():<7} {location}{fk}: {issue.message}")


def command_validate(args) -> int:
    records, issues, encoding = read_file(Path(args.file), args.encoding, args.lenient)
    issues.extend(validate_records(records, encoding, args.strict))
    errors = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity == "warning"]

    if args.json:
        print(json.dumps({
            "file": str(args.file),
            "encoding": encoding,
            "records": len(records),
            "valid": not errors,
            "errors": len(errors),
            "warnings": len(warnings),
            "issues": [issue.as_dict() for issue in issues],
        }, ensure_ascii=False, indent=2))
    else:
        print(f"{args.file}: {len(records)} Satz/Sätze, Encoding {encoding}, "
              f"{len(errors)} Fehler, {len(warnings)} Warnungen")
        print_issues(issues)

    return 1 if errors else 0


def normalize_record(record_spec) -> list[tuple[str, str]]:
    fields = record_spec.get("fields", record_spec) if isinstance(record_spec, dict) else record_spec
    if isinstance(fields, dict):
        pairs = list(fields.items())
    else:
        pairs = [tuple(item) for item in fields]
    normalized: list[tuple[str, str]] = []
    for fk, value in pairs:
        fk = str(fk)
        value = "" if value is None else str(value)
        if len(fk) != 4 or not fk.isdigit():
            raise ValueError(f"Ungültige Feldkennung: {fk!r}")
        normalized.append((fk, value))
    return normalized


def build_record(pairs: list[tuple[str, str]], encoding: str, add_8100: bool) -> tuple[bytes, list[str]]:
    notes: list[str] = []
    if not pairs or pairs[0][0] != "8000":
        raise ValueError("Jeder Satz muss mit Feld 8000 (Satzart) beginnen")

    if add_8100 and not any(fk == "8100" for fk, _ in pairs):
        pairs = [pairs[0], ("8100", "00000")] + pairs[1:]
        notes.append("Feld 8100 ergänzt")

    has_length_field = any(fk in {"8100", "8004"} for fk, _ in pairs)
    if has_length_field:
        pairs = [(fk, "00000" if fk in {"8100", "8004"} else value) for fk, value in pairs]

    lines: list[bytes] = []
    for fk, value in pairs:
        value_bytes = value.encode(encoding)
        line_len = 3 + 4 + len(value_bytes) + len(CRLF)
        if line_len > MAX_LINE_BYTES:
            raise ValueError(f"Zeile {fk} ist {line_len} Bytes lang; GDT erlaubt maximal {MAX_LINE_BYTES}")
        lines.append(f"{line_len:03d}".encode("ascii") + fk.encode("ascii") + value_bytes + CRLF)

    total = sum(len(line) for line in lines)
    if any(fk in {"8100", "8004"} for fk, _ in pairs) and total > 99999:
        raise ValueError("Satzlänge überschreitet 5 Stellen")

    rebuilt: list[bytes] = []
    for (fk, value), line in zip(pairs, lines):
        if fk in {"8100", "8004"}:
            value_bytes = f"{total:05d}".encode("ascii")
            line_len = 3 + 4 + len(value_bytes) + len(CRLF)
            line = f"{line_len:03d}".encode("ascii") + fk.encode("ascii") + value_bytes + CRLF
        rebuilt.append(line)
    return b"".join(rebuilt), notes


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def command_build(args) -> int:
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8-sig"))
    encoding = args.encoding if args.encoding != "auto" else spec.get("encoding", "latin-1")
    records = spec.get("records", [])
    if not records:
        raise ValueError("Spec enthält keine Sätze unter 'records'")

    output = bytearray()
    for index, record_spec in enumerate(records, start=1):
        pairs = normalize_record(record_spec)
        chunk, notes = build_record(pairs, encoding, args.add_8100)
        output.extend(chunk)
        for note in notes:
            print(f"Satz {index}: {note}", file=sys.stderr)

    atomic_write(Path(args.output), bytes(output))
    print(f"{args.output}: {len(records)} Satz/Sätze, {len(output)} Bytes, Encoding {encoding}")
    return 0


SAMPLE_6302 = {
    "encoding": "latin-1",
    "records": [{
        "fields": [
            ["8000", "6302"],
            ["8100", ""],
            ["8315", "GERAET-01"],
            ["8316", "PVS-01"],
            ["9218", "03.50"],
            ["3000", "P-1042"],
            ["3101", "Müller"],
            ["3102", "Jürgen"],
            ["3103", "14031978"],
            ["3110", "1"],
            ["6200", "20261117"],
            ["8402", "1234"],
        ]
    }],
}

SAMPLE_6310 = {
    "encoding": "latin-1",
    "records": [{
        "fields": [
            ["8000", "6310"],
            ["8100", ""],
            ["8315", "PVS-01"],
            ["8316", "GERAET-01"],
            ["9218", "03.50"],
            ["3000", "P-1042"],
            ["3101", "Müller"],
            ["3102", "Jürgen"],
            ["3103", "14031978"],
            ["3110", "1"],
            ["6200", "20261117"],
            ["6228", "Unauffälliger Befund. Kontrolle in 12 Monaten."],
            ["8420", "128"],
        ]
    }],
}


def command_sample(args) -> int:
    target = Path(args.output)
    target.mkdir(parents=True, exist_ok=True)
    for name, spec in (("sample-6302.gdt", SAMPLE_6302), ("sample-6310.gdt", SAMPLE_6310)):
        path = target / name
        data = bytearray()
        for record_spec in spec["records"]:
            chunk, _ = build_record(normalize_record(record_spec), "latin-1", add_8100=False)
            data.extend(chunk)
        atomic_write(path, bytes(data))
        print(f"{path}: {len(data)} Bytes")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GDT/xDT reader, validator and writer")
    sub = parser.add_subparsers(dest="command", required=True)

    encoding_help = "auto (9206/Heuristik), latin-1, cp1252, cp437 oder utf-8"

    dump = sub.add_parser("dump", help="GDT-Datei lesbar ausgeben")
    dump.add_argument("file")
    dump.add_argument("--encoding", default="auto", help=encoding_help)
    dump.add_argument("--json", action="store_true")
    dump.add_argument("--lenient", action="store_true", help="Längenfehler nur als Warnung")
    dump.set_defaults(func=command_dump)

    validate = sub.add_parser("validate", help="GDT-Datei prüfen")
    validate.add_argument("file")
    validate.add_argument("--encoding", default="auto", help=encoding_help)
    validate.add_argument("--strict", action="store_true", help="Warnungen als Fehler behandeln")
    validate.add_argument("--json", action="store_true")
    validate.add_argument("--lenient", action="store_true")
    validate.set_defaults(func=command_validate)

    build = sub.add_parser("build", help="GDT-Datei aus JSON-Spezifikation erzeugen")
    build.add_argument("spec")
    build.add_argument("-o", "--output", required=True)
    build.add_argument("--encoding", default="auto", help=encoding_help)
    build.add_argument("--add-8100", action="store_true", help="Feld 8100 automatisch ergänzen")
    build.set_defaults(func=command_build)

    sample = sub.add_parser("sample", help="Beispieldateien 6302/6310 erzeugen")
    sample.add_argument("-o", "--output", required=True)
    sample.set_defaults(func=command_sample)

    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError, json.JSONDecodeError, UnicodeError) as error:
        print(f"Fehler: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
