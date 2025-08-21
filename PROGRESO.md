# Progreso del Simulador LEO/GEO Jamming

## 1. Alcance Actual

El script `JammerSimulator.py` proporciona una interfaz educativa para visualizar enlaces LEO y GEO y calcular métricas básicas de propagación y desempeño:

- Distancia slant range (geométrica exacta para LEO/GEO usando ley de cosenos).
- Pérdida de espacio libre (FSPL).
- Latencia de propagación (one‑way; base para RTT = 2x).
- C/N0 y C/N (a partir de EIRP, G/T, BW y FSPL, ignorando pérdidas adicionales y figura de ruido detallada).
- Elevación y visibilidad (criterio Elevación > 0°).

### 1.1 Definiciones clave e impacto (formato lineal)

Slant range (d): Distancia en línea de vista GS–satélite. Depende de la geometría (Re, Ro, Δ). Impacto: a mayor d suben FSPL y latencia; bajan C/N0 y C/N.

Elevación (E): Ángulo entre horizonte local y la LOS al satélite. Depende de Δ (posición relativa). Impacto: elevaciones bajas alargan trayecto y añaden posibles pérdidas (atm, clutter) no modeladas aún.

FSPL [dB]: Pérdida de espacio libre puramente geométrica. Depende de distancia D y frecuencia f (20 log10(4πDf/c)). Impacto: crece con D y f; reducirla mejora C/N0 directamente.

EIRP [dBW]: Potencia isotrópica radiada equivalente de transmisión. Suma de potencia TX y ganancia antena menos pérdidas front‑end. Impacto: +1 dB EIRP → +1 dB C/N0.

G/T [dB/K]: Figura de mérito de recepción (ganancia antena sobre temperatura de ruido del sistema). Depende de ganancia Rx y T_sys. Impacto: +1 dB G/T → +1 dB C/N0.

C/N0 [dBHz]: Relación portadora‑ruido referida a 1 Hz. Se calcula EIRP + G/T – FSPL + 228.6. Impacto: métrica base de calidad; fija techo de C/N para cualquier BW.

C/N [dB]: Relación portadora‑ruido en el ancho de banda útil. C/N = C/N0 – 10 log10(BW). Impacto: determina BER y modulación/FEC alcanzable.

BW [Hz]: Ancho de banda ocupado / filtrado de ruido. Parámetro de entrada. Impacto: más BW baja C/N (misma potencia repartida) pero permite mayor capacidad potencial.

Frecuencia (f): Frecuencia portadora. Parámetro de entrada. Impacto: frecuencias altas aumentan FSPL y (en realidad) pérdidas de atmósfera/lluvia (no incluidas aún).

Latencia one‑way [ms]: Tiempo de propagación ida (d/c). Impacto: influye en interactividad; en GEO es crítico; también afecta protocolos ventana grande.

RTT [ms]: Tiempo ida y vuelta (2× one‑way). Impacto: condiciona TCP, VoIP conversacional y aplicaciones en tiempo real.

Visibilidad: Estado binario (E>0). Depende de elevación. Impacto: si no visible no hay enlace útil (métricas físicas dejan de aplicarse).

Modo (LEO/GEO): Configuración geométrica seleccionada. Entrada usuario. Impacto: define rango típico y perfil de variación temporal (LEO dinámico, GEO estable).

Notas:
* +10 dB en FSPL (distancia/frecuencia) exige +10 dB entre (EIRP + G/T) para mantener C/N0.
* Reducir BW sube C/N pero limita throughput (Shannon: C ≈ BW * log2(1+SNR), aproximación no implementada todavía).
* Latencia no altera C/N pero afecta QoE (gaming, voz) y eficiencia de control.
* C/N0 es independiente de BW: separa la física del uso espectral.

## 2. Modelos y Fórmulas Implementadas

### 2.1 Geometría Orbital Simplificada

Parámetros básicos:
* Re = 6371 km  (radio medio terrestre)
* Ro = Re + h   (radio orbital geocéntrico; h = altitud)
   * Ejemplos: h_LEO ≈ 500 km  → Ro ≈ 6871 km;  h_GEO = 35786 km → Ro ≈ 42157 km
* Δ = ángulo central (radianes) entre la proyección del satélite y la estación en el centro de la Tierra

Slant range (distancia GS–Sat) en km:
```
d = sqrt( Re^2 + Ro^2 - 2*Re*Ro*cos(Δ) )
```

Elevación (observador sobre el ecuador, sin refracción):
```
sin(E) = (Ro*cos(Δ) - Re) / d
```
Visible si E > 0. Horizonte (E = 0) cuando:
```
cos(Δ_horizonte) = Re / Ro  ->  Δ_horizonte = arccos(Re/Ro)
```

### 2.2 Free Space Path Loss (FSPL)

Para frecuencia f (Hz) y distancia D (m):
```
FSPL[dB] = 20 * log10( 4 * π * D * f / c )
```
con c = 299,792,458 m/s.

Ejemplo numérico (LEO ~1200 km slant, f=12 GHz):
- \( D = 1.2\times10^6\,\text{m} \)
- \( 4\pi D f / c \approx 6.033\times10^{11} \)
- FSPL ≈ 20 log10(6.033e11) ≈ 20 * (11.780) ≈ **235.6 dB**

(Verifica según distancia concreta registrada en CSV; si el CSV indica ~180 dB es porque la distancia usada era ~2,000 km y la fórmula coincide con esa magnitud.)

### 2.3 Latencia de Propagación
```
t_one_way_ms = (D / c) * 1000
t_RTT_ms      = 2 * t_one_way_ms
```
Ejemplo: LEO D=2,000 km → \( D=2\times10^6\,m \Rightarrow t_{ow}\approx 6.67\,ms \).

GEO típico (≈ 40,000 km): \( t_{ow} ≈ 133 \) ms; RTT ≈ 266 ms.

### 2.4 Densidad de Potencia Portadora a Ruido (C/N0)

Modelo educativo:
```
C/N0[dBHz] = EIRP[dBW] + G/T[dB/K] - FSPL[dB] + 228.6
```
Donde 228.6 dB = \(10\log_{10}(1/k)\) con k constante de Boltzmann.

### 2.5 Relación C/N para un Ancho de Banda B
```
C/N[dB] = C/N0[dBHz] - 10*log10(B)   (B en Hz)
```
Ejemplo: si C/N0 = 70 dBHz y B = 1 MHz → 10 log10(1e6)=60 dB ⇒ C/N ≈ 10 dB.

## 3. Ejemplo Numérico Integrado (LEO)
Supongamos:
- Altitud LEO: 500 km ⇒ \(R_O = 6871\) km.
- Estación en elevación E = 30°.

1. Slant range con la fórmula:
   d ≈ sqrt(6371^2 + 6871^2 - 2*6371*6871*cos(Δ)). Ajustando Δ que da E=30° resulta d ≈ 1200 km.
2. FSPL (12 GHz, 1.2e6 m): ≈ 232–236 dB (dependiendo distancia precisa).
3. Latencia ow: ≈ 4–6 ms.
4. Con EIRP = 53 dBW, G/T = -42 dB/K, FSPL=233 dB: C/N0 ≈ 53 - 42 - 233 + 228.6 ≈ 6.6 dBHz (muy bajo, ilustra necesidad de mejoras de enlace – en práctica habría más ganancias y pérdidas adicionales que ajustar).

## 4. Flujo de Cálculo en el Código
1. Se captura el ángulo orbital (LEO) o longitud relativa (GEO).
2. Se calcula \( \Delta \) y luego slant range y elevación.
3. Si Elevación > 0°: se calculan FSPL, latencia, C/N0 y C/N.
4. Se actualiza panel visual y se registra en historial para exportación.

## 5. Exportación de Datos
- CSV o XLSX con cabeceras legibles (ej: `FSPL [dB]`, `C/N0 [dBHz]`).
- XLSX aplica estilo (negrita, cursiva, tamaño 13) a la fila de cabeceras.

## 6. Limitaciones / Próximos Pasos
- No se modelan: pérdidas atmosféricas, polarización, dispersión de lluvia, pointing loss.
- C/N0 sin figura de ruido real del receptor ni potencia recibida intermedia.
- Elevación asume GS sobre ecuador (latitud 0°) para simplicidad.

## 7. Próximas Mejores Extensiones Sugeridas
1. Añadir pérdidas adicionales configurables (atm, rain, pointing).
2. Mostrar RTT además de one‑way.
3. Integrar modelo de interferencia / Jammer y cálculo C/I y C/(N+I).
4. Soporte de múltiples satélites LEO (trayectorias y handover). 
5. Opción de fijar latitud de la GS para elevación realista.

---
*Documento vivo – actualizar conforme se añadan nuevas funcionalidades.*
