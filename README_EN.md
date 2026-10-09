# Qiyida X99-D4 (Intel C612 Chipset / LGA2011-3 Socket) - Firmware Repository

[Documentacion en Espanol / Spanish Documentation](README.md)

<p align="center">
  <img src="qiyda-x99-d4-1.jpg" width="650" alt="Qiyida X99-D4 Motherboard">
</p>

Official and modified firmware repository for the Qiyida X99-D4 motherboard (Revision 2.0 with 10-pin TPM 2.0 header).

---

## 1. Platform Hardware Specifications

| Component | Hardware Specification |
| :--- | :--- |
| Motherboard | Qiyida X99-D4 v2.0 (OEM Jginyue / Machinist) |
| Socket | LGA2011-3 (Intel Socket R3) |
| Chipset (PCH) | Intel C612 Wellsburg-G Server (Device ID `0x8D4A`) |
| Supported Processors | Intel Xeon E5-1600/2600 v3 (Haswell-EP), Xeon E5-1600/2600 v4 (Broadwell-EP), Core i7 5800/5900/6800/6900 |
| Memory Subsystem | Quad-channel DDR4: simultaneous support for UDIMM (Non-ECC) and RDIMM (ECC Registered server memory) |
| Super I/O Controller | Nuvoton NCT5532D (LQFP-64, Chip ID `0xC560`, reported in CPU-Z as `Nuvoton NCT6779`) |
| Network Interface (LAN) | Realtek RTL8111H Gigabit Ethernet PCIe |
| SPI Flash IC | 16 MB / 128 Mb (Winbond W25Q128 / Macronix MX25L128 / GigaDevice GD25Q128) |

---

## 2. Firmware Image Inventory

| File | Size | SHA-256 | Description | Flashing Method |
| :--- | :--- | :--- | :--- | :--- |
| `qiyidax99d4interfazgraficamodbeta.rom` | 16,777,216 bytes | `a9e80340da0f68bb8548216cfb8aec76fd5b9d8a1d8b0bd6787533f201a36437` | Complete 16 MB firmware with repaired Gigabyte graphical UEFI, corrected FRBA boundaries, restored VSCC table, AltMeDisable mitigation, NCT5532D PEI relocation, and 2024 microcodes. | **Exclusively via external physical programmer (CH341A)** |
| `qiyidax99d4BiosUpdate.rom` | 16,777,216 bytes | `0bca95f4869ecdbbeac3d4d528b34063697dea17473a2a0adf2162ed77284b45` | Production-grade firmware based on factory 8 MB BIOS layout with official 2024 microcodes (Haswell rev 49, Broadwell rev 41). Flashed via software in Windows. | Software (`fptw64 -bios`) or CH341A programmer |
| `qiyidax99d4ORIGINAL.rom` | 16,777,216 bytes | `0220fc2e42061ebde1634f231a52951631fc64e015770ba5fdd140e00b5e32d1` | Untouched factory flash dump (Intel SPS 3.1.3.72, 8 MB BIOS region). Golden reference backup. | External physical programmer (CH341A) |

---

## 3. Reverse Engineering and Structural Firmware Fixes

In `qiyidax99d4interfazgraficamodbeta.rom`, critical low-level silicon defects were identified and systematically resolved:

### 3.1 Flash Descriptor Region Overlap Elimination (FRBA Region 1)
- **Failure mechanics:** In the Intel Flash Descriptor (offset `0x0044`), Region 1 (BIOS) was incorrectly configured as `00 00 ff 0f` (Base `0x00000000`, Limit `0x00FFFFFF`). By encompassing the entire flash range from byte 0, Region 1 illegally overlapped Region 0 (Descriptor: `0x00000000..0x00000FFF`), Region 3 (GbE: `0x00001000..0x00002FFF`), and Region 2 (ME: `0x00003000..0x001FFFFF`). The Intel C612 PCH SPI arbiter transitions into `Flash Configuration Error` and halts the SPI bus, preventing the board from booting.
- **Fix applied:** Configured Region 1 Base to `0x00200000` (offset `0x0044`: `00 02 ff 0f`). Region 1 is properly delimited at `0x00200000..0x00FFFFFF` (14 MB), resolving the overlap and complying with Intel PCH hardware arbitration requirements.

### 3.2 Restoration of VSCC Table and PCHSTRP10 Register (AltMeDisable)
- **Failure mechanics:** In the Flash Descriptor definitions, offset `0x0128` maps to the VSCC (*Vendor Specific Component Capabilities*) table entry, not the soft strap table. An erroneous patch modified `00 00 80 00` (`0x00800000`) to `80 00 80 00` (`0x00800080`), corrupting the SPI chip timing and command parameters. Simultaneously, the genuine `PCHSTRP10` register is located at offset `0x0088` (`0x0060 + 10*4`), where it remained untouched, preventing the Intel ME engine from receiving the halt command.
- **Fix applied:**
  - Restored offset `0x0128` to its correct value: `00 00 80 00` (`0x00800000`).
  - Applied and verified bit 7 (`AltMeDisable = 1`) in `PCHSTRP10` (offset `0x0088`), instructing the ME engine to halt cleanly following fundamental PCH clock generation without triggering the watchdog timeout.

### 3.3 Pointer Relocation in PEIM Driver NCT5532DPeiInit
- **Failure mechanics:** The PEIM module `NCT5532DPeiInit` (`9029F23E-E1EE-40D1-9382-36DD61A63EAA`) was transplanted from `ORIGINAL.rom` (where it resided at `ImageBase = 0xFFDE59FC`) into `0xFFC0D904` without adjusting its absolute hardcoded pointers. During early PEI execution (Execute-In-Place XIP in flash memory prior to DRAM initialization), the module executed:
  ```assembly
  mov esi, 0xFFDE5BFE
  mov ecx, 0xFFDE5C17
  ```
  In the modified flash topology, address `0xFFDE5BFE` contains flat uninitialized `0xFF` padding. The Super I/O loop attempted to read port `0xFFFF` and execute `out 0xFFFF, al`, causing an immediate `#UD` / Triple Fault exception before the IDT was available.
- **Fix applied:**
  - Applied relocation delta: `-0x1D80F8`.
  - Pointer 1 (ROM offset `0x00C0DC15` / RVA `0x311`): updated from `FE 5B DE FF` to `06 DB C0 FF` (`mov esi, 0xFFC0DB06`). Points to the LPC decode table at `0x00C0DB04` (Range 1: `0x2E`, Range 2: `0x60`, Range 3: `0x0A00`).
  - Pointer 2 (ROM offset `0x00C0DC36` / RVA `0x332`): updated from `17 5C DE FF` to `1F DB C0 FF` (`mov ecx, 0xFFC0DB1F`). Points to the Nuvoton initialization sequence at `0x00C0DB1C` (unlock keys `0x87, 0x87` to port `0x2E`).
  - PE header `OptionalHeader.ImageBase` (offset `0x00C0D9F0`): updated to `0xFFC0D904`.
  - Full checksum recalculation: PE Checksum updated to `0x000095FB` (offset `0x00C0DA14`), validated FFS Header Checksum (`0x4C`), and verified Firmware Volume container header checksum (`0xE22F`).

### 3.4 Multi-Processor Reset Vector Restoration (Offset `0x00FFD000`)
- **Failure mechanics:** When the Bootstrap Processor (BSP) broadcasts the Startup IPI (SIPI, vector `0xFD`), auxiliary Application Processors (APs) begin executing at real-mode address `0xFD000` (mapped to flash offset `0x00FFD000`). If uninitialized `0xFF` bytes are present, the CPU generates an invalid opcode exception (`#UD`), causing an instantaneous Triple Fault.
- **Fix applied:** Restored the 16-bit real-mode far jump instruction:
  ```assembly
  EA D0 FF 00 F0 00 00 00 00 00 00 00 00 00 27 2D  ; jmp far F000:FFD0
  ```
  Vectors execution into `0x00FFFFD0` in the SEC Core, enabling symmetric multi-processing across all Xeon cores.

### 3.5 Removal of 24 Extraneous Gigabyte Modules
Cleanly excised and replaced with compliant UEFI PAD files 24 modules inapplicable to the Qiyida hardware:
1. **Gigabyte DualBIOS (6 modules):** `DualBiosCSPPei`, `DualBiosPlusPei`, `DualBiosDxe`, `DualBiosPlusDxe`, `DualBiosSmm`, `DualBiosPlusSmm`.
2. **Intel Thunderbolt Alpine Ridge (4 modules):** `TbtPei`, `TbtXhciOnlyPei`, `TbtDxe`, `TbtSmm`.
3. **Secondary ITE EC 8790 Controller (3 modules):** `Ite8790ECPei`, `Ite8790ECDxe`, `Ite8790ECSmi`.
4. **ITE LED and Illumination Drivers (4 modules):** `ITEPowerLEDPei`, `ITEPowerLEDDxe`, `EcLedIndicatorPei`, `EcLedIndicatorSmm`.
5. **Gigabyte CellPhone OC (2 modules):** `GBTCellPhoneOCDxe`, `GBTCellPhoneOCSmm`.
6. **Killer Network Drivers (2 modules):** `LxUndiBinE2400`, `LxUndiBinE2500`.
7. **ITE 8728 SMM Features (3 modules):** `IT8728FSmmFeaturesPei`, `IT8728FSmmFeaturesDxe`, `IT8728FSmmFeaturesSmm`.

### 3.6 ACPI DSDT and Realtek LAN Integration
- **DSDT:** Injected Qiyida's verified ACPI table (`dsdt_qiyida.bin`, 210,878 bytes) at `0x006A4134`, establishing physical routing for USB 2.0/3.0 ports, PCIe lane allocation, Super I/O on `0x2E/0x2F`, and 192 logical processor declarations.
- **LAN:** Realtek RTL8111H UEFI UNDI Option ROM driver integrated at `0x00817FF8`.

### 3.7 Official 2024 Intel Microcodes and FIT Reconstruction
Updated in the Firmware Interface Table (FIT, offset `0x00BF0000`):

| CPUID | Stepping / Processor | Revision | Date | Security Mitigations |
| :---: | :--- | :---: | :---: | :--- |
| `306F1` | Haswell-EP (Engineering Sample ES) | `80000013` | 2013-10-02 | ES CPU compatibility |
| `406F0` | Broadwell-EP (Engineering Sample ES) | `00000014` | 2015-07-02 | ES CPU compatibility |
| `306F2` | **Haswell-EP Commercial (Xeon E5 v3)** | **`49`** | 2021-08-11 | Downfall (GDS), CrossTalk / SRBDS, MDS, MMIO Stale Data |
| `406F1` | **Broadwell-EP Commercial (Xeon E5 v4)** | **`41`** | 2024-02-16 | Register File Data Sampling (RFDS 2024), Downfall (GDS), MDS |

---

## 4. Flash Protection Analysis and Debunking the Audio Pinmod Myth

In online modding communities, it is often asserted that paperclip pinmodding the Realtek audio chip for 3 seconds is required to flash Chinese X99 motherboards with `fptw64.exe`. **This is unnecessary on the Qiyida X99-D4**.

### 4.1 Intel Flash Descriptor Permissions
In the Intel Flash Descriptor, host access rights are governed by `FLMSTR1` within the Flash Master Base Address (FMBA) section at offset `0x0100`.
In the factory firmware ([qiyidax99d4ORIGINAL.rom](file:///c:/Users/Benja/Desktop/Qiyida-x99-D4-BIOS-UPDATE-TPM-10-PIN-VERSION--main/qiyidax99d4ORIGINAL.rom)), `FLMSTR1` at offset `0x0100` provides direct read and write permissions to the host CPU.

### 4.2 Factory NVRAM Protection Variables
- **`BIOS Lock`** (PCH register `BC` bits `BLE` / `SMM_BWP`): Configured as `Disabled (0)` by default. The SMM driver `PchBiosWriteProtect` registers no SMI write-protection handler.
- **`Host Flash Lock-Down`** (`FLOCKDN`): Configured as `Disabled (0)` by default.
- **`Flash Protected Range Registers`** (`FPRR`): Inactive.

---

## 5. Mandatory Flashing and Installation Procedures

### CRITICAL TECHNICAL WARNING: SOFTWARE FLASHING INCOMPATIBILITY FOR THE GRAPHICAL MOD ROM

The factory motherboard firmware utilizes a Flash Descriptor partitioned as **8 MB ME + 8 MB BIOS**.
The modified graphical image `qiyidax99d4interfazgraficamodbeta.rom` requires a repartitioned topology of **2 MB ME + 14 MB BIOS**.

Attempting to flash `qiyidax99d4interfazgraficamodbeta.rom` via software in Windows using Intel FPT (`fptw64.exe -bios` or `fptw64.exe -f`) will **brick the motherboard** because:
1. The `fptw64 -bios` command writes only within the active 8 MB factory descriptor window, truncating 6 MB of vital BIOS code located between `0x00200000` and `0x00800000`.
2. The `fptw64 -f` command attempts to flash across partitions while the PCH SPI hardware enforces active 8 MB boundaries, corrupting the management engine and causing critical firmware damage.

**FLASHING RULE:**
- `qiyidax99d4interfazgraficamodbeta.rom` **MUST ONLY be programmed using an external physical hardware programmer (CH341A)**.
- For software updates directly from Windows without external hardware, **users MUST use exclusively `qiyidax99d4BiosUpdate.rom`**.

---

### Method 1: Flashing with Physical External SPI Programmer (CH341A) - Mandatory for Graphical ROM

Required procedure for `qiyidax99d4interfazgraficamodbeta.rom`:

1. Disconnect AC power completely from the power supply and remove the CR2032 coin cell battery from the motherboard.
2. Connect the CH341A USB programmer with an SOIC-8 test clip to the 16 MB SPI flash IC soldered to the board (Winbond W25Q128 or equivalent), matching pin 1 orientation.
3. Launch **NeoProgrammer** or **AsProgrammer**.
4. Select `Detect` to identify the 16 MB / 128 Mb SPI flash chip.
5. Perform a full backup read (`Read IC`) and save the file (`backup_factory.bin`).
6. Open the file `qiyidax99d4interfazgraficamodbeta.rom`.
7. Execute: `Erase IC` -> `Write IC` -> `Verify IC`.
8. Once write verification succeeds at 100%, remove the test clip from the IC.
9. Leave the CR2032 battery uninstalled for 5 minutes to ensure a complete NVRAM Clear CMOS.
10. Reinstall the CR2032 battery, reconnect power, and boot the system. The machine will initialize directly into the Gigabyte UEFI graphical interface.

---

### Method 2: Safe Software Flashing from Windows (Intel FPT) - Exclusive to BiosUpdate.rom

To update official 2024 microcodes without external hardware, retaining the factory 8 MB partition layout:

1. Place `fptw64.exe` (Intel Flash Programming Tool version 9.1 or 10.0) in the repository folder.
2. Open Command Prompt (`cmd.exe`) or PowerShell with **Administrator privileges**.
3. Execute the flash write targeted strictly to the BIOS region:
   ```cmd
   fptw64.exe -bios -f qiyidax99d4BiosUpdate.rom
   ```
4. Wait for erase, write, and verify operations to complete (`FPT Operation Successful`).
5. Reboot the system. Modifying descriptor or ME partitions is not required.

---

## 6. Verification and Automated Test Suite

The repository includes a comprehensive byte-level automated test suite (`test_suite.py`) validating:
- Exact file size (16,777,216 bytes).
- FRBA boundaries, 4KB page alignment, and mathematical non-overlap across SPI regions.
- Restoration of the VSCC table entry at offset `0x0128` to `0x00800000`.
- Soft strap register `PCHSTRP10` at offset `0x0088` with bit 7 set to 1 (`AltMeDisable`).
- Disassembly of `NCT5532DPeiInit` instructions and validity of LPC / Super I/O configuration tables.
- Verification that relocated pointers strictly inhabit PE bounds [ImageBase, ImageBase + SizeOfImage).
- Total eradication of obsolete pointers `0xFFDE5BFE` and `0xFFDE5C17`.
- Integrity of checksums in PE32 OptionalHeader, FFS header, and Firmware Volume container.
- Secondary processor AP reset vector (`EA D0 FF 00 F0...`) at `0x00FFD000`.
- SEC Core entry vector at `0x00FFFFF0`.
- Intel microcode storage blocks and FIT table integrity.
- Unmodified integrity of companion ROM files (`ORIGINAL.rom` and `BiosUpdate.rom`).

To execute the test suite:
```bash
python test_suite.py
```

---

## 7. Credits and References

- Official Intel CPU microcodes: repository [platomav/CPUMicrocodes](https://github.com/platomav/CPUMicrocodes).
- UEFI and FFS structural analysis: `UEFITool` by Nikolaj Schlej.
- Architecture specifications: *Intel C610 Series Chipset and Intel X99 Chipset Datasheet*, *Intel 64 and IA-32 Architectures Software Developer's Manual*, *UEFI Platform Initialization Specification*.
