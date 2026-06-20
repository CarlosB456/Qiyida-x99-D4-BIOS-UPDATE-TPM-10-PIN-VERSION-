# Qiyida X99 D4 (C612) - BIOS Update & Mods
<p align="center">
  <img src="qiyda-x99-d4-1.jpg" width="600">
</p>

Este repositorio contiene versiones actualizadas y experimentales del firmware para la placa base china **Qiyida X99 D4 (Chipset C612 / X99)(10 PINS TPM VERSION)**. 

El objetivo de este proyecto es doble: proveer una base de firmware 100% estable con los últimos parches de seguridad de Intel, y ofrecer una versión experimental para obtener la interfaz gráfica premium de Gigabyte.

## ⚠️ ESTADO DEL PROYECTO: NO TESTEADO (BETA)
**De momento, NO se han podido testear en hardware ni la BIOS con microcódigos actualizados ni la versión de interfaz gráfica (`qiyidax99d4interfazgraficamodbeta.rom`) ya que no contamos temporalmente con un grabador físico CH341A.**

Flasear una BIOS siempre conlleva riesgos. **No uses AFUDOS/AFUWIN**. Se recomienda encarecidamente esperar a pruebas de validación o flashear bajo tu propio riesgo SOLO si tienes a mano un programador CH341A como método de recuperación en caso de fallo (Brick).

---

## 🛠️ Mejoras y Cambios Implementados

### 1. Actualización de Microcódigos Intel (2024) - `qiyidax99d4BiosUpdate.rom`
Se han reemplazado los microcódigos obsoletos de fábrica (2015-2019) por las versiones más recientes disponibles de Intel. Esto no solo mejora la seguridad, sino que soluciona pantallazos azules, congelamientos en estados de reposo (C-States) y fallos en virtualización.

| Procesador | CPUID | Microcódigo Original | Nuevo Microcódigo | Fecha del Parche |
| :--- | :---: | :---: | :---: | :---: |
| **Haswell-E/EP (Xeon v3)** | `306F2` | Rev `3D` (2018) | **Rev `49`** | Agosto 2021 |
| **Broadwell-E/EP (Xeon v4)** | `406F1` | Rev `38` (2019) | **Rev `41`** | Febrero 2024 |

**Vulnerabilidades mitigadas con esta actualización:**
- MDS (Microarchitectural Data Sampling) / ZombieLoad
- CrossTalk / SRBDS
- MMIO Stale Data
- **Downfall (GDS) y RFDS** (Crítico para instrucciones AVX2/AVX-512 en plataformas X99).

### 2. Mod de Interfaz Gráfica Gigabyte (EXPERIMENTAL) - `qiyidax99d4interfazgraficamodbeta.rom`
Se construyó un mod experimental de alto nivel ("Cross-Flash") tomando como base la BIOS UEFI de una placa **Gigabyte X99 Ultra Gaming (F7c)** para portar su interfaz gráfica avanzada y menús de Overclocking a la placa Qiyida.

**Técnicas de ingeniería aplicadas en esta versión:**
- **Trasplante del Flash Descriptor:** Se inyectó el descriptor original de la Qiyida para mantener las configuraciones eléctricas del PCH C612 (straps) intactas.
- **Inyección de DSDT (ACPI):** Mapeo correcto de pistas PCIe y puertos USB de la Qiyida hacia el núcleo lógico de Gigabyte.
- **Inyección SioDxeInit (Nuvoton NCT6779D):** Reemplazo del driver Super I/O nativo de Gigabyte (ITE) por el de Qiyida para evitar cuelgues en el POST y mantener la lectura de sensores térmicos y RPM de ventiladores.
- **Inyección LAN Realtek (Sin Conflictos):** Sustitución del driver UNDI Realtek nativo para garantizar red funcional.
- **Neutralización de Telemetría VRM (AMIBCP):** Se forzaron los valores de `PWM Phase Control` y `CPU VRIN PWM Thermal Protection` a modo Normal/Disabled (`0`). Esto evita que el BIOS de Gigabyte exija lecturas térmicas digitales al VRM analógico de la Qiyida, previniendo *thermal throttling* fantasma y cuelgues.

### 3. Herramientas Utilizadas
Para garantizar que la estructura de la BIOS permanezca funcional, las modificaciones se hicieron mediante herramientas profesionales de análisis estructural:
- **MMTool Aptio 5.0.2.0024:** Para inyección segura de microcódigos y recálculo de la tabla FIT.
- **MCExtractor v1.104.0:** Para la verificación criptográfica y hexadecimal de los microcódigos.
- **UEFITool 0.28.0:** Para extracción, análisis y trasplante de volúmenes DXE (DSDT, SIO, LAN) sin corromper los *padding files* de la arquitectura Aptio V.
- **AMIBCP 5.0.2:** Para la modificación interna de los menús M.I.T. de Gigabyte y el forzado de perfiles de energía seguros (Failsafe) en el control del VRM.

---

## 🚀 Instrucciones de Flasheo (Vía Windows/DOS)

*Nota: Solo realiza esto si asumes el riesgo y tienes un programador CH341A de respaldo.*
Se recomienda encarecidamente utilizar Intel FPT (v9 o v10, dependiendo de la versión de Intel ME de tu placa).

1. Abre una consola de comandos como Administrador (CMD o PowerShell).
2. Realiza un backup de tu BIOS actual:
   ```cmd
   fptw64.exe -d backup_original.rom
   ```
3. Flashea la nueva BIOS (reemplaza por el nombre del archivo que vayas a probar):
   ```cmd
   fptw64.exe -bios -f nombre_del_archivo.rom
   ```
4. **Paso Crítico:** Tras el flasheo exitoso, apaga el ordenador, desconéctalo de la corriente y retira la pila CR2032 de la placa base durante 5 minutos para hacer un **Clear CMOS**.
5. Enciende el PC, entra a la BIOS y carga los valores óptimos (Restore Defaults).

---

## 📝 Créditos y Notas
- Microcódigos proporcionados por el repositorio oficial de [platomav/CPUMicrocodes](https://github.com/platomav/CPUMicrocodes).
- Análisis estructural de BIOS y "Cross-flashing" realizado para asegurar la máxima estabilidad posible en hardware X99 clonado.
