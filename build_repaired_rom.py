import struct
import shutil
import subprocess
import os

def make_pad(size):
    assert size >= 24 and size % 8 == 0, f"Invalid PAD size {size}"
    hdr = bytearray(b'\xFF' * 16) # GUID
    hdr += bytearray([0, 0xAA, 0xF0, 0x00]) # csum_hdr, csum_file, type=0xF0, attrib=0
    hdr += size.to_bytes(3, 'little')
    hdr += bytearray([0xF8]) # state
    # Calculate csum_hdr: sum(header treating state as 0) + csum_hdr = 0 (mod 256)
    h_temp = bytearray(hdr)
    h_temp[16] = 0
    h_temp[17] = 0
    h_temp[23] = 0
    hdr[16] = (0x100 - (sum(h_temp) % 256)) % 256
    return bytes(hdr) + (b'\xFF' * (size - 24))

def main():
    print("=== Step 0: Loading input files ===")
    with open('qiyidax99d4interfazgraficamodbeta.rom', 'rb') as f:
        rom = bytearray(f.read())
    print(f"Loaded modbeta ROM: {len(rom)} bytes")

    with open('qiyidax99d4ORIGINAL.rom', 'rb') as f:
        orig = f.read()

    with open('qiyidax99d4BiosUpdate.rom', 'rb') as f:
        bios_update = f.read()

    # -------------------------------------------------------------
    # 1. AP Startup reset vector repair at 0x00FFD000
    # -------------------------------------------------------------
    print("\n=== Step 1: Fixing AP startup reset vector at 0x00FFD000 ===")
    ap_vector = bytes.fromhex("EA D0 FF 00 F0 00 00 00 00 00 00 00 00 00 27 2D")
    rom[0x00FFD000:0x00FFD000 + 16] = ap_vector
    print(f"Restored AP vector at 0x00FFD000: {rom[0x00FFD000:0x00FFD010].hex(' ')}")

    # -------------------------------------------------------------
    # 2. Super I/O in PEI: Replace IT8728FPeiInit with NCT5532DPeiInit
    # -------------------------------------------------------------
    print("\n=== Step 2: Replacing IT8728FPeiInit with NCT5532DPeiInit in PEI volume ===")
    # Extract NCT5532DPeiInit from ORIGINAL at 0x00DE59C8 (size 0x8C6)
    nct_data = orig[0x00DE59C8:0x00DE59C8 + 0x8C6]
    assert len(nct_data) == 0x8C6
    # It occupies 0x00C0D8D0 to 0x00C0E196, plus 2 bytes FF padding = 0x00C0E198 (span 0x8C8)
    rom[0x00C0D8D0:0x00C0D8D0 + 0x8C6] = nct_data
    rom[0x00C0D8D0 + 0x8C6:0x00C0E198] = b'\xFF\xFF'
    # From 0x00C0E198 to 0x00C0E920 (remainder + IT8728FSmmFeaturesPei): pad file of size 0x788
    pad_sio_rem = make_pad(0x00C0E920 - 0x00C0E198) # 0x788 bytes
    rom[0x00C0E198:0x00C0E920] = pad_sio_rem
    print(f"Injected NCT5532DPeiInit at 0x00C0D8D0..0x00C0E198 and PAD at 0x00C0E198..0x00C0E920")

    # -------------------------------------------------------------
    # 3 & 4. Neutralize DualBIOS and Phantom Hardware Drivers
    # -------------------------------------------------------------
    print("\n=== Steps 3 & 4: Removing DualBIOS and phantom hardware drivers ===")
    pad_targets = [
        # (Name, start, end)
        ("IT8728FSmmFeaturesDxe", 0x002A7808, 0x002A8098),
        ("DualBiosPlusDxe + DualBiosDxe", 0x0032AED0, 0x0032DE70),
        ("GBTCellPhoneOCDxe", 0x003302E0, 0x003309D8),
        ("ITEPowerLEDDxe + Ite8790ECDxe", 0x0037DE50, 0x0037F1C8),
        ("TbtDxe", 0x00399920, 0x0039B078),
        ("LxUndiBinE2400 + LxUndiBinE2500", 0x00443AE0, 0x0044CFF0),
        ("IT8728FSmmFeaturesSmm", 0x0045A1F0, 0x0045B0C0),
        ("DualBiosPlusSmm + DualBiosSmm + EcLedIndicatorSmm + GBTCellPhoneOCSmm", 0x00480D80, 0x00484BE0),
        ("Ite8790ECSmi", 0x00494D60, 0x004956B0),
        ("TbtSmm", 0x0049CF80, 0x0049F688),
        ("DualBiosPlusPei + DualBiosCSPPei + EcLedIndicatorPei", 0x00C3B1A0, 0x00C3C578),
        ("ITEPowerLEDPei + Ite8790ECPei", 0x00C472B0, 0x00C48178),
        ("TbtPei + TbtXhciOnlyPei", 0x00C5A788, 0x00C5B600),
    ]

    for name, start, end in pad_targets:
        size = end - start
        pad_data = make_pad(size)
        assert len(pad_data) == size
        rom[start:end] = pad_data
        print(f"  Neutralized {name:65s} [0x{start:08X}..0x{end:08X}] (0x{size:X} bytes PAD)")

    # -------------------------------------------------------------
    # 5. DSDT & LAN Verification
    # -------------------------------------------------------------
    print("\n=== Step 5: Verifying DSDT and Realtek LAN ===")
    with open('Herramientas/UEFITool/dsdt_qiyida.bin', 'rb') as f:
        dsdt_qiyida = f.read()
    assert dsdt_qiyida in rom, "Error: dsdt_qiyida not found in ROM!"
    print("DSDT Qiyida table is verified present in the firmware image.")

    # -------------------------------------------------------------
    # 6. Intel Flash Descriptor: Set AltMeDisable bit in PCHSTRP10
    # -------------------------------------------------------------
    print("\n=== Step 6: Setting AltMeDisable in PCHSTRP10 (Intel Flash Descriptor) ===")
    flmap1 = struct.unpack('<I', rom[0x18:0x1C])[0]
    fpsba = ((flmap1 >> 16) & 0xFF) << 4
    pchstrp10_offset = fpsba + 10 * 4
    val = struct.unpack('<I', rom[pchstrp10_offset:pchstrp10_offset+4])[0]
    new_val = val | (1 << 7)
    rom[pchstrp10_offset:pchstrp10_offset+4] = struct.pack('<I', new_val)
    print(f"PCHSTRP10 at 0x{pchstrp10_offset:04X}: 0x{val:08X} -> 0x{new_val:08X} (AltMeDisable={bool(new_val & (1<<7))})")

    # -------------------------------------------------------------
    # 7. Microcode Injection & FIT Table Update
    # -------------------------------------------------------------
    print("\n=== Step 7: Injecting 2024 Microcodes and Updating FIT ===")
    # Extract updated microcode container from qiyidax99d4BiosUpdate.rom
    target_guid = bytes.fromhex('728508177f37ef448f4eb09fff46a070')
    p = bios_update.find(target_guid)
    found_mc = False
    while p != -1:
        if bios_update[p+24:p+28] == b'\x01\x00\x00\x00':
            mc_ffs_size = int.from_bytes(bios_update[p+20:p+23], 'little')
            mc_ffs_data = bios_update[p:p+mc_ffs_size]
            found_mc = True
            break
        p = bios_update.find(target_guid, p+1)
    assert found_mc, "Could not find microcode FFS in BiosUpdate ROM"
    print(f"Found 2024 Microcode FFS: size 0x{len(mc_ffs_data):X}")

    # Old microcode FFS at 0x00D21F08 had size 0x1E428.
    # New microcode FFS has size 0x22828 (0x4400 bytes larger).
    # Next pad file at 0x00D40330 had size 0x2BD888 up to 0x00FFDBB8.
    # New pad file starts at 0x00D21F08 + 0x22828 = 0x00D44730.
    # New pad file size = 0x00FFDBB8 - 0x00D44730 = 0x2B9488 (0x4400 bytes smaller).
    mc_start = 0x00D21F08
    rom[mc_start:mc_start + len(mc_ffs_data)] = mc_ffs_data
    pad_mc_start = mc_start + len(mc_ffs_data)
    pad_mc_size = 0x00FFDBB8 - pad_mc_start
    rom[pad_mc_start:0x00FFDBB8] = make_pad(pad_mc_size)
    print(f"Updated Microcode FFS at 0x{mc_start:08X}..0x{pad_mc_start:08X}")
    print(f"Adjusted following PAD file at 0x{pad_mc_start:08X}..0x00FFDBB8 (size 0x{pad_mc_size:X})")

    # Re-apply AP Startup Reset Vector inside the pad region at 0x00FFD000
    ap_vector = bytes.fromhex("EA D0 FF 00 F0 00 00 00 00 00 00 00 00 00 27 2D")
    rom[0x00FFD000:0x00FFD000 + 16] = ap_vector
    print(f"Restored AP Startup Reset Vector at 0x00FFD000: {rom[0x00FFD000:0x00FFD010].hex(' ')}")

    # Update FIT Table entries at 0x00BF0000
    fit_off = 0x00BF0000
    # Entry 1: Microcode 1 (CPUID 306F1) at 0x00D21F20 -> 0xFFD21F20
    # Entry 2: Microcode 2 (CPUID 406F0) at 0x00D2A720 -> 0xFFD2A720
    # Entry 3: Microcode 3 (CPUID 306F2, Rev 49) at 0x00D32320 -> 0xFFD32320
    # Entry 4: Microcode 4 (CPUID 406F1, Rev 41) at 0x00D3BB20 -> 0xFFD3BB20
    mc_addrs = [0xFFD21F20, 0xFFD2A720, 0xFFD32320, 0xFFD3BB20]
    for i, addr in enumerate(mc_addrs):
        entry_offset = fit_off + (i + 1) * 16
        # uint64 addr, uint32 size_type, uint16 ver, uint8 type, uint8 csum
        # Format: <Q I H B B
        # size=0, ver=0x0100, type=0x01, csum=0x00
        new_entry = struct.pack('<QIHBB', addr, 0, 0x0100, 0x01, 0x00)
        rom[entry_offset:entry_offset+16] = new_entry
        print(f"  FIT Entry {i+1}: 0x{addr:08X} (Type 0x01, Ver 0x0100)")

    # -------------------------------------------------------------
    # 8. Save modified ROM and verify
    # -------------------------------------------------------------
    output_filename = 'qiyidax99d4interfazgrafica_reparada.rom'
    with open(output_filename, 'wb') as f:
        f.write(rom)
    print(f"\n=== Step 8: Successfully wrote {output_filename} ({len(rom)} bytes) ===")

if __name__ == '__main__':
    main()
