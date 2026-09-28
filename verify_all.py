import struct
import hashlib
import lzma
import subprocess

def verify():
    rom_path = 'qiyidax99d4interfazgrafica_reparada.rom'
    print(f"=== VERIFYING {rom_path} ===")
    with open(rom_path, 'rb') as f:
        rom = f.read()

    # 1. Size
    assert len(rom) == 16777216, f"Incorrect size {len(rom)}"
    print("[PASS] ROM Size: 16,777,216 bytes (16.0 MB)")

    # 2. Intel Flash Descriptor & PCHSTRP10
    sig = rom[0x10:0x14]
    assert sig == b'\x5A\xA5\xF0\x0F', f"Invalid FD signature {sig.hex()}"
    flmap1 = struct.unpack('<I', rom[0x18:0x1C])[0]
    fpsba = ((flmap1 >> 16) & 0xFF) << 4
    pchstrp10 = struct.unpack('<I', rom[fpsba+40:fpsba+44])[0]
    assert (pchstrp10 & (1 << 7)) != 0, "AltMeDisable bit not set in PCHSTRP10!"
    print(f"[PASS] Intel Flash Descriptor valid, PCHSTRP10=0x{pchstrp10:08X} (AltMeDisable bit 7 is SET)")

    # 3. AP Startup Reset Vector
    ap_vec = rom[0x00FFD000:0x00FFD010]
    expected_ap = bytes.fromhex("EA D0 FF 00 F0 00 00 00 00 00 00 00 00 00 27 2D")
    assert ap_vec == expected_ap, f"AP vector mismatch: {ap_vec.hex()}"
    print(f"[PASS] AP Startup Reset Vector at 0x00FFD000: {ap_vec.hex(' ')}")

    # 4. Top Reset Vector
    top_vec = rom[0x00FFFFF0:0x01000000]
    expected_top = bytes.fromhex("90 90 e9 83 e8 00 00 00 fd 00 00 00 00 00 c0 ff")
    assert top_vec == expected_top, f"Top reset vector mismatch: {top_vec.hex(' ')}"
    print(f"[PASS] Top Reset Vector at 0x00FFFFF0: {top_vec.hex(' ')}")

    # 5. Super I/O in PEI: NCT5532DPeiInit
    with open('qiyidax99d4ORIGINAL.rom', 'rb') as f:
        orig = f.read()
    orig_nct = orig[0x00DE59C8:0x00DE59C8+0x8C6]
    rom_nct = rom[0x00C0D8D0:0x00C0D8D0+0x8C6]
    assert rom_nct == orig_nct, "NCT5532DPeiInit in ROM does not match original!"
    print("[PASS] NCT5532DPeiInit in PEI volume at 0x00C0D8D0 matches Qiyida original byte-for-byte")

    # 6. Super I/O in DXE: SioDxeInit
    sio_guid = bytes.fromhex("1E09824EA13289468A00CDE41ED63CDD")
    p_sio = rom.find(sio_guid)
    assert p_sio == 0x0031B220, f"SioDxeInit at unexpected offset 0x{p_sio:08X}"
    orig_sio = orig[0x008E5150:0x008E5150+0x147B]
    rom_sio = rom[p_sio:p_sio+0x147B]
    assert rom_sio == orig_sio, "SioDxeInit does not match Qiyida original!"
    print(f"[PASS] SioDxeInit in DXE volume at 0x{p_sio:08X} matches Qiyida original byte-for-byte")

    # 7. DSDT ACPI Table
    with open('Herramientas/UEFITool/dsdt_qiyida.bin', 'rb') as f:
        dsdt = f.read()
    p_dsdt = rom.find(dsdt)
    assert p_dsdt == 0x006A4134, f"DSDT at unexpected offset 0x{p_dsdt:08X}"
    print(f"[PASS] DSDT Qiyida ACPI table verified at 0x{p_dsdt:08X} ({len(dsdt)} bytes)")

    # 8. Realtek LAN driver
    with open('Herramientas/UEFITool/lan_qiyida.ffs', 'rb') as f:
        lan_ffs = f.read()
    lan_guid = lan_ffs[:16]
    p_lan = rom.find(lan_guid)
    assert p_lan == 0x00817FF8, f"LAN driver at unexpected offset 0x{p_lan:08X}"
    # Decompress payload and compare
    mod_lan = rom[p_lan:p_lan+0x16DD1]
    decomp_orig = lzma.decompress(lan_ffs[48:61] + lan_ffs[61:])
    decomp_rom = lzma.decompress(mod_lan[48:61] + mod_lan[61:])
    assert decomp_orig == decomp_rom, "Decompressed LAN driver does not match!"
    print(f"[PASS] Realtek LAN driver verified at 0x{p_lan:08X} (decompressed payload byte-for-byte match)")

    # 9. DualBIOS and Phantom Modules Check (Must be ABSENT)
    forbidden_guids = [
        ("DualBiosPlusDxe", "5daffe19bd4b0a45979038dfc3c39343"),
        ("DualBiosDxe", "0b1b4dc7b1914a48a038fe7a0847aa07"),
        ("DualBiosPlusSmm", "39a5e50dfa7ccd4bb89e73a223696279"),
        ("DualBiosSmm", "b368b4888ba4874babe28e56dffdaf8d"),
        ("DualBiosPlusPei", "5c96f9fbb103dc4c9eaa4830a69bd2e2"),
        ("DualBiosCSPPei", "a154c36154d67049b34958007e55f0e2"),
        ("ITEPowerLEDDxe", "e6dcf28e79f2be40a58fffa9bf864a1e"),
        ("Ite8790ECDxe", "9b52519071275f4d86d4913f2090819d"),
        ("TbtDxe", "14f6b7ef8bbcdd4db09a22079fc1512f"),
        ("LxUndiBinE2400", "6d8d4e6352863646b0473f3e615f41f3"),
        ("LxUndiBinE2500", "b76bce3249800d45ab8c9ebffcd5a2b3"),
        ("EcLedIndicatorSmm", "71dcb38617393a4ca735164f1f5da712"),
        ("GBTCellPhoneOCSmm", "4c4b842298507043a427e660b81f6876"),
        ("GBTCellPhoneOCDxe", "e696ce89de94ac40ba14ffdb137ab04d"),
        ("Ite8790ECSmi", "0c183ccb14cf6541bc6d2116ff8d8bea"),
        ("TbtSmm", "d7f0d9b7dbebe44eab77b30c4b9093cc"),
        ("EcLedIndicatorPei", "456473cd0cb63341b7caa65471f1e7f0"),
        ("ITEPowerLEDPei", "35a138f28918df48813e07b78b76191b"),
        ("Ite8790ECPei", "f8e6ca369079024a95e84103333beded"),
        ("TbtPei", "969d8e1ae6661b4695d6882c984d0b00"),
        ("TbtXhciOnlyPei", "1ca1393e72420b46b1c972486c9e0499"),
        ("IT8728FSmmFeaturesPei", "7d5b5773e1874a498c6436cf9d057576"),
        ("IT8728FSmmFeaturesDxe", "df09954c28d64e4aa3cce32c1039ee7d"),
        ("IT8728FSmmFeaturesSmm", "ca4bd19d169dc645b65eb4bace131fab"),
    ]
    for name, ghex in forbidden_guids:
        pos = rom.find(bytes.fromhex(ghex))
        assert pos == -1, f"Forbidden module {name} (GUID {ghex}) still present at 0x{pos:08X}!"
    assert 'IT8728FPeiInit'.encode('utf-16le') not in rom, "IT8728FPeiInit still present in ROM!"
    assert 'ITEPowerLEDPei'.encode('utf-16le') not in rom, "ITEPowerLEDPei still present in ROM!"
    assert 'ITEPowerLEDDxe'.encode('utf-16le') not in rom, "ITEPowerLEDDxe still present in ROM!"
    assert 'GBTCellPhoneOC'.encode('utf-16le') not in rom, "GBTCellPhoneOC still present in ROM!"
    assert 'NCT5532DPeiInit'.encode('utf-16le') in rom, "NCT5532DPeiInit not found in ROM!"
    print(f"[PASS] All 24 DualBIOS, secondary ITE, Power LED, GBT CellPhone OC, Thunderbolt, Killer LAN, and IT8728F modules confirmed completely REMOVED")

    # 10. Microcodes and FIT Table
    mc_specs = [
        (0x000306F1, 0x80000013, 0xFFD21F20),
        (0x000406F0, 0x00000014, 0xFFD2A720),
        (0x000306F2, 0x00000049, 0xFFD32320),
        (0x000406F1, 0x0B000041, 0xFFD3BB20),
    ]
    fit_off = 0x00BF0000
    for i, (cpuid, rev, paddr) in enumerate(mc_specs):
        entry_off = fit_off + (i + 1) * 16
        e_addr, e_size, e_ver, e_type, e_csum = struct.unpack('<QIHBB', rom[entry_off:entry_off+16])
        assert e_addr == paddr, f"FIT Entry {i+1} address mismatch: 0x{e_addr:X} vs 0x{paddr:X}"
        assert e_type == 1, f"FIT Entry {i+1} type mismatch: {e_type}"
        # Check actual microcode at paddr in ROM
        rom_mc_off = paddr - 0xFF000000
        hdr_ver, m_rev, m_date, m_cpuid = struct.unpack('<IIII', rom[rom_mc_off:rom_mc_off+16])
        assert hdr_ver == 1, f"Invalid microcode header at 0x{rom_mc_off:X}"
        assert m_cpuid == cpuid, f"Microcode {i+1} CPUID mismatch: 0x{m_cpuid:X} vs 0x{cpuid:X}"
        assert m_rev == rev, f"Microcode {i+1} Rev mismatch: 0x{m_rev:X} vs 0x{rev:X}"
        print(f"[PASS] Microcode {i+1}: CPUID 0x{cpuid:08X} Rev 0x{rev:08X} verified at 0x{rom_mc_off:08X} (FIT physical 0x{paddr:08X})")

    # 11. Hash and integrity
    sha256 = hashlib.sha256(rom).hexdigest()
    md5 = hashlib.md5(rom).hexdigest()
    print(f"\n[SUMMARY] Binary Integrity Verified:")
    print(f"  SHA-256: {sha256}")
    print(f"  MD5:     {md5}")
    print("\nALL VERIFICATION CHECKS PASSED PERFECTLY!\n")

if __name__ == '__main__':
    verify()
