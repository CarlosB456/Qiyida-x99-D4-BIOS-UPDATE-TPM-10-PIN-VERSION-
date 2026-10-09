#!/usr/bin/env python3
"""
Comprehensive Test Suite for qiyidax99d4interfazgraficamodbeta.rom.

Verifies structural integrity, silicon requirements, and firmware repairs:
1. Exact ROM File Size (16,777,216 bytes).
2. Intel Flash Descriptor FRBA boundaries, 4KB page alignment, & elimination of illegal region overlaps.
3. VSCC Table restoration at offset 0x0128 (restored to 0x00800000).
4. PCHSTRP10 soft strap at offset 0x0088 with AltMeDisable (bit 7 set).
5. NCT5532DPeiInit relocation, instruction disassembly, and verification of non-0xFF data tables.
6. Verification that target pointers reside strictly within PE Image bounds (ImageBase <= ptr < ImageBase + SizeOfImage).
7. Verification that old broken pointers (0xFFDE5BFE, 0xFFDE5C17) are completely eradicated from NCT5532D.
8. Checksum validity across PE32, FFS File Header, and Firmware Volume Header.
9. AP Multi-Processor Reset Vector at 0x00FFD000.
10. SEC Core Reset Vector at 0x00FFFFF0.
11. Microcode storage blocks and Firmware Interface Table (FIT) integrity.
12. Integrity of companion firmware images (ORIGINAL.rom and BiosUpdate.rom).
13. SHA-256 cryptographic digest match.
"""

import unittest
import hashlib
from pathlib import Path

ROM_PATH = Path("qiyidax99d4interfazgraficamodbeta.rom")
ORIG_PATH = Path("qiyidax99d4ORIGINAL.rom")
BIOS_UPD_PATH = Path("qiyidax99d4BiosUpdate.rom")

EXPECTED_SIZE = 16777216  # 16 MB
EXPECTED_MODBETA_SHA256 = "a9e80340da0f68bb8548216cfb8aec76fd5b9d8a1d8b0bd6787533f201a36437"
EXPECTED_ORIG_SHA256 = "0220fc2e42061ebde1634f231a52951631fc64e015770ba5fdd140e00b5e32d1"
EXPECTED_BIOS_UPD_SHA256 = "0bca95f4869ecdbbeac3d4d528b34063697dea17473a2a0adf2162ed77284b45"

class TestQiyidaRomRepairs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assertTrue(cls, ROM_PATH.exists(), f"ROM file not found: {ROM_PATH}")
        cls.rom = ROM_PATH.read_bytes()

    def test_01_exact_file_size(self):
        """ROM must be exactly 16,777,216 bytes (16 MB / 128 Mb SPI flash)."""
        self.assertEqual(len(self.rom), EXPECTED_SIZE,
                         f"ROM size is {len(self.rom)} bytes, expected exactly {EXPECTED_SIZE}")

    def test_02_flash_descriptor_signature(self):
        """Intel Flash Descriptor must have valid signature 0x0FF0A55A at offset 0x10."""
        sig = int.from_bytes(self.rom[0x10:0x14], "little")
        self.assertEqual(sig, 0x0FF0A55A, f"Invalid IFD signature: 0x{sig:08X}")

    def test_03_frba_boundaries_and_no_overlap(self):
        """FRBA Region 1 (BIOS) must start at 0x00200000, align to 4KB, and not overlap other regions."""
        flmap0 = int.from_bytes(self.rom[0x14:0x18], "little")
        frba_offset = (flmap0 >> 12) & 0x0FF0
        self.assertEqual(frba_offset, 0x0040, f"Expected FRBA offset 0x0040, got 0x{frba_offset:04X}")

        # Region 0 (Descriptor): 0x0040
        reg0 = int.from_bytes(self.rom[frba_offset:frba_offset + 4], "little")
        reg0_base = (reg0 & 0x1FFF) << 12
        reg0_limit = (((reg0 >> 16) & 0x1FFF) << 12) | 0xFFF

        # Region 1 (BIOS): 0x0044
        reg1 = int.from_bytes(self.rom[frba_offset + 4:frba_offset + 8], "little")
        reg1_base = (reg1 & 0x1FFF) << 12
        reg1_limit = (((reg1 >> 16) & 0x1FFF) << 12) | 0xFFF

        # Region 2 (ME): 0x0048
        reg2 = int.from_bytes(self.rom[frba_offset + 8:frba_offset + 12], "little")
        reg2_base = (reg2 & 0x1FFF) << 12
        reg2_limit = (((reg2 >> 16) & 0x1FFF) << 12) | 0xFFF

        # Region 3 (GbE): 0x004C
        reg3 = int.from_bytes(self.rom[frba_offset + 12:frba_offset + 16], "little")
        reg3_base = (reg3 & 0x1FFF) << 12
        reg3_limit = (((reg3 >> 16) & 0x1FFF) << 12) | 0xFFF

        # Assert raw bytes at 0x0044: must be 00 02 ff 0f (0x0FFF0200)
        reg1_raw = self.rom[0x44:0x48]
        self.assertEqual(reg1_raw, bytes.fromhex("0002ff0f"),
                         f"FRBA Region 1 raw bytes at 0x44 are {reg1_raw.hex()}, expected 0002ff0f")

        # 4KB SPI page alignment checks
        self.assertEqual(reg0_base % 4096, 0)
        self.assertEqual((reg0_limit + 1) % 4096, 0)
        self.assertEqual(reg1_base % 4096, 0)
        self.assertEqual((reg1_limit + 1) % 4096, 0)
        self.assertEqual(reg2_base % 4096, 0)
        self.assertEqual((reg2_limit + 1) % 4096, 0)
        self.assertEqual(reg3_base % 4096, 0)
        self.assertEqual((reg3_limit + 1) % 4096, 0)

        # Base and limit values
        self.assertEqual(reg0_base, 0x00000000)
        self.assertEqual(reg0_limit, 0x00000FFF)

        self.assertEqual(reg3_base, 0x00001000)
        self.assertEqual(reg3_limit, 0x00002FFF)

        self.assertEqual(reg2_base, 0x00003000)
        self.assertEqual(reg2_limit, 0x001FFFFF)

        self.assertEqual(reg1_base, 0x00200000, "BIOS Region 1 Base must be 0x00200000 (14 MB BIOS)")
        self.assertEqual(reg1_limit, 0x00FFFFFF, "BIOS Region 1 Limit must be 0x00FFFFFF (top of 16 MB flash)")

        # Verify strict non-overlapping active boundaries
        self.assertGreaterEqual(reg3_base, reg0_limit + 1, "GbE overlaps Descriptor")
        self.assertGreaterEqual(reg2_base, reg3_limit + 1, "ME overlaps GbE")
        self.assertGreaterEqual(reg1_base, reg2_limit + 1, "BIOS overlaps ME region")

    def test_04_vscc_table_restoration(self):
        """Offset 0x0128 in VSCC table must be 00 00 80 00 (0x00800000)."""
        vscc_bytes = self.rom[0x0128:0x012C]
        self.assertEqual(vscc_bytes, bytes.fromhex("00008000"),
                         f"VSCC at 0x0128 is {vscc_bytes.hex()}, expected 00008000 (0x00800000)")
        vscc_val = int.from_bytes(vscc_bytes, "little")
        self.assertEqual(vscc_val, 0x00800000)

    def test_05_pchstrp10_altmedisable(self):
        """PCHSTRP10 at offset 0x0088 must have AltMeDisable (bit 7) set to 1."""
        strap_byte = self.rom[0x0088]
        self.assertTrue(bool(strap_byte & 0x80),
                        f"Bit 7 of PCHSTRP10 at offset 0x0088 is not set: byte is 0x{strap_byte:02X}")

    def test_06_nct5532d_pei_relocation_and_pointers(self):
        """NCT5532DPeiInit must have pointers relocated to 0xFFC0DB06 and 0xFFC0DB1F."""
        guid_expected = bytes.fromhex("3ef22990eee1d140938236dd61a63eaa")
        ffs_hdr = self.rom[0x00C0D8D0:0x00C0D8D0 + 16]
        self.assertEqual(ffs_hdr, guid_expected, "NCT5532DPeiInit GUID mismatch at 0x00C0D8D0")

        pe_base = 0x00C0D904
        self.assertEqual(self.rom[pe_base:pe_base + 2], b"MZ", "DOS header magic missing at PE base")

        ptr1_bytes = self.rom[0x00C0DC15:0x00C0DC19]
        self.assertEqual(ptr1_bytes, bytes.fromhex("06dbc0ff"),
                         f"Pointer 1 at 0x00C0DC15 is {ptr1_bytes.hex()}, expected 06dbc0ff (0xFFC0DB06)")
        ptr1_val = int.from_bytes(ptr1_bytes, "little")
        self.assertEqual(ptr1_val, 0xFFC0DB06)

        ptr2_bytes = self.rom[0x00C0DC36:0x00C0DC3A]
        self.assertEqual(ptr2_bytes, bytes.fromhex("1fdbc0ff"),
                         f"Pointer 2 at 0x00C0DC36 is {ptr2_bytes.hex()}, expected 1fdbc0ff (0xFFC0DB1F)")
        ptr2_val = int.from_bytes(ptr2_bytes, "little")
        self.assertEqual(ptr2_val, 0xFFC0DB1F)

    def test_07_nct5532d_pei_instruction_disassembly(self):
        """Disassembled instructions at 0xFFC0DC14 and 0xFFC0DC35 must load the valid data tables."""
        try:
            import capstone
            pe_base = 0x00C0D904
            code = self.rom[pe_base + 0x310:pe_base + 0x340]
            md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
            disasm = list(md.disasm(code, 0xFFC0D904 + 0x310))

            mov_esi = [ins for ins in disasm if ins.mnemonic == "mov" and "esi" in ins.op_str and "0xffc0db06" in ins.op_str.lower()]
            mov_ecx = [ins for ins in disasm if ins.mnemonic == "mov" and "ecx" in ins.op_str and "0xffc0db1f" in ins.op_str.lower()]

            self.assertTrue(len(mov_esi) >= 1, "Failed to find 'mov esi, 0xffc0db06' in disassembly")
            self.assertTrue(len(mov_ecx) >= 1, "Failed to find 'mov ecx, 0xffc0db1f' in disassembly")
        except ImportError:
            self.assertEqual(self.rom[0x00C0DC14:0x00C0DC19], bytes.fromhex("be06dbc0ff"))
            self.assertEqual(self.rom[0x00C0DC35:0x00C0DC3A], bytes.fromhex("b91fdbc0ff"))

    def test_08_nct5532d_target_data_tables_validity(self):
        """Data tables pointed to by relocated registers must contain valid Super I/O / LPC configs and NOT 0xFF."""
        # Target table 1 at ROM offset 0x00C0DB04 (memory 0xFFC0DB04)
        lpc_table = self.rom[0x00C0DB04:0x00C0DB04 + 24]
        self.assertNotEqual(lpc_table, b"\xFF" * 24, "LPC decode table contains uninitialized 0xFF padding")

        port0 = int.from_bytes(lpc_table[0:2], "little")
        len0 = lpc_table[2]
        self.assertEqual(port0, 0x002E, f"Expected Range 0 BasePort 0x002E, got 0x{port0:04X}")
        self.assertEqual(len0, 0x02, f"Expected Range 0 Len 2, got {len0}")

        port1 = int.from_bytes(lpc_table[8:10], "little")
        self.assertEqual(port1, 0x0060, f"Expected Range 1 BasePort 0x0060, got 0x{port1:04X}")

        port2 = int.from_bytes(lpc_table[16:18], "little")
        len2 = lpc_table[18]
        self.assertEqual(port2, 0x0A00, f"Expected Range 2 BasePort 0x0A00, got 0x{port2:04X}")
        self.assertEqual(len2, 0x40, f"Expected Range 2 Len 0x40, got 0x{len2:02X}")

        # Target table 2 at ROM offset 0x00C0DB1C (memory 0xFFC0DB1C)
        sio_init_table = self.rom[0x00C0DB1C:0x00C0DB1C + 8]
        self.assertNotEqual(sio_init_table, b"\xFF" * 8, "Super I/O config table contains uninitialized 0xFF padding")
        self.assertEqual(sio_init_table[0:4], bytes.fromhex("2e000087"), "First unlock key must write 0x87 to port 0x2E")
        self.assertEqual(sio_init_table[4:8], bytes.fromhex("2e000087"), "Second unlock key must write 0x87 to port 0x2E")

    def test_09_pointers_within_pe_bounds(self):
        """Pointers must reside within the PE image boundaries [ImageBase, ImageBase + SizeOfImage)."""
        pe_base = 0x00C0D904
        e_lfanew = int.from_bytes(self.rom[pe_base + 0x3C:pe_base + 0x40], "little")
        opt_hdr = pe_base + e_lfanew + 24
        img_base = int.from_bytes(self.rom[opt_hdr + 28:opt_hdr + 32], "little")
        size_of_image = int.from_bytes(self.rom[opt_hdr + 56:opt_hdr + 60], "little")

        ptr1 = int.from_bytes(self.rom[0x00C0DC15:0x00C0DC19], "little")
        ptr2 = int.from_bytes(self.rom[0x00C0DC36:0x00C0DC3A], "little")

        self.assertGreaterEqual(ptr1, img_base, "Pointer 1 points below ImageBase")
        self.assertLess(ptr1, img_base + size_of_image, "Pointer 1 points beyond SizeOfImage")

        self.assertGreaterEqual(ptr2, img_base, "Pointer 2 points below ImageBase")
        self.assertLess(ptr2, img_base + size_of_image, "Pointer 2 points beyond SizeOfImage")

    def test_10_eradication_of_broken_pointers(self):
        """Old broken pointers (0xFFDE5BFE, 0xFFDE5C17) must not exist in NCT5532D module."""
        pe_base = 0x00C0D904
        pe_len = 0x860
        pe_code = self.rom[pe_base:pe_base + pe_len]

        broken_ptr1 = bytes.fromhex("fe5bdeff")
        broken_ptr2 = bytes.fromhex("175cdeff")

        self.assertNotIn(broken_ptr1, pe_code, "Old broken pointer 0xFFDE5BFE still found in NCT5532DPeiInit!")
        self.assertNotIn(broken_ptr2, pe_code, "Old broken pointer 0xFFDE5C17 still found in NCT5532DPeiInit!")

    def test_11_optional_header_image_base(self):
        """PE OptionalHeader.ImageBase at 0x00C0D9F0 must be 0xFFC0D904."""
        img_base_bytes = self.rom[0x00C0D9F0:0x00C0D9F4]
        self.assertEqual(img_base_bytes, bytes.fromhex("04d9c0ff"),
                         f"ImageBase is {img_base_bytes.hex()}, expected 04d9c0ff (0xFFC0D904)")
        img_base_val = int.from_bytes(img_base_bytes, "little")
        self.assertEqual(img_base_val, 0xFFC0D904)

    def test_12_checksums_pe_ffs_fv(self):
        """Checksums in PE32 OptionalHeader, FFS Header, and Firmware Volume Header must be valid."""
        # 1. PE Checksum validation
        pe_base = 0x00C0D904
        pe_len = 0x860
        pe_buf = bytearray(self.rom[pe_base:pe_base + pe_len])
        stored_pe_chk = int.from_bytes(pe_buf[0x110:0x114], "little")

        pe_buf[0x110:0x114] = b'\x00\x00\x00\x00'
        if len(pe_buf) % 2 != 0:
            pe_buf.append(0)
        acc = 0
        for i in range(0, len(pe_buf), 2):
            w = int.from_bytes(pe_buf[i:i+2], "little")
            acc += w
            acc = (acc & 0xFFFF) + (acc >> 16)
        acc = (acc & 0xFFFF) + (acc >> 16)
        calc_pe_chk = (acc + pe_len) & 0xFFFFFFFF
        self.assertEqual(stored_pe_chk, calc_pe_chk,
                         f"Stored PE Checksum 0x{stored_pe_chk:08X} does not match computed 0x{calc_pe_chk:08X}")

        # 2. FFS Header Checksum validation
        ffs_hdr = self.rom[0x00C0D8D0:0x00C0D8D0 + 24]
        hdr_sum = (sum(ffs_hdr[:16]) + ffs_hdr[16] + sum(ffs_hdr[18:23])) & 0xFF
        self.assertEqual(hdr_sum, 0, f"FFS Header checksum sum is 0x{hdr_sum:02X}, expected 0")

        # 3. FFS File Checksum: Attributes is 0x00, so Checksum.File must be 0xAA (FFS_FIXED_CHECKSUM)
        file_chk = ffs_hdr[17]
        self.assertEqual(file_chk, 0xAA, f"FFS File Checksum is 0x{file_chk:02X}, expected 0xAA")

        # 4. Firmware Volume Header Checksum at 0x00C00000
        fv_hdr = self.rom[0x00C00000:0x00C00000 + 0x48]
        fv_words = [int.from_bytes(fv_hdr[i:i+2], "little") for i in range(0, len(fv_hdr), 2)]
        fv_sum = sum(fv_words) & 0xFFFF
        self.assertEqual(fv_sum, 0, f"Firmware Volume Header checksum sum is 0x{fv_sum:04X}, expected 0")

    def test_13_ap_reset_vector(self):
        """AP Multi-Processor startup vector at 0x00FFD000 must be EA D0 FF 00 F0 (jmp far F000:FFD0)."""
        ap_vector = self.rom[0x00FFD000:0x00FFD010]
        expected_ap = bytes.fromhex("ead0ff00f0000000000000000000272d")
        self.assertEqual(ap_vector, expected_ap,
                         f"AP reset vector at 0x00FFD000 is {ap_vector.hex()}, expected {expected_ap.hex()}")

    def test_14_sec_reset_vector(self):
        """SEC Core Reset Vector at 0x00FFFFF0 must be NOP, NOP, JMP."""
        sec_vector = self.rom[0x00FFFFF0:0x01000000]
        self.assertEqual(sec_vector[:3], bytes.fromhex("9090e9"),
                         f"SEC reset vector starts with {sec_vector[:3].hex()}, expected 9090e9")

    def test_15_microcodes_and_fit_table(self):
        """FIT table and 4 official Intel microcode entries must be intact with valid checksums."""
        fit_ptr = int.from_bytes(self.rom[0x00FFFFC0:0x00FFFFC8], "little")
        self.assertEqual(fit_ptr, 0xFFBF0000, f"FIT pointer is 0x{fit_ptr:08X}, expected 0xFFBF0000")

        fit_offset = 0x00BF0000
        self.assertEqual(self.rom[fit_offset:fit_offset + 8], b"_FIT_   ", "FIT table header signature missing")

        expected_microcodes = [
            (0x00D21F20, 0x306F1, 0x80000013, 0x8800),
            (0x00D2A720, 0x406F0, 0x00000014, 0x7C00),
            (0x00D32320, 0x306F2, 0x00000049, 0x9800),
            (0x00D3BB20, 0x406F1, 0x0B000041, 0x8C00),
        ]

        for off, exp_cpuid, exp_rev, exp_size in expected_microcodes:
            hdr = self.rom[off:off + 48]
            rev = int.from_bytes(hdr[4:8], "little")
            cpuid = int.from_bytes(hdr[12:16], "little")
            total_size = int.from_bytes(hdr[32:36], "little")
            self.assertEqual(cpuid, exp_cpuid, f"Microcode CPUID mismatch at 0x{off:08X}")
            self.assertEqual(rev, exp_rev, f"Microcode Rev mismatch at 0x{off:08X}")
            self.assertEqual(total_size, exp_size, f"Microcode Size mismatch at 0x{off:08X}")

            mc_block = self.rom[off:off + total_size]
            dwords = [int.from_bytes(mc_block[i:i+4], "little") for i in range(0, total_size, 4)]
            self.assertEqual(sum(dwords) & 0xFFFFFFFF, 0, f"Microcode block at 0x{off:08X} has invalid checksum")

    def test_16_companion_roms_unmodified(self):
        """Companion ROMs (ORIGINAL.rom and BiosUpdate.rom) must remain unmodified and intact."""
        self.assertTrue(ORIG_PATH.exists(), f"{ORIG_PATH} missing")
        orig_hash = hashlib.sha256(ORIG_PATH.read_bytes()).hexdigest()
        self.assertEqual(orig_hash, EXPECTED_ORIG_SHA256, "ORIGINAL.rom was modified")

        self.assertTrue(BIOS_UPD_PATH.exists(), f"{BIOS_UPD_PATH} missing")
        upd_hash = hashlib.sha256(BIOS_UPD_PATH.read_bytes()).hexdigest()
        self.assertEqual(upd_hash, EXPECTED_BIOS_UPD_SHA256, "BiosUpdate.rom was modified")

    def test_17_repaired_rom_sha256(self):
        """Repaired ROM must match expected SHA-256 cryptographic digest."""
        rom_hash = hashlib.sha256(self.rom).hexdigest()
        self.assertEqual(rom_hash, EXPECTED_MODBETA_SHA256,
                         f"Repaired ROM hash is {rom_hash}, expected {EXPECTED_MODBETA_SHA256}")

if __name__ == "__main__":
    unittest.main(verbosity=2)
