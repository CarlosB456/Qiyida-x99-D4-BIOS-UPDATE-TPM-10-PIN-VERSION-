# Qiyida X99-D4 (Chipset Intel C612 / Socket LGA2011-3) - Firmware Repository

[English documentation / Documentacion en Ingles](README_EN.md)

<p align="center">
  <img src="qiyda-x99-d4-1.jpg" width="650" alt="Qiyida X99-D4 Motherboard">
</p>

Repositorio de firmware oficial y modificado para la placa base Qiyida X99-D4 (Revision 2.0 con conector TPM 2.0 de 10 pines).

---

## 1. Especificaciones de Hardware de la Plataforma

| Componente | Especificacion de Hardware |
| :--- | :--- |
| Placa base | Qiyida X99-D4 v2.0 (OEM Jginyue / Machinist) |
| Socket | LGA2011-3 (Intel Socket R3) |
| Chipset (PCH) | Intel C612 Wellsburg-G Server (Device ID `0x8D4A`) |
| Procesadores compatibles | Intel Xeon E5-1600/2600 v3 (Haswell-EP), Xeon E5-1600/2600 v4 (Broadwell-EP), Core i7 5800/5900/6800/6900 |
| Memoria RAM | DDR4 4 canales: soporte simultaneo para UDIMM (Non-ECC) y RDIMM (ECC Registrada de servidor) |
| Super I/O | Nuvoton NCT5532D (LQFP-64, Chip ID `0xC560`, detectado en CPU-Z como `Nuvoton NCT6779`) |
| Interfaz de Red (LAN) | Realtek RTL8111H Gigabit Ethernet PCIe |
| Chip SPI Flash | 16 MB / 128 Mb (Winbond W25Q128 / Macronix MX25L128 / GigaDevice GD25Q128) |

---

## 2. Inventario de Archivos de Firmware

| Archivo | Tamano | SHA-256 | Descripcion | Metodo de Flasheo |
| :--- | :--- | :--- | :--- | :--- |
| `qiyidax99d4interfazgraficamodbeta.rom` | 16,777,216 bytes | `a9e80340da0f68bb8548216cfb8aec76fd5b9d8a1d8b0bd6787533f201a36437` | Firmware completo de 16 MB con interfaz grafica UEFI Gigabyte reparada, limites FRBA corregidos, tabla VSCC restaurada, mitigacion AltMeDisable, reubicacion PEI NCT5532D y microcodigos 2024. | **Exclusivamente programador fisico externo (CH341A)** |
| `qiyidax99d4BiosUpdate.rom` | 16,777,216 bytes | `0bca95f4869ecdbbeac3d4d528b34063697dea17473a2a0adf2162ed77284b45` | Firmware de produccion basado en la BIOS original de 8 MB con microcodigos 2024 (Haswell rev 49, Broadwell rev 41). Flasheable por software en Windows. | Software (`fptw64 -bios`) o programador CH341A |
| `qiyidax99d4ORIGINAL.rom` | 16,777,216 bytes | `0220fc2e42061ebde1634f231a52951631fc64e015770ba5fdd140e00b5e32d1` | Volcado de fabrica integro (Intel SPS 3.1.3.72, BIOS 8 MB). Respaldo de referencia. | Programador fisico externo (CH341A) |

---

## 3. Ingenieria Inversa y Reparaciones Estructurales en la ROM Modificada

En `qiyidax99d4interfazgraficamodbeta.rom` se diagnosticaron y corrigieron anomalías a nivel de silicio:

### 3.1 Correccion de Solapamiento en Flash Descriptor (FRBA Region 1)
- **Mecanica del fallo:** En el Intel Flash Descriptor (offset `0x0044`), la Region 1 (BIOS) tenia asignados los limites `00 00 ff 0f` (Base `0x00000000`, Limite `0x00FFFFFF`). Al abarcar todo el espacio desde el byte 0, la Region 1 se solapaba ilegalmente sobre el Descriptor (Region 0: `0x00000000..0x00000FFF`), GbE (Region 3: `0x00001000..0x00002FFF`) y ME (Region 2: `0x00003000..0x001FFFFF`). El arbitro SPI del chipset Intel C612 entra en estado `Flash Configuration Error` y bloquea las transacciones en el bus SPI, impidiendo el arranque.
- **Correccion aplicada:** Se configuro la Base en `0x00200000` (offset `0x0044`: `00 02 ff 0f`). La Region 1 queda acotada en `0x00200000..0x00FFFFFF` (14 MB), eliminando el solapamiento con las regiones inferiores y respetando el arbitraje de hardware del PCH.

### 3.2 Restauracion de Tabla VSCC y Registro PCHSTRP10 (AltMeDisable)
- **Mecanica del fallo:** En la definicion de chipsets del Flash Descriptor, el offset `0x0128` corresponde a una entrada de la tabla VSCC (*Vendor Specific Component Capabilities*), no al registro de soft straps. Una modificacion errónea altero `00 00 80 00` (`0x00800000`) a `80 00 80 00` (`0x00800080`), corrompiendo los parametros de temporizacion y comandos del chip SPI flash. Al mismo tiempo, el verdadero registro de straps `PCHSTRP10` reside en el offset `0x0088` (`0x0060 + 10*4`), donde permanecia inalterado, impidiendo que el motor Intel ME recibiera la señal de desactivacion.
- **Correccion aplicada:**
  - Se restauro el offset `0x0128` a su valor integro `00 00 80 00` (`0x00800000`).
  - Se valido y aplico el bit 7 (`AltMeDisable = 1`) en `PCHSTRP10` (offset `0x0088`), instruyendo al motor ME detenerse ordenadamente tras la generacion de reloj del PCH sin activar el temporizador watchdog.

### 3.3 Reubicacion de Punteros en Modulo PEIM NCT5532DPeiInit
- **Mecanica del fallo:** El driver PEIM `NCT5532DPeiInit` (`9029F23E-E1EE-40D1-9382-36DD61A63EAA`) fue trasplantado desde `ORIGINAL.rom` (donde residia en `ImageBase = 0xFFDE59FC`) a `0xFFC0D904` sin reubicar sus punteros absolutos. Durante la fase temprana PEI (ejecucion directa XIP en memoria flash antes de inicializar la RAM), el codigo ejecutaba:
  ```assembly
  mov esi, 0xFFDE5BFE
  mov ecx, 0xFFDE5C17
  ```
  En la nueva distribucion de flash, la direccion `0xFFDE5BFE` contiene relleno `0xFF`. El bucle de configuracion Super I/O leia puerto `0xFFFF`, ejecutaba `out 0xFFFF, al` y generaba una excepcion `#UD` / Triple Fault inmediata al no existir tabla IDT instalada.
- **Correccion aplicada:**
  - Delta de reubicacion aplicado: `-0x1D80F8`.
  - Puntero 1 (offset ROM `0x00C0DC15` / RVA `0x311`): corregido de `FE 5B DE FF` a `06 DB C0 FF` (`mov esi, 0xFFC0DB06`). Enlaza con la tabla LPC en `0x00C0DB04` (Rango 1: `0x2E`, Rango 2: `0x60`, Rango 3: `0x0A00`).
  - Puntero 2 (offset ROM `0x00C0DC36` / RVA `0x332`): corregido de `17 5C DE FF` a `1F DB C0 FF` (`mov ecx, 0xFFC0DB1F`). Enlaza con la tabla de inicializacion Nuvoton en `0x00C0DB1C` (secuencia de desbloqueo `0x87, 0x87` a puerto `0x2E`).
  - Cabecera PE `OptionalHeader.ImageBase` (offset `0x00C0D9F0`): actualizada a `0xFFC0D904`.
  - Recalculacion integral de checksums: PE Checksum actualizado a `0x000095FB` (offset `0x00C0DA14`), validacion del checksum de cabecera FFS (`0x4C`) y verificacion del checksum del Firmware Volume contenedor (`0xE22F`).

### 3.4 Vector de Arranque Multiprocesador (Offset `0x00FFD000`)
- **Mecanica del fallo:** Cuando el procesador principal (BSP) envia la interrupcion de inicio SIPI (vector `0xFD`), los nucleos auxiliares (APs) inician ejecucion en la direccion fisica `0xFD000` (mapeada en `0x00FFD000`). Si el area contiene relleno plano `0xFF`, la CPU genera una excepcion `#UD` instantanea.
- **Correccion aplicada:** Instruccion x86 verificada en modo real de 16 bits:
  ```assembly
  EA D0 FF 00 F0 00 00 00 00 00 00 00 00 00 27 2D  ; jmp far F000:FFD0
  ```
  Deriva la ejecucion al vector `0x00FFFFD0` en el SEC Core para la inicializacion simetrica de los nucleos.

### 3.5 Extirpacion de Modulos Parasitos de Gigabyte
Se eliminaron y reemplazaron por bloques de relleno UEFI PAD limpios 24 modulos no aplicables al hardware de la Qiyida X99-D4:
1. **Gigabyte DualBIOS (6 modulos):** `DualBiosCSPPei`, `DualBiosPlusPei`, `DualBiosDxe`, `DualBiosPlusDxe`, `DualBiosSmm`, `DualBiosPlusSmm`.
2. **Intel Thunderbolt Alpine Ridge (4 modulos):** `TbtPei`, `TbtXhciOnlyPei`, `TbtDxe`, `TbtSmm`.
3. **Controlador ITE EC 8790 (3 modulos):** `Ite8790ECPei`, `Ite8790ECDxe`, `Ite8790ECSmi`.
4. **Controladores de iluminacion LED ITE (4 modulos):** `ITEPowerLEDPei`, `ITEPowerLEDDxe`, `EcLedIndicatorPei`, `EcLedIndicatorSmm`.
5. **Gigabyte CellPhone OC (2 modulos):** `GBTCellPhoneOCDxe`, `GBTCellPhoneOCSmm`.
6. **Red Killer LAN (2 modulos):** `LxUndiBinE2400`, `LxUndiBinE2500`.
7. **SMM Features ITE 8728 (3 modulos):** `IT8728FSmmFeaturesPei`, `IT8728FSmmFeaturesDxe`, `IT8728FSmmFeaturesSmm`.

### 3.6 ACPI DSDT y Driver LAN Realtek
- **DSDT:** Inyeccion de la tabla ACPI oficial Qiyida (`dsdt_qiyida.bin`, 210,878 bytes) en `0x006A4134`, declarando puertos USB, pistas PCIe, Super I/O en `0x2E/0x2F` y 192 procesadores logicos.
- **LAN:** Driver Option ROM Realtek RTL8111H UEFI UNDI integrado en `0x00817FF8`.

### 3.7 Microcodigos Oficiales Intel 2024 y Tabla FIT
Actualizados en el Firmware Interface Table (FIT, offset `0x00BF0000`):

| CPUID | Stepping / Procesador | Revision | Fecha | Mitigaciones de Seguridad |
| :---: | :--- | :---: | :---: | :--- |
| `306F1` | Haswell-EP (Muestra de Ingenieria ES) | `80000013` | 2013-10-02 | Compatibilidad procesadores ES |
| `406F0` | Broadwell-EP (Muestra de Ingenieria ES) | `00000014` | 2015-07-02 | Compatibilidad procesadores ES |
| `306F2` | **Haswell-EP Comercial (Xeon E5 v3)** | **`49`** | 2021-08-11 | Downfall (GDS), CrossTalk / SRBDS, MDS, MMIO Stale Data |
| `406F1` | **Broadwell-EP Comercial (Xeon E5 v4)** | **`41`** | 2024-02-16 | Register File Data Sampling (RFDS 2024), Downfall (GDS), MDS |

---

## 4. Analisis de Protecciones de Flash y Desmitificacion del Pinmod

En comunidades tecnicas existe la creencia de que se requiere puentear pines del chip de audio Realtek durante 3 segundos para flashear placas base chinas con `fptw64.exe`. **Esto es innecesario en la placa Qiyida X99-D4**.

### 4.1 Permisos en el Intel Flash Descriptor de Fabrica
En el Flash Descriptor, el registro de permisos del host `FLMSTR1` reside en la seccion Flash Master Base Address (FMBA, offset `0x0100`).
En el firmware de fabrica ([qiyidax99d4ORIGINAL.rom](file:///c:/Users/Benja/Desktop/Qiyida-x99-D4-BIOS-UPDATE-TPM-10-PIN-VERSION--main/qiyidax99d4ORIGINAL.rom)), `FLMSTR1` en offset `0x0100` tiene definidos permisos directos de lectura y escritura para el procesador host.

### 4.2 Estado de Protecciones en NVRAM
- **`BIOS Lock`** (Registro PCH `BC` bits `BLE` / `SMM_BWP`): Configurado en `Disabled (0)` de fabrica. El driver SMM `PchBiosWriteProtect` no instala manejadores SMI de bloqueo.
- **`Host Flash Lock-Down`** (`FLOCKDN`): Configurado en `Disabled (0)` de fabrica.
- **`Flash Protected Range Registers`** (`FPRR`): Inactivo.

---

## 5. Instrucciones Obligatorias de Flasheo e Instalacion

### ADVERTENCIA TECNICA CRITICA: INCOMPATIBILIDAD DE FLASHEO POR SOFTWARE PARA LA ROM GRAFICA

La placa base de fabrica posee un Flash Descriptor con particion de **8 MB ME + 8 MB BIOS**.
El archivo modificado `qiyidax99d4interfazgraficamodbeta.rom` implementa una distribucion reestructurada de **2 MB ME + 14 MB BIOS**.

Si un usuario intenta flashear `qiyidax99d4interfazgraficamodbeta.rom` mediante software en Windows utilizando Intel FPT (`fptw64.exe -bios` o `fptw64.exe -f`), **el equipo quedara inservible (brickeado)** debido a que:
1. El comando `fptw64 -bios` graba unicamente dentro del rango activo del descriptor de fabrica (8 MB), omitiendo 6 MB de codigo BIOS vital situado entre `0x00200000` y `0x00800000`.
2. El comando `fptw64 -f` intenta escribir a traves de las particiones activas mientras el controlador SPI del chipset mantiene en hardware los limites de 8 MB/8 MB, destruyendo la region de gestion y corrompiendo la flash.

**REGLA DE FLASHEO:**
- `qiyidax99d4interfazgraficamodbeta.rom` **SOLO debe grabarse con programador fisico externo (CH341A)**.
- Para actualizar el equipo por software desde Windows sin hardware externo, **se debe utilizar exclusivamente `qiyidax99d4BiosUpdate.rom`**.

---

### Metodo 1: Grabacion con Programador Fisico Externo SPI (CH341A) - Obligatorio para ROM Grafica

Procedimiento requerido para `qiyidax99d4interfazgraficamodbeta.rom`:

1. Desconectar completamente la fuente de alimentacion de la red electrica y retirar la pila de litio CR2032 de la placa base.
2. Conectar el programador USB CH341A con pinza de prueba SOIC-8 al chip SPI flash de 16 MB soldado en la placa (Winbond W25Q128 o equivalente), respetando la orientacion del pin 1.
3. Abrir **NeoProgrammer** o **AsProgrammer**.
4. Seleccionar `Detect` para identificar el chip de 16 MB / 128 Mb.
5. Realizar una lectura de respaldo completa (`Read IC`) y guardar el archivo como copia de seguridad (`backup_fabrica.bin`).
6. Cargar en el programa el archivo `qiyidax99d4interfazgraficamodbeta.rom`.
7. Ejecutar la secuencia completa: `Erase IC` -> `Write IC` -> `Verify IC`.
8. Una vez finalizada y verificada la grabacion al 100%, retirar la pinza del chip.
9. Mantener la pila CR2032 fuera de la placa durante 5 minutos para asegurar un Clear CMOS completo de la NVRAM.
10. Reinstalar la pila CR2032, conectar la alimentacion y encender el equipo. El sistema iniciara directamente en la interfaz grafica Gigabyte UEFI.

---

### Metodo 2: Actualizacion Segura por Software desde Windows (Intel FPT) - Exclusivo para BiosUpdate.rom

Para actualizar microcodigos oficiales 2024 sin programador fisico, manteniendo la distribucion de particion de fabrica (8 MB BIOS):

1. Descargar o situar `fptw64.exe` (Intel Flash Programming Tool versión 9.1 o 10.0) en la carpeta del repositorio.
2. Abrir Símbolo del Sistema (`cmd.exe`) o PowerShell con **privilegios de Administrador**.
3. Ejecutar la grabacion exclusiva de la region BIOS:
   ```cmd
   fptw64.exe -bios -f qiyidax99d4BiosUpdate.rom
   ```
4. Esperar a que el proceso complete el borrado, escritura y verificacion (`FPT Operation Successful`).
5. Reiniciar el sistema. No se requiere reprogramar el Descriptor ni la region ME.

---

## 6. Verificacion y Suite de Pruebas

El repositorio incluye una suite automatizada de pruebas exhaustivas (`test_suite.py`) que comprueba byte a byte:
- Tamaño de archivo exacto (16,777,216 bytes).
- Limites FRBA y ausencia matematica de solapamiento en el bus SPI.
- Restauracion de la tabla VSCC en offset `0x0128` a `0x00800000`.
- Registro `PCHSTRP10` en offset `0x0088` con bit 7 en 1 (`AltMeDisable`).
- Desensamblado de instrucciones de `NCT5532DPeiInit` y consistencia de tablas de configuracion LPC / Super I/O.
- Punteros en rango estricto del espacio PE [ImageBase, ImageBase + SizeOfImage).
- Ausencia total de los punteros obsoletos `0xFFDE5BFE` y `0xFFDE5C17`.
- Integridad de checksums en PE32 OptionalHeader, cabecera FFS y Firmware Volume.
- Vector de inicio multiprocesador AP (`EA D0 FF 00 F0...`) en `0x00FFD000`.
- Vector de entrada SEC en `0x00FFFFF0`.
- Microcodigos Intel y tabla FIT.
- Respaldo integro de ROMs acompañantes (`ORIGINAL.rom` y `BiosUpdate.rom`).

Para ejecutar las pruebas:
```bash
python test_suite.py
```

---

## 7. Creditos y Referencias

- Microcodigos oficiales de Intel: repositorio [platomav/CPUMicrocodes](https://github.com/platomav/CPUMicrocodes).
- Analisis de estructuras UEFI y FFS: `UEFITool` por Nikolaj Schlej.
- Especificaciones de arquitectura: *Intel C610 Series Chipset and Intel X99 Chipset Datasheet*, *Intel 64 and IA-32 Architectures Software Developer's Manual*, *UEFI Platform Initialization Specification*.
