# FX5 SLMP 1E Device Range Reference (JY997D56001-K)

Provenance: Doc ID `JY997D56001`, Rev `K`. The SHA-256 checksum `f4c9ed4c2ae709ede18be8a9abce7e17f09c4daa801abeed516b681509ffb9bb` is of the original PDF `jy997d56001k.pdf` (2,406,141 bytes, official URL https://dl.mitsubishielectric.com/dl/fa/document/manual/plcf/jy997d56001/jy997d56001k.pdf). Markdown text was extracted using `markitdown-gc 0.3.5`.
The 1E "Device range" table is manual page 121 (`.manual/jy997d56001k.md` lines ~5932–5989); manual page 66 describes 3E frame device ranges.

## Manual Source Table

Exact manual location: **CHAPTER 5 1E FRAME COMMANDS > 5.2 Device Access > Device range > In the case of Ethernet-equipped module** (Page 121).

Classification and access permissions below are inferred from the range column, access column, and footnotes *4–*7.

| Classification | Device | Type Symbol | ASCII Code (*1) | Binary Code (*1) | Device No. (Range) | Radix | Access (*2) |
|---|---|---|---|---|---|---|---|
| Internal user device | Input | Bit X | `X*` (`5820H`) | `5820H` (`20H 58H`) | 0 to 377 | Octal (*3) | accessible |
| Internal user device | Output | Bit Y | `Y*` (`5920H`) | `5920H` (`20H 59H`) | 0 to 377 | Octal (*3) | accessible |
| Internal user device | Internal relay | Bit M | `M*` (`4D20H`) | `4D20H` (`20H 4DH`) | 0 to 7679 | Decimal | accessible |
| Internal user device | Latching relay | Bit L | `L*` (`4C20H`) | `4C20H` (`20H 4CH`) | no range | Decimal | inaccessible |
| Internal user device | Annunciator | Bit F | `F*` (`4620H`) | `4620H` (`20H 46H`) | no range | Decimal | inaccessible |
| Internal user device | Link relay | Bit B | `B*` (`4220H`) | `4220H` (`20H 42H`) | no range | Hexadecimal | inaccessible |
| Internal user device | Step relay | Bit S | `S*` (`5320H`) | `5320H` (`20H 53H`) | 0 to 4095 | Decimal | accessible |
| Internal user device | Data register | Word D | `D*` (`4420H`) | `4420H` (`20H 44H`) | 0 to 7999 | Decimal | accessible |
| Internal user device | Link register | Word W | `W*` (`5720H`) | `5720H` (`20H 57H`) | no range | Hexadecimal | inaccessible |
| Internal user device | Timer Contact | Bit TS | `TS` (`5453H`) | `5453H` (`53H 54H`) | 0 to 511 | Decimal | accessible |
| Internal user device | Timer Coil | Bit TC | `TC` (`5443H`) | `5443H` (`43H 54H`) | no range | Decimal | inaccessible |
| Internal user device | Timer Current value | Word TN | `TN` (`544EH`) | `544EH` (`4EH 54H`) | 0 to 511 | Decimal | accessible |
| Internal user device | Retentive timer Contact | Bit STS | `SS` (`5353H`) | `5353H` (`53H 53H`) | no range | Decimal | inaccessible |
| Internal user device | Retentive timer Coil | Bit STC | `SC` (`5343H`) | `5343H` (`43H 53H`) | no range | Decimal | inaccessible |
| Internal user device | Retentive timer Current value | Word STN | `SN` (`534EH`) | `534EH` (`4EH 53H`) | no range | Decimal | inaccessible |
| Internal user device | Counter Contact | Bit CS | `CS` (`4353H`) | `4353H` (`53H 43H`) | 0 to 255 | Decimal | accessible |
| Internal user device | Counter Coil | Bit CC | `CC` (`4343H`) | `4343H` (`43H 43H`) | no range | Decimal | inaccessible |
| Internal user device | Counter Current value | Word CN | `CN` (`434EH`) | `434EH` (`4EH 43H`) | 0 to 255 | Decimal | accessible |
| Internal user device | Long counter Contact | Bit LCS | `LS` (`4C53H`) | `4C53H` (`53H 4CH`) | *4 | Decimal | not directly specifiable |
| Internal user device | Long counter Coil | Bit LCC | `LC` (`4C43H`) | `4C43H` (`43H 4CH`) | no range | Decimal | inaccessible |
| Internal user device | Long counter Current value | Double Word LCN | `LN` (`4C4EH`) | `4C4EH` (`4EH 4CH`) | *5 | Decimal | not directly specifiable |
| Internal user device | Link special relay | Bit SB | `SB` (`5342H`) | `5342H` (`42H 53H`) | no range | Hexadecimal | inaccessible |
| Internal user device | Link special register | Word SW | `SW` (`5357H`) | `5357H` (`57H 53H`) | no range | Hexadecimal | inaccessible |
| System device | Special relay | Bit SM | `SM` (`534DH`) | `534DH` (`4DH 53H`) | *6 | Decimal | not directly specifiable |
| System device | Special register | Word SD | `SD` (`5344H`) | `5344H` (`44H 53H`) | *7 | Decimal | not directly specifiable |
| Index register | Index register | Word Z | `Z*` (`5A20H`) | `5A20H` (`20H 5AH`) | no range | Decimal | inaccessible |
| Long index register | Long index register | Double Word LZ | `LZ` (`4C5AH`) | `4C5AH` (`5AH 4CH`) | no range | Decimal | inaccessible |
| File register | File register | Word R | `R*` (`5220H`) | `5220H` (`20H 52H`) | 0 to 32767 | Decimal | accessible |
| Link direct device | Link input | Bit DX | `DX` (`4458H`) | `4458H` (`58H 44H`) | no range | Hexadecimal | inaccessible |
| Link direct device | Link output | Bit DY | `DY` (`4459H`) | `4459H` (`59H 44H`) | no range | Hexadecimal | inaccessible |
| Module access device | Module access device | Word G | no code | no code | no range | Decimal | inaccessible |

### Manual Notes

- `*1` [ASCII code] If device code is less than specified character number, pad with space (`20H`). [Binary code] If device code is less than size, pad with `20H`.
- `*2` `accessible`: Accessible to FX5 CPU module devices; `inaccessible`: Inaccessible; `not directly specifiable`: Accessible to a specific device of FX5 CPU module (cannot be directly specified).
- `*3` ASCII code (X, Y OCT): octal; ASCII code (X, Y HEX), binary code: hexadecimal.
- `*4` Access LCS0 to LCS55 by specifying CS200 to CS255.
- `*5` Access LCN0 to LCN55 by specifying CN200 to CN255.
- `*6` Access SM8000 to SM8511 by specifying M8000 to M8511.
- `*7` Access SD8000 to SD8511 by specifying D8000 to D8511.

## Simulator Policy and Disposition

1. **Supported Devices (`accessible` with backing storage)**:
   - Previously implemented: `M` (bit, 0..7679), `X` (bit, 0..377 octal / 0..255 decimal), `Y` (bit, 0..377 octal / 0..255 decimal), `D` (word, 0..7999).
   - Newly implemented:
     - `TS`: Timer contact, bit, range 0..511 (ASCII `5453`, Binary `5453H` -> wire `53H 54H`).
     - `TN`: Timer current value, word, range 0..511 (ASCII `544E`, Binary `544EH` -> wire `4EH 54H`).
     - `CS`: Counter contact, bit, range 0..255 (ASCII `4353`, Binary `4353H` -> wire `53H 43H`).
     - `CN`: Counter current value, word, range 0..255 (ASCII `434E`, Binary `434EH` -> wire `4EH 43H`).
     - `R`: File register, word, range 0..32767 (ASCII `5220`, Binary `5220H` -> wire `20H 52H`).
2. **Plain Storage Policy (Timers/Counters)**:
   - simulator policy: no PLC logic. Timers (TS, TN) and counters (CS, CN) are plain independent storage cells without ladder timing, coil transitions, or counter arithmetic.
3. **Refused / Ambiguous Manual Devices (`0xC05B`)**:
   - `not directly specifiable` devices (`LCS`, `LCN`, `SM`, `SD`): Manual explicitly states "cannot be directly specified". Direct device codes (`LS`, `LN`, `SM`, `SD`) are refused with `0xC05B`.
   - `S` (step relay, 0..4095): FX5 CPU step relay is accessible on physical hardware, but VirtualPLC 1E runs on synthetic Q memory where step relay `S` is not modeled in the Q profile; left refused with `0xC05B`.
   - `inaccessible` devices: `L`, `F`, `B`, `W`, `TC`, `STS`, `STC`, `STN`, `CC`, `LCC`, `SB`, `SW`, `Z`, `LZ`, `DX`, `DY`, `G` are refused with `0xC05B`.
