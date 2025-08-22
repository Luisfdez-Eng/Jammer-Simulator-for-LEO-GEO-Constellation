# Progreso del Simulador LEO/GEO Jamming

## 1. Alcance Actual

El script `JammerSimulator.py` proporciona una interfaz educativa para visualizar enlaces LEO y GEO y calcular métricas básicas de propagación y desempeño. Se han incorporado ya las fases 0 y 1 del plan incremental (estructuración interna + geometría/dinámica + Doppler) y se ha añadido la visualización de RTT:

- Distancia slant range (geométrica exacta para LEO/GEO usando ley de cosenos).
- Pérdida de espacio libre (FSPL).
- Latencia de propagación one‑way y RTT (2x) visibles en UI.
- C/N0 y C/N (a partir de EIRP, G/T, BW y FSPL, ignorando pérdidas adicionales y figura de ruido detallada).
- Elevación y visibilidad (criterio Elevación > 0°).
- Geometría orbital (Δ central, radio orbital geocéntrico, horizonte Δ_h, tiempo restante de visibilidad).
- Dinámica orbital ideal circular (velocidad orbital v_orb, velocidad angular ω, periodo orbital T_orb) para LEO.
- Rate geométrico de cambio de distancia (range rate).
- Doppler instantáneo y |Doppler| máximo teórico.

### 1.1 Definiciones clave e impacto (formato lineal)

Slant range (d): Distancia en línea de vista GS–satélite. Depende de la geometría (Re, Ro, Δ). Impacto: a mayor d suben FSPL y latencia; bajan C/N0 y C/N.

Elevación (E): Ángulo entre horizonte local y la LOS al satélite. Depende de Δ (posición relativa). Impacto: elevaciones bajas alargan trayecto y añaden posibles pérdidas (atm, clutter) no modeladas aún.

FSPL [dB]: Atenuación geométrica ideal debida solo a la propagación en el vacío: depende de distancia y frecuencia (20 log10(4πDf/c)). Es inevitable y física.. Impacto: crece con D y f; reducirla mejora C/N0 directamente.

EIRP [dBW]: Potencia isotrópica radiada equivalente de transmisión. Suma de potencia TX y ganancia antena menos pérdidas front‑end. Impacto: +1 dB EIRP → +1 dB C/N0.

G/T [dB/K]: Figura de mérito de recepción (ganancia antena sobre temperatura de ruido del sistema). Depende de ganancia Rx y T_sys. Impacto: +1 dB G/T → +1 dB C/N0.

C/N0 [dBHz]: Relación portadora‑ruido referida a 1 Hz. Se calcula EIRP + G/T – FSPL + 228.6. Impacto: métrica base de calidad; fija techo de C/N para cualquier BW.

C/N [dB]: Relación portadora‑ruido en el ancho de banda útil. C/N = C/N0 – 10 log10(BW). Impacto: determina BER y modulación/FEC alcanzable.

BW [Hz]: Ancho de banda ocupado / filtrado de ruido. Parámetro de entrada. Impacto: más BW baja C/N (misma potencia repartida) pero permite mayor capacidad potencial.

Frecuencia (f): Frecuencia portadora. Parámetro de entrada. Impacto: frecuencias altas aumentan FSPL y (en realidad) pérdidas de atmósfera/lluvia (no incluidas aún).

Latencia one‑way [ms]: Tiempo de propagación ida (d/c). Impacto: influye en interactividad; en GEO es crítico; también afecta protocolos ventana grande.

RTT [ms]: Tiempo ida y vuelta (2× one‑way). Impacto: condiciona TCP, VoIP conversacional y aplicaciones en tiempo real. (Ahora mostrado en la interfaz)

Δ Central [°]: Ángulo en el centro de la Tierra entre sub‑satélite y estación. Impacto: gobierna simultáneamente elevación, distancia y visibilidad.

r_orb [km]: Radio orbital geocéntrico (Re + h). Impacto: determina velocidad orbital y Δ_horizonte.

v_orb [km/s]: Velocidad orbital circular ideal (sqrt(μ/r)). Impacto: define dinámica temporal (periodo, Doppler máximo).

ω [deg/s]: Velocidad angular aparente sobre el centro (v_orb/r_orb). Impacto: ritmo de variación de geometría y ventanas de visibilidad.

Range rate [km/s]: Derivada instantánea de la distancia slant. Signo negativo acercándose, positivo alejándose. Impacto: determina Doppler.

T_orb [min]: Periodo orbital ideal circular. Impacto: cadencia de repeticiones de pase.

Visib. restante [s]: Tiempo estimado hasta perder visibilidad (E→0). Impacto: planeación de handover / ventana de enlace.

Doppler f_d [kHz]: Desplazamiento de frecuencia instantáneo ( (v_rad/c)*f_c ). Impacto: necesidad de corrección de frecuencia / tracking.

|f_d| max [kHz]: Valor absoluto máximo teórico (v_orb/c * f_c) para la órbita y frecuencia configuradas.

Visibilidad: Estado binario (E>0). Depende de elevación. Impacto: si no visible no hay enlace útil (métricas físicas dejan de aplicarse).

Modo (LEO/GEO): Configuración geométrica seleccionada. Entrada usuario. Impacto: define rango típico y perfil de variación temporal (LEO dinámico, GEO estable).

Notas:
* +10 dB en FSPL (distancia/frecuencia) exige +10 dB entre (EIRP + G/T) para mantener C/N0.
* Reducir BW sube C/N pero limita throughput (Shannon: C ≈ BW * log2(1+SNR), aproximación no implementada todavía).
* Latencia no altera C/N pero afecta QoE (gaming, voz) y eficiencia de control.
* C/N0 es independiente de BW: separa la física del uso espectral.

## 2. Modelos y Fórmulas Implementadas

### 2.1 Geometría Orbital Simplificada (Fase 1)

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

### 2.4 Dinámica Orbital y Doppler (Fase 1)

Velocidad orbital circular (m/s):
```
v_orb = sqrt( μ / r_orb )
```
Velocidad angular (rad/s):
```
ω = v_orb / r_orb
```
Periodo orbital (s):
```
T_orb = 2π * sqrt(r_orb^3 / μ)
```
Range rate (signo elegido según acercamiento a nadir):
```
dd/dΔ = (Re * r_orb * sin(Δ)) / d
range_rate = dd/dΔ * ω
```
Doppler instantáneo y máximo:
```
f_d = (v_rad / c) * f_c
f_d_max = (v_orb / c) * f_c
```
Tiempo restante de visibilidad (si E>0):
```
Δ_rem = Δ_h - Δ_actual
vis_remaining = Δ_rem / ω_deg   (ω en deg/s)
```

### 2.5 Densidad de Potencia Portadora a Ruido (C/N0)

Modelo educativo:
```
C/N0[dBHz] = EIRP[dBW] + G/T[dB/K] - FSPL[dB] + 228.6
```
Donde 228.6 dB = \(10\log_{10}(1/k)\) con k constante de Boltzmann.

### 2.6 Relación C/N para un Ancho de Banda B

### 2.7 Bloque de Pérdidas Adicionales (Fase 2)

Entradas (todas en dB, inicial 0):
```
RFL_feeder, AML_misalignment, AA_atmos, Rain_att, PL_polarization, L_pointing, L_impl
```
Suma de pérdidas extra:
```
L_total_extra = Σ pérdidas_i
```
Pérdida total de trayecto (educativa, sin distinguir uplink/downlink todavía):
```
Path_loss_total = FSPL + L_total_extra
```
Aplicación al enlace:
* C/N0 ahora se calcula usando Path_loss_total (antes sólo FSPL). Cada dB de pérdidas extra reduce C/N0 un 1 dB.

Visualización:
* En panel principal: Σ Pérdidas Extra y Path Loss Total.
* Sección colapsable (botón) muestra cada componente individual.
* Export histórico añade columnas: cada pérdida individual, loss_total_extra_db, path_loss_total_db.

### 2.8 Back-off y EIRP Efectivo (Fase 3)

Objetivo: Modelar la diferencia entre la potencia teórica de saturación de un amplificador (TWT / SSPAs / amplificador del jammer) y la potencia realmente operativa cuando se introduce margen (back-off) para mantener linealidad y máscara espectral.

Conceptos:
* EIRP_sat_saturated: EIRP al operar en saturación (salida máxima lineal + compresión) suponiendo ganancias ideales y sin distorsión admisible.
* Input Back-Off (IBO): Reducción aplicada a la señal de entrada respecto al punto de saturación para evitar que los picos entren en compresión.
* Output Back-Off (OBO): Diferencia entre la potencia de salida saturada y la real de operación. Relacionada con IBO pero no idéntica (eficiencia y curva de transferencia); aquí se aproxima: OBO ≈ IBO − 5 dB (modelo educativo simple que refleja que parte del drive adicional no se traduce 1:1 en salida por la compresión).
* PAPR / Cresta: Modulación multicarrier (OFDM, múltiples portadoras o jamming multitono) exige más IBO para que los picos no distorsionen → se sacrifica EIRP efectivo.

Entradas UI:
```
EIRP_sat_saturated (dBW)
Input_backoff (dB)
Override manual (flag + EIRP_manual)
```

Reglas implementadas (modelo simplificado):
```
Output_backoff = max(0, Input_backoff - 5)
EIRP_eff = (override ? EIRP_manual : EIRP_sat_saturated - Input_backoff)
```

Impacto físico en un enlace real:
1. Linealidad y Calidad de Modulación: Más back-off reduce productos de intermodulación (IMD3, IMD5) y mejora EVM, permitiendo usar modulaciones de orden alto (ej. 64/128/256APSK) sin exceder límites de MER.
2. Máscaras Espectrales / Interferencia: Menos distorsión fuera de banda → menor interferencia a canales adyacentes y menor probabilidad de violar regulaciones (ETSI, FCC, ITU).
3. Eficiencia de Potencia: Back-off disminuye la eficiencia del amplificador (TWT/SSPA) y la potencia útil radiada; hay trade‑off entre eficiencia energética y pureza espectral.
4. Capacidad / Throughput: Cada dB de Input_backoff (sin override) resta 1 dB de EIRP_eff → baja C/N0 → reduce margen de Eb/N0 (que se calculará en Fase 4) obligando a elegir una modulación/FEC más robusta y de menor tasa.
5. Diseño de Jammer: Un jammer que usa formas de onda de alta cresta (ruido amplio, multicarrier) debe aplicar back-off; un jammer de onda continua (CW) o single-tone puede operar casi en saturación maximizando densidad de interferencia. Este simulador permite visualizar esa pérdida de eficacia relativa.
6. Multi‑carrier en GEO/HTS: Transpondedores GEO con múltiples carriers suelen operar con OBO de 3–6 dB; broadcast single‑carrier puede acercarse a saturación (OBO <1 dB). Esto se puede ensayar variando Input_backoff para observar el impacto directo 1:1 en C/N0.

Por qué la función override: facilita estudiar escenarios "¿qué pasaría si" fijando directamente un EIRP efectivo sin mover el parámetro de saturación base, comparando políticas de operación (ej. política A: bajar drive vs política B: hardware diferente con mayor P_sat).

Relación con fases futuras:
* Fase 4 añadirá cálculo de Eb/N0 y margen; el efecto del back-off se verá propagado a la métrica de disponibilidad/capacidad.
* Permitirá ilustrar el compromiso entre limpieza espectral (más back-off) y robustez del enlace/jamming (más EIRP efectivo).

Export / Historial:
* Nuevas columnas: EIRP SAT, INPUT BO, OUTPUT BO, EIRP EFF, OVERRIDE FLAG para trazar series temporales y comparar estrategias.

Resumen conceptual: El back-off es un control de calidad de señal que cuesta potencia. El simulador lo traduce directamente en una reducción de C/N0 (dB por dB) anticipando la degradación de margen de enlace que se cuantificará en la siguiente fase.

Ejemplos típicos reales (orientativos):
* GEO Broadcast (monocarrier): IBO ≈ 0.5–1.5 dB → OBO ≈ 0.5–1 dB.
* GEO Multi-carrier (varios carriers SCPC): IBO 4–6 dB → OBO 3–5 dB.
* OFDM / Alta PAPR: IBO 7–10 dB (o más) según crest factor.
* Jammer CW: IBO ~0 dB (máximo EIRP).
* Jammer multiruido ancho: IBO 4–8 dB para no distorsionar y mantener espectro plano.
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

## 4. Flujo de Cálculo en el Código (actualizado Fases 0-1)
1. Se captura el ángulo orbital (LEO) o longitud relativa (GEO).
2. Se calcula \( \Delta \) y luego slant range y elevación.
3. Bloques modulares: (a) actualización de parámetros, (b) geometría/dinámica orbital, (c) doppler, (d) métricas de enlace (FSPL, latencia, C/N0, C/N), (e) render de tabla y (f) logging histórico.
4. Si Elevación > 0°: se calculan FSPL, latencia OW/RTT, C/N0, C/N y Doppler.
5. Se actualiza panel visual y se registra en historial para exportación.

## 5. Exportación de Datos
- CSV o XLSX con cabeceras legibles (ej: `FSPL [dB]`, `C/N0 [dBHz]`).
- XLSX aplica estilo (negrita, cursiva, tamaño 13) a la fila de cabeceras.

## 6. Limitaciones / Próximos Pasos
- El bloque de pérdidas es agregado y no separa uplink/downlink ni dependencia de frecuencia/elevación real (modelos de atmósfera y lluvia aún simplificados a un único término Rain_att).
- Falta todavía el desglose de temperatura de ruido (T_rx, cielo claro, exceso lluvia) y cálculo de T_sys explícito (Fase 4).
- No se calcula Eb/N0, margen frente a requisito ni capacidad Shannon: previsto en Fase 4.
- Sin modelado de interferencia/jammer externo (C/I, C/(N+I)) todavía.
- Elevación supone GS en ecuador (latitud 0°) para simplificar geometría.
- No se distinguen aún canales forward / return ni potencias separadas en ambos sentidos.

## 7. Próximas Mejores Extensiones Sugeridas
1. (Completo) Pérdidas adicionales y Path Loss Total (Fase 2).
2. (Completo) RTT visible (Fase 1) y Back‑off / EIRP efectivo (Fase 3).
3. Bloque de ruido detallado: T_sys, N0, Eb/N0, Margen, capacidad Shannon, adaptación (Fase 4).
4. Modelo de interferencia / jammer externo: C/I, C/(N+I), J/S, potencia jammer con su propio back-off.
5. Soporte multi‑satélite LEO, handover y agregación.
6. Latitud/longitud real de la estación y modelos atmosféricos dependientes de elevación.
7. Cobertura y dimensionamiento (Fase 6), reorganización UI (Fase 7), export schema_version (Fase 8).
8. Validación y sanitización de entradas (Fase 9); documentación extendida final (Fase 10).

---
## 8. Estado de Fases (Resumen)

- Fase 0: Estructuras de contenedores (losses, noise, power, throughput, latencies, coverage) y helpers dB. (Completado)
- Fase 1: Geometría, dinámica, Doppler, periodo, visibilidad restante y RTT. (Completado)
- Fase 2: Pérdidas configurables, Path Loss Total afectando C/N0, export ampliado. (Completado)
- Fase 3: Back-off, EIRP efectivo, override manual, impacto directo en C/N0. (Completado)
- Próxima en cola: Fase 4 (ruido detallado, T_sys, N0, Eb/N0, margen, capacidad, preparación para interferencia).

*Documento vivo – actualizar conforme se añadan nuevas funcionalidades.*
