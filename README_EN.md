# Qiyida X99-D4 (Intel C612 Chipset / LGA2011-3 Socket) - Firmware Repository

[Documentacion en Espanol / Spanish Documentation](README.md)

<p align="center">
  <img src="qiyda-x99-d4-1.jpg" width="650" alt="Qiyida X99-D4 Motherboard">
</p>

Official and modified firmware repository for the Chinese Qiyida X99-D4 motherboard (Revision 2.0 with 10-pin TPM 2.0 header).

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

| File | Size | SHA-256 | Description |
| :--- | :--- | :--- | :--- |
| `qiyidax99d4interfazgrafica_reparada.rom` | 16,777,216 bytes | `f208445b5cfd55b8d171e288f237baae45fc2286d5844f386bbf5c46205a16d3` | Complete 16 MB firmware with Gigabyte UEFI GUI, AltMeDisable mitigation, 2024 microcodes, Nuvoton Super I/O, and Realtek LAN. |
| `qiyidax99d4BiosUpdate.rom` | 16,777,216 bytes | `0bca95f4869ecdbbeac3d4d528b34063697dea17473a2a0adf2162ed77284b45` | Production-grade firmware based on factory BIOS with 2024 microcodes (Haswell rev 49, Broadwell rev 41). Flashed via software using `fptw64 -bios`. |
| `qiyidax99d4ORIGINAL.rom` | 16,777,216 bytes | `0220fc2e42061ebde1634f231a52951631fc64e015770ba5fdd140e00b5e32d1` | Untouched factory flash dump (Intel SPS 3.1.3.72, 8 MB BIOS region). |
| `X99UG.F7c` | 16,777,216 bytes | `90818dd14d621360badea1463f975a367952e2a0d43e7dc73401a7ab0a2d3a1f` | Original donor firmware from Gigabyte GA-X99-Ultra Gaming (F7c). |

---

## 3. Reverse Engineering and Structural Firmware Fixes

The preliminary experimental mod (`qiyidax99d4interfazgraficamodbeta.rom`) suffered from critical architectural faults that prevented booting on physical hardware. In `qiyidax99d4interfazgrafica_reparada.rom`, the following low-level defects have been resolved:

### 3.1 Multi-Processor Startup Reset Vector Restoration (Offset `0x00FFD000`)
In the preliminary mod, the UEFITool rebuild process zeroed the padding block at `0x00FFD000` with flat `0xFF` bytes, obliterating the secondary processor reset hook.
- **Failure mechanics:** When the Bootstrap Processor (BSP) issues a Startup IPI (SIPI, vector `0xFD`), the secondary Application Processors (APs) begin executing at physical real-mode address `0xFD000` (mapped to flash offset `0x00FFD000`). Encountering `0xFF 0xFF`, the CPU triggers an invalid opcode exception (`#UD`) without an active IDT, causing an instantaneous Triple Fault before completing the PEI phase.
- **Fix applied:** Restored the 16-bit real-mode far jump instruction:
  ```assembly
  EA D0 FF 00 F0 00 00 00 00 00 00 00 00 00 27 2D  ; jmp far F000:FFD0
  ```
  This vectors execution to `0x00FFFFD0` in the SEC Core, enabling transition into 32-bit protected mode across all Xeon cores.

### 3.2 Super I/O Architecture (Nuvoton NCT5532D / NCT6779)
- **Silicon identification:** The physical IC soldered to the PCB is a compact 64-pin LQFP package (7 mm x 7 mm, 16 pins per side). Interrogating register `0x20` (Chip ID High = `0xC5`) and register `0x21` (Chip ID Low/Rev = `0x62` or `0x63`) under the family bitmask `0xFFF8` returns Device ID `0xC560`. In industry hardware databases (CPUID, CPU-Z, HWMonitor, Linux `nct6775` driver), `0xC560` is mapped under the family flagship name: `Nuvoton NCT6779`. The internal silicon registers and logical architecture are identical.
- **PEI phase fix:** The Gigabyte base firmware included `IT8728FPeiInit`, which transmitted ITE unlock sequences (`87 01 55 55`), keeping the LPC bus unresponsive. This module was removed and replaced at `0x00C0D8D0` with Qiyida's official driver: `NCT5532DPeiInit` (`9029F23E-E1EE-40D1-9382-36DD61A63EAA`).
- **PCH C612 LPC decoding:** The driver configures three LPC decode windows on the PCH:
  - Range 1: Base `0x002E` (Super I/O Index/Data).
  - Range 2: Base `0x0060` (PS/2 Keyboard and Mouse on `0x60/0x64`).
  - Range 3: Base `0x0A00` with 64-byte window (`0x0A00..0x0A3F` for Hardware Monitor registers).
  - Issues Nuvoton unlock key `0x87, 0x87` and enables KBC (Logical Device 05).
- **DXE phase:** Verified `SioDxeInit` (`4E82091E-32A1-4689-8A00-CDE41ED63CDD`) at `0x0031B220`, publishing the standard `EFI_SIO_PROTOCOL` for UART COM1 (`0x3F8`, IRQ 4) and hardware monitoring.

### 3.3 Mitigation of the 30-Minute Intel ME Watchdog Shutdown
- **Root cause:** The Qiyida board utilizes a server Intel C612 PCH (Wellsburg-G), built to run Intel Server Platform Services (SPS 3.1). Loading Gigabyte's consumer UEFI image (designed for consumer Intel ME 9.1/10.0) causes HECI communication failures against server PCH silicon fuses. Consequently, the Intel ME Watchdog Timer forces an unconditional system shutdown at precisely 30 minutes of runtime.
- **Fix applied:** Modified soft strap register `PCHSTRP10` in the Intel Flash Descriptor (offset `0x0128`), setting bit 7 (`AltMeDisable = 1`):
  ```text
  Offset 0x0128: 00 00 80 00 -> 80 00 80 00
  ```
  This instructs the Intel ME coprocessor to halt cleanly following fundamental PCH clock generation, neutralizing the watchdog timer.

### 3.4 Removal of 24 Extraneous Gigabyte Modules
To eliminate POST delays and bus hangs caused by polling hardware absent on the Qiyida PCB, 24 proprietary Gigabyte modules were cleanly excised and replaced with compliant UEFI PAD files:
1. **Gigabyte DualBIOS (6 modules):** `DualBiosCSPPei`, `DualBiosPlusPei`, `DualBiosDxe`, `DualBiosPlusDxe`, `DualBiosSmm`, `DualBiosPlusSmm`. Prevents bootloops triggered by searching for a secondary physical SPI chip.
2. **Intel Thunderbolt Alpine Ridge (4 modules):** `TbtPei`, `TbtXhciOnlyPei`, `TbtDxe`, `TbtSmm`.
3. **Secondary ITE EC 8790 Controller (3 modules):** `Ite8790ECPei`, `Ite8790ECDxe`, `Ite8790ECSmi`.
4. **ITE LED and Illumination Drivers (4 modules):** `ITEPowerLEDPei`, `ITEPowerLEDDxe`, `EcLedIndicatorPei`, `EcLedIndicatorSmm`.
5. **Gigabyte CellPhone OC (2 modules):** `GBTCellPhoneOCDxe`, `GBTCellPhoneOCSmm`.
6. **Killer Network Drivers (2 modules):** `LxUndiBinE2400`, `LxUndiBinE2500`.
7. **ITE 8728 SMM Features (3 modules):** `IT8728FSmmFeaturesPei`, `IT8728FSmmFeaturesDxe`, `IT8728FSmmFeaturesSmm`.

### 3.5 ACPI DSDT and Realtek LAN Injection
- **DSDT:** Injected Qiyida's verified ACPI table (`dsdt_qiyida.bin`, 210,878 bytes) at `0x006A4134`, establishing physical routing for USB 2.0/3.0 ports, PCIe lane allocation, Super I/O on `0x2E/0x2F`, and 192 logical processor declarations.
- **LAN:** Confirmed the Realtek RTL8111H UEFI UNDI Option ROM driver (`lan_qiyida.ffs`) at `0x00817FF8`.

### 3.6 Official 2024 Intel Microcodes and FIT Table Reconstruction
Updated the microcode storage volume and rebuilt the Firmware Interface Table (FIT, offset `0x00BF0000`):

| CPUID | Stepping / Processor | Revision | Date | Security Mitigations |
| :---: | :--- | :---: | :---: | :--- |
| `306F1` | Haswell-EP (Engineering Sample ES) | `80000013` | 2013-10-02 | ES CPU compatibility |
| `406F0` | Broadwell-EP (Engineering Sample ES) | `00000014` | 2015-07-02 | ES CPU compatibility |
| `306F2` | **Haswell-EP Commercial (Xeon E5 v3)** | **`49`** | 2021-08-11 | Downfall (GDS), CrossTalk / SRBDS, MDS, MMIO Stale Data |
| `406F1` | **Broadwell-EP Commercial (Xeon E5 v4)** | **`41`** | 2024-02-16 | Register File Data Sampling (RFDS 2024), Downfall (GDS), MDS |

---

## 4. Flash Protection Analysis and Debunking the Audio Pinmod Myth

In online modding communities, it is often asserted that paperclip pinmodding the Realtek audio chip for 3 seconds is mandatory to flash Chinese X99 boards using `fptw64.exe`. **This is unnecessary on the Qiyida X99-D4**.

### 4.1 Intel Flash Descriptor Factory Privileges
On retail branded motherboards (ASUS, MSI, Gigabyte), the Flash Master 1 register (`FLMSTR1`) is factory-locked to `0x00020000`, blocking host CPU write access to the Descriptor and ME regions (`Error 26`).
On the factory Qiyida X99-D4 BIOS ([qiyidax99d4ORIGINAL.rom](file:///c:/Users/Benja/Desktop/Qiyida-x99-D4-BIOS-UPDATE-TPM-10-PIN-VERSION--main/qiyidax99d4ORIGINAL.rom), offset `0x0060`), `FLMSTR1` is configured from the factory as:
```text
FLMSTR1 = 0xFFFF0000
Bits [23:16] Read Access  = 0xFF (Full read access across all regions)
Bits [31:24] Write Access = 0xFF (Full write access granted across all regions)
```
The PCH hardware grants full read and write access to the CPU by default.

### 4.2 Factory NVRAM Protection Variables
- **`BIOS Lock`** (PCH register `BC` bits `BLE` / `SMM_BWP`): Set to **`Disabled (0)`** by default in factory NVRAM. The SMM driver `PchBiosWriteProtect` registers no SMI write-protection handler.
- **`Host Flash Lock-Down`** (`FLOCKDN`): Set to **`Disabled (0)`** by default.
- **`Flash Protected Range Registers`** (`FPRR`): Inactive.

---

## 5. Flashing and Installation Procedures

### Method 1: Software Flashing from Windows via Intel FPT (No External Hardware)
To flash the full 16 MB image containing the graphical UEFI interface (`qiyidax99d4interfazgrafica_reparada.rom`), use the native Intel ME protection override exposed in the factory BIOS:

1. **Enter the BIOS:** Power on the machine and tap `Del`.
2. **Enable Intel ME Reflash Mode:**
   - Navigate to the **`IntelRCSetup`** tab.
   - Enter **`Server ME Configuration`**.
   - Enter **`Manageability Application Configuration`**.
   - Set **`Me FW Image Re-Flash`** from `Disabled` to **`Enabled`**.
   - Press `F4` (Save & Exit).
3. **Automatic Reboot:** The machine will reboot. During POST, the `MeFwDowngrade` driver executes `HMRFPO_ENABLE` and triggers a cold reset. The system boots with Intel ME write restrictions removed.
4. **Flash in Windows:**
   - Log into Windows.
   - Open Command Prompt (`cmd.exe`) or PowerShell with **Administrator privileges** in the repository directory.
   - Execute the 16 MB full-chip flash:
     ```cmd
     fptw64.exe -f qiyidax99d4interfazgrafica_reparada.rom
     ```
   - FPT will erase, write, and verify all flash regions (`FPT Operation Successful`).
5. **Mandatory Clear CMOS:**
   - Shut down the PC completely and unplug the power supply cable from the AC outlet.
   - Remove the CR2032 lithium battery for 5 minutes to clear obsolete NVRAM configuration tokens.
   - Reinsert the battery and power on: the board will initialize natively into the Gigabyte graphical UEFI interface.

---

### Method 2: External SPI Hardware Programmer (CH341A)
Recommended for recovery or as a zero-risk fail-safe procedure:
1. Connect the USB CH341A programmer with an SOIC-8 test clip to the motherboard SPI flash chip (ensure the computer power supply is disconnected from AC power).
2. Open **NeoProgrammer** or **AsProgrammer**.
3. Detect the 16 MB SPI flash IC (Winbond W25Q128 or equivalent).
4. Perform a full backup read (`Read IC`) and save the file (`backup_factory.bin`).
5. Load `qiyidax99d4interfazgrafica_reparada.rom`.
6. Run: `Erase IC` -> `Write IC` -> `Verify IC`.
7. Remove the test clip, perform a 5-minute Clear CMOS (removing the CR2032 battery), and boot the system.

---

### Method 3: Official 2024 Microcode Update Alone (`qiyidax99d4BiosUpdate.rom`)
If you only wish to apply the 2024 microcodes onto the factory text-mode BIOS without modifying the GUI or 8 MB factory layout:
```cmd
fptw64.exe -bios -f qiyidax99d4BiosUpdate.rom
```
Does not require BIOS setting adjustments or ME region flashing.

---

## 6. Build and Verification Tooling

The repository provides automated scripts to inspect and rebuild the firmware:

- **`verify_all.py`:** Comprehensive forensic test suite. Verifies the exact 16,777,216-byte size, validates the AP reset vector at `0x00FFD000`, confirms `PCHSTRP10` bit 7 (`AltMeDisable`), asserts absence of all 24 extraneous modules, and parses all FIT table microcode pointers.
  ```cmd
  python verify_all.py
  ```
- **`build_repaired_rom.py`:** Python script executing clean, byte-accurate reconstruction of the image from verified modules and standard UEFI padding structures.
  ```cmd
  python build_repaired_rom.py
  ```

---

## 7. Credits and Technical References
- CPU Microcodes: official Intel repository maintained by [platomav/CPUMicrocodes](https://github.com/platomav/CPUMicrocodes).
- Firmware Structural Analysis Tools: `UEFITool` and `UEFIExtract` by Nikolaj Schlej.
- Architecture References: *Intel C610 Series Chipset and Intel X99 Chipset Datasheet*, *Intel 64 and IA-32 Architectures Software Developer's Manual*.
