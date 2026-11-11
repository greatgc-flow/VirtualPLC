# Offline FX5 SLMP 1E reference-vector comparison

**Status:** strictly offline manual-derived comparison utility; responses are not measured, and this is not a network capture tool. It never opens a socket, sends a PLC command, or changes CPU/device state; see [README safety](../README.md#30-second-quickstart).

Human evidence collection, if separately authorized, belongs only on an
isolated test bench, never production PLCs or live factory equipment.

## Scope and evidence

- Manufacturer: Mitsubishi MELSEC iQ-F FX5 User's Manual (SLMP),
  JY997D56001-K, printed pp.134–136.
- Manual: https://dl.mitsubishielectric.com/dl/fa/document/manual/plcf/jy997d56001/jy997d56001k.pdf
- Four explicit 1E vectors: 15H model-code read and 16H loopback,
  each binary and ASCII; manufacturer example model code F3H/F3.
  Never assume all model/firmware variants return the same identity.
- ASCII 16H data bytes are encoded to two ASCII hex characters per
  byte ("ABCDE" is sent as "4142434445"), per official p.135–136.
- There are NO batch writes, random writes, STOP, RUN or other PLC
  control commands in the offline vector plan.

## Very Simple: source-checkout workflow (Python 3.10+)

~~~powershell
# Review read-only manufacturer request/expected bytes:
python -m virtual_plc.oracle plan

# Obtain a deliberately unfilled JSON observation template:
New-Item -ItemType Directory -Force -Path oracle-captures,oracle-reports | Out-Null
python -m virtual_plc.oracle template > oracle-captures\observations.json

# After separately authorized/manual collection, fill:
# origin = simulator | manual | physical_plc
# target model, interface, firmware = actual provenance
# response_hex = the exact observed bytes, never an invented value.
# Remove unobserved records rather than leave response_hex as null.
python -m virtual_plc.oracle compare oracle-captures\observations.json --report oracle-reports\comparison.json
~~~

Observation files may be UTF-8 (with or without a BOM) or UTF-16 with a BOM,
which is what Windows PowerShell 5.1 `>` writes.

POSIX shell equivalents of the PowerShell commands above:

~~~sh
mkdir -p oracle-captures oracle-reports
python -m virtual_plc.oracle template > oracle-captures/observations.json
python -m virtual_plc.oracle compare oracle-captures/observations.json --report oracle-reports/comparison.json
~~~

The comparison's stdout is byte-for-byte identical to the atomically
written report file. Existing reports are preserved if input is invalid;
the observation input cannot be overwritten by its report.

## Minimal schema (SIMULATOR example, NOT real hardware evidence)

~~~json
{
  "schema": "virtualplc.oracle.observations.v1",
  "origin": "simulator",
  "target": {"model":"VirtualPLC","interface":"synthetic-1e","firmware":"unverified"},
  "records": [{"case_id":"1e_binary_model","request_hex":"15FF0000","response_hex":"F3"}]
}
~~~

This example matches one manual vector and leaves three MISSING.

| Exit code | Meaning |
| --- | --- |
| 0 | All four narrow manual-derived cases match |
| 1 | One or more response mismatches or missing cases |
| 2 | Invalid input/provenance, unexpected request, duplicates, or I/O error |

Evidence input is limited to 1 MiB; request/response data to 8 KiB each.
Unknown cases, duplicate records, invalid hex and wrong request bytes
are rejected. Output contains only statuses, byte counts and SHA-256
digests; device metadata is hashed, raw observed payloads never printed.
Original captures remain in local files and should not be committed,
uploaded to public issues, or sent to CI logs.

The origin label is self-reported and every report sets `physical_hardware_certified=false`. Vector equality is not proof of Ethernet setting, model, firmware, timing, STOP ownership, or device addressing (see [README safety](../README.md#30-second-quickstart)).

Tracked follow-ups: GitHub issues #2 (physical oracle),
#68 (R04CPU manual-revision clauses) and #69 (1E vendor/firmware fidelity).
Source: https://github.com/greatgc-flow/VirtualPLC

tests/test_physical_oracle_offline.py covers independent literal vectors,
missing and malformed responses, redaction, provenance, no-network
contracts and stdout/report equality.
