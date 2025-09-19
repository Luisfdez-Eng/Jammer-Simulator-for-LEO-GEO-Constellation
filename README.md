# 🛰️ Educational LEO / GEO Satellite Link Simulator & Progressive Jamming Analysis Framework

> **Versión**: 2.2.0 - Dashboard CSV Avanzado con Suavizado CINR  
> **Última Actualización**: 10 de Enero de 2025  
> **Estado Actual**: **Escenario 1 Completo, Dashboard CSV Optimizado, Escenario 2 con Spot Jamming Operacional**

Un proyecto evolutivo cuyo núcleo es una interfaz gráfica interactiva Tkinter que simula un enlace satélite ↔ estación terrestre. Está diseñado para: (1) visualizar geometría orbital LEO vs GEO, (2) exponer y desmitificar un presupuesto de enlace dinámico, y (3) actuar como base para análisis de escenarios de interferencia (jamming), contramedidas y análisis de resistencia de constelaciones a gran escala.

<img width="1911" height="1030" alt="image" src="https://github.com/user-attachments/assets/8269c758-15db-4a73-830e-01540549dfdd" />

## 🔍 Visión General
El repositorio actualmente incluye el script principal `JammerSimulator.py` implementando:
- Carga de parámetros (JSON) con separación entre estado central y GUI.
- Renderizado 2D simplificado de la Tierra, satélite LEO animado y slot GEO arrastrable.
- Cálculos fundamentales: rango slant, elevación, pérdida de espacio libre (FSPL), latencia de propagación, C/N0 y C/N.
- Panel de métricas en tiempo real más exportación histórica CSV/XLSX avanzada.
- **Sistema Dashboard CSV**: Exportación estructurada con 84/146/53 columnas según configuración de jammers.
- **Algoritmos de Suavizado**: Eliminación de discontinuidades en CINR para transiciones realistas.

Sobre esta base construiremos iterativamente un framework modular cubriendo fenómenos operacionales y hostiles en sistemas satelitales contemporáneos (mega-constelaciones, enlaces híbridos, ataques coordinados, contramedidas adaptativas, degradación ambiental, estrategias de resistencia, etc.).

## 🎯 Objetivos Educativos Centrales
1. Hacer tangible la brecha geométrica y energética entre LEO y GEO (distancia, FSPL, latencia, Doppler futuro).
2. Proporcionar transparencia en presupuesto de enlace: cada término visible y trazable.
3. Añadir complejidad gradualmente: comenzar con "vacío ideal" (sin pérdidas extra, sin interferencia); añadir factores incrementalmente con fundamento claro.
4. Fomentar experimentación rápida: parámetros editables + exportaciones limpias.
5. Preparar sustrato para evoluciones avanzadas (jamming adaptativo, clima severo, redundancia híbrida, resistencia sistémica).

## ✅ Estado Actual (Implementación Avanzada)

### 🌟 Características Principales Implementadas

#### **🔄 Separación Completa UL/DL**
- **Enlaces Independientes**: Uplink y Downlink totalmente separados
- **Interfaz con Pestañas**: GUI reorganizada con pestañas Uplink, Downlink y End-to-End  
- **Cálculos Separados**: Frecuencias, EIRP, G/T independientes por enlace
- **Análisis End-to-End**: Combinación de ruidos UL+DL con métricas totales

#### **📊 Dashboard CSV Avanzado (Implementación Mayor)**
- **Sistema de Columnas Dinámico**: 
  - **Sin jammers**: 53 columnas organizadas por secciones
  - **Jammer único**: 84 columnas con métricas de interferencia
  - **Múltiples jammers**: 146 columnas con análisis individual y acumulado
- **Estructura Organizada**: 6 secciones lógicas (Básicos, UL, DL, E2E, Potencia, Pérdidas)
- **Formato XLSX Profesional**: Cabeceras en negrita, columnas auto-ajustadas, paneles congelados

#### **🔧 Algoritmos de Suavizado CINR**
- **Eliminación Salto Brusco**: Corregido descenso CINR de 7.38 dB → 0.17 dB
- **Degradación Responsiva**: Eliminación de degradación constante ~10.47 dB
- **Transiciones Realistas**: Algoritmos anti-discontinuidad implementados
- **Plot Continuity**: Columna `e2e.cinr_jammed.plot.db` para visualización continua

#### **🎨 Sistema de Etiquetas Mejorado**
- **Formato 1-Decimal**: Eliminación de precisión excesiva (ej: 12.7 dB vs 12.7234 dB)
- **Legibilidad Dashboard**: Labels optimizados para análisis visual
- **Consistencia Visual**: Formato uniforme en toda la interfaz

#### **🧠 Recomendaciones Dinámicas**
- **Lógica Basada en Thresholds**: Recomendaciones según degradación_db actual
- **Estados Adaptativos**: 
  - `degradacion_db < 5.0`: "CONFIGURACION_OPTIMA"
  - `5.0 ≤ degradacion_db < 15.0`: "AUMENTAR_POTENCIA"  
  - `degradacion_db ≥ 15.0`: "CONTRAMEDIDAS_AVANZADAS"
- **Contexto Inteligente**: Sugerencias basadas en condiciones operacionales

### 🏗️ Arquitectura Técnica Completamente Renovada

#### **Correcciones Fundamentales Implementadas**
```python
# Eliminación elevation_factor discontinuidades (líneas 685-700)
def calculate_jammer_effectiveness_individual():
    # ❌ ANTES: if elevation_deg < threshold: effectiveness *= elevation_factor
    # ✅ AHORA: Cálculo directo sin factores artificiales
    
# Cálculo single-jammer directo (líneas 4124-4135)  
def calculate_single_jammer_cinr():
    # ❌ ANTES: Interpolación compleja causando saltos
    # ✅ AHORA: Cálculo directo CINR = f(C/N, C/I)
    
# Sistema de etiquetas formateado (líneas 4175-4195)
def format_jammer_labels():
    # ❌ ANTES: f"{value:.4f}" → 12.7234 dB  
    # ✅ AHORA: f"{value:.1f}" → 12.7 dB
```

#### **Estructura CSV Optimizada**
```
=== SECCIÓN 1: PARÁMETROS BÁSICOS (8 columnas) ===
TIEMPO [s], MODO, ELEVACIÓN [°], DISTANCIA SLANT [km], 
FSPL [dB], LATENCIA IDA [ms], LATENCIA RTT [ms], ESTADO C/N

=== SECCIÓN 2: UPLINK (6 columnas) ===
UL C/N0 [dBHz], UL C/N [dB], UL FREQ [GHz], UL BW [MHz],
UL G/T [dB/K], UL ESTADO C/N

=== SECCIÓN 3: DOWNLINK (6 columnas) ===  
DL C/N0 [dBHz], DL C/N [dB], DL FREQ [GHz], DL BW [MHz],
DL G/T [dB/K], DL ESTADO C/N

=== SECCIÓN 4: END-TO-END (6 columnas) ===
E2E LATENCIA TOTAL [ms], E2E LATENCIA RTT [ms], E2E C/N TOTAL [dB],
E2E CINR TOTAL [dB], E2E ENLACE CRÍTICO, E2E ESTADO

=== SECCIÓN 5: JAMMING (11 columnas - cuando aplique) ===
JAMMING ACTIVADO, NUMERO DE JAMMERS, C/I TOTAL [dB],
CINR CON JAMMING [dB], DEGRADACION JAMMING [dB],
EFECTIVIDAD JAMMING, SEPARACION ANGULAR [°], etc.

=== SECCIÓN 6: PÉRDIDAS (8 columnas) ===
Σ PÉRDIDAS EXTRA [dB], FEEDER RF [dB], DESALINEACIÓN ANTENA [dB], etc.
```

### 🎯 Sistema de Jamming Modular Completo

#### **Spot Jamming Operacional**
- **SpotJammingCalculator**: Clase dedicada con cálculos C/I precisos
- **Discriminación Angular FCC**: Implementación oficial ITU-R S.465
- **Modos B1/B2**: Cálculo C/I para Satélite→Estación y Terminal→Satélite
- **CINR Combinado**: C/I + N usando fórmula `CINR = -10*log10(10^(-C/N/10) + 10^(-C/I/10))`

#### **Evaluación de Efectividad**
- 🔴 **EFECTIVO**: CINR < 10 dB (servicio severamente degradado)
- 🟡 **MODERADO**: CINR 10-15 dB (zona crítica)  
- 🟢 **INEFECTIVO**: CINR > 15 dB (servicio normal)

### 🔬 Validaciones Técnicas Completadas

#### **Testing de Suavizado CINR**
```python
# Caso validado: LEO con jammer 60 dBW
✅ Antes: CINR 7.38 dB → salto brusco → 0.17 dB  
✅ Ahora: CINR 7.38 dB → transición suave → 7.2 dB → 6.8 dB

# Degradación responsiva validada
✅ Antes: Degradación constante ~10.47 dB
✅ Ahora: Degradación variable 4.5-15.2 dB según condiciones
```

#### **Validación FCC Discriminación**
```python
# ITU-R S.465 implementado y validado:
✅ θ = 2° → G(2°) = 21.47 dB (discriminación angular)
✅ θ = 4° → G(4°) = 14.0 dB  
✅ Reducción 4°→2° → +7.5 dB interferencia (correcto)
```

### 📈 Métricas Dinámicas en Tiempo Real

#### **Física Orbital Realista**
- **Rotación Terrestre**: Implementada con física correcta (0.004167°/s) y escalado temporal 100x
- **Dinámica LEO/GEO**: Mecánica orbital real usando v=√(μ/r), períodos ~95min para LEO 550km
- **Sincronización Multi-Cuerpo**: LEO + Tierra + GEO rotan coordinadamente con física apropiada
- **Control Temporal Avanzado**: Resolución 0.1s con sensibilidad ajustable (0.1x-5.0x)

#### **Cálculos de Enlaces Completos**
- **Métricas Básicas**: FSPL, C/N0, C/N, Eb/N0, latencias, Doppler
- **MODCOD Adaptativo**: Tabla completa con eficiencias espectrales y Eb/N0 requerido
- **Geometría Precisa**: Elevación corregida por rotación terrestre, distancia slant, visibilidad  
- **Arquitectura Multi-Constelación**: Framework preparado para múltiples satélites

## 📊 Métricas y Modelos (Implementación Actual)

| Categoría | Implementado | Próxima Expansión |
|-----------|--------------|-------------------|
| **Dashboard CSV** | **84/146/53 columnas**, **suavizado CINR**, **labels 1-decimal** | Multi-jammer analytics, series temporales |
| **Geometría** | Elevación, rango slant, visibilidad, corregida por rotación terrestre | Seguimiento multi-satélite, inclinación orbital |
| **Dinámica** | Velocidad orbital realista, períodos, rotación terrestre (0.004167°/s) | Vectores velocidad orbital, rate de rango, Doppler avanzado |
| **Potencia** | EIRP efectivo con back-off entrada/salida, EIRP saturado | Control potencia avanzado, beam steering |
| **Pérdidas** | FSPL + 7 categorías configurables (feeder, desalineación, atmosférica, lluvia, polarización, apuntamiento, implementación) | Modelos atmosféricos ITU-R, estadísticas rain fade |
| **Ruido** | Descomposición completa T_sys, T_rx, T_sky, N0 | Exceso temperatura lluvia, degradación interferencia |
| **Rendimiento** | C/N0, C/N, Eb/N0, análisis margen, capacidad Shannon, eficiencia espectral | Curvas BER, codificación adaptativa, métricas QoS |
| **Jamming** | **Spot Jamming**, **discriminación FCC**, **C/I calculado**, **CINR suavizado** | Barrage Jamming, Smart Jamming, multi-jammer |
| **Latencia** | One-way, RTT con delays procesamiento y switching | Latencias red, buffering, delays adaptativos |
| **Interferencia** | **C/I, C/(N+I), jammers terrestres**, **evaluación efectividad** | Agregación multi-jammer, ataques coordinados |

## 🗺️ Progreso Implementación Escenarios

### ✅ **Escenario 1: Validación Fundamental LEO** *(Completado + Dashboard Optimizado)*
- **Status**: ✅ **COMPLETADO CON MEJORAS MAYORES**
- **Implementado**: 
  - Órbitas LEO 550km y GEO 35,786km realistas con física correcta
  - Rotación terrestre sincronizada con dinámica orbital
  - Presupuesto enlace completo: FSPL, C/N0, C/N, Eb/N0, latencias
  - Selección adaptativa MODCOD con análisis eficiencia espectral
  - **Dashboard CSV**: 53/84/146 columnas organizadas por secciones
  - **Suavizado CINR**: Algoritmos anti-discontinuidad implementados
  - **Recomendaciones Dinámicas**: Lógica basada en thresholds de degradación
- **Validado**: Mecánica orbital, cálculos RF, geometría, exportación profesional

### ✅ **Escenario 2: Discriminación Angular FCC con Jammer Terrestre** *(Base Operacional)*
- **Status**: ✅ **SPOT JAMMING COMPLETAMENTE FUNCIONAL**
- **Implementado**:
  - **SpotJammingCalculator**: Cálculos C/I precisos para modos B1/B2
  - **Discriminación Angular FCC**: ITU-R S.465 oficial implementado
  - **CINR Combinado**: C/I + N con fórmula estándar
  - **Evaluación Efectividad**: Estados EFECTIVO/MODERADO/INEFECTIVO
  - **Sistema Modular**: JammerSystem.py independiente y reutilizable
  - **Visualización Dinámica**: Status con colores y métricas en tiempo real
  - **Exportación Completa**: 11 columnas adicionales de análisis jamming
- **Validado**: Discriminación FCC, cálculos C/I, CINR suavizado, export CSV

### ⏳ **Escenarios 3-11: Evolución Planificada**
3. **LEO Mega-Constelación** con Probabilidad de Outage
4. **NB-IoT Multi-Beam** con Reúso de Frecuencia  
5. **Starlink Real-World Validation** con Actualizaciones Software
6. **UPA Arrays** con Beam Pointing Realista
7. **Nearest vs Random Jamming** Schemes
8. **A-FFHR Military Anti-Jamming**
9. **Ultra-Dense LEO Optimization**
10. **Rain Effects** con Energy Dispersal
11. **Multi-Technique Integrated** Analysis

Cada escenario añade entradas configurables, nuevas métricas y documentación explicativa para preservar trazabilidad física y claridad conceptual.

## 🧩 Arquitectura Código (Implementación Actual)
```
JammerSimulator.py (~4,200 líneas - ampliado significativamente)
 ├─ ParameterLoader              (ingesta parámetros JSON con validación)
 ├─ Satellite / Constellation    (modelo orbital + framework multi-constelación)  
 ├─ MultiConstellation           (framework para múltiples sistemas satelitales)
 ├─ LEOEducationalCalculations   (fórmulas centrales: FSPL, C/N0, latencia, Doppler)
 ├─ JammerSimulatorCore          (estado compartido + calculadoras LEO/GEO)
 ├─ SimulatorGUI (Tkinter)       (controles avanzados, gestión tiempo, 35+ métricas, export)
 └─ Dashboard CSV System         (exportación estructurada 84/146/53 columnas)

JammerSystem.py (~450 líneas - nuevo módulo modular)
 ├─ SpotJammingCalculator        (cálculos C/I, discriminación FCC, CINR)
 ├─ JammerConfig                 (configuración completa por jammer)
 ├─ JammerManager                (gestión múltiples jammers)
 └─ JammerWidget/Dialog          (interfaz configuración avanzada)
```

La implementación actual incluye rotación terrestre realista, sincronización multi-cuerpo, control temporal avanzado y **sistema dashboard CSV completamente renovado**. Las extensiones futuras factorizarán módulos jamming adicionales (`barrage_jamming.py`, `smart_jamming.py`, `countermeasures.py`) para mantener claridad educativa.

## ▶️ Flujo de Uso Actual

### 🚀 Inicio y Configuración
1. Ejecutar `python JammerSimulator.py`.
2. Seleccionar modo LEO o GEO.
3. Ajustar EIRP, G/T, frecuencia, ancho de banda y parámetros de pérdidas.

### ⏰ Opciones Control Temporal
- **Modo Automático**: Iniciar animación con dinámica orbital en tiempo real
- **Modo Manual**: Habilitar controles deslizantes para posicionamiento preciso
- **Sensibilidad**: Ajustar escala temporal (0.1x-5.0x) para análisis detallado
- **Arrastrar timeline**: Saltar a momentos específicos (resolución 0.1s)

### 🎯 Funciones Jamming (Nuevo)
- **Añadir Jammers**: Configuración tipo Spot con potencia, posición, frecuencia
- **Análisis C/I**: Cálculos automáticos de interferencia en tiempo real
- **Visualización Efectividad**: Status con colores (EFECTIVO/MODERADO/INEFECTIVO)
- **Discriminación Angular**: Modelado FCC oficial con separación angular

### 📊 Análisis y Exportación Avanzada
- **Métricas Dashboard**: 35+ métricas en tiempo real incluyendo geometría orbital y calidad enlace
- **Configuración Avanzada**: MODCOD, back-off, temperaturas ruido, delays procesamiento
- **Export Estructurado**: Series temporales completas a CSV/XLSX para análisis offline
- **Dashboard CSV**: 53/84/146 columnas organizadas por secciones según configuración

## ⚡ Instalación Rápida
Mínimo: Python 3.10+ (Tkinter usualmente incluido). Opcional: `openpyxl` para export XLSX.
```bash
pip install openpyxl
python JammerSimulator.py
```
En Windows, instalar distribución oficial Python si falta Tkinter.

## 🗃️ Parámetros (JSON)
`SimulatorParameters.json` centraliza altitudes, EIRP, G/T y valores base. Los próximos parámetros de pérdidas, ruido e interferencia lo extenderán de manera compatible hacia atrás.

**Nuevas Secciones Añadidas**:
```json
{
  "Jamming": {
    "enabled": false,
    "spot_jamming": {
      "power_dbm": 40.0,
      "antenna_gain_dbi": 15.0,
      "frequency_ghz": 12.0,
      "position": {"distance_from_gs_km": 50.0, "azimuth_deg": 45.0}
    },
    "discrimination": {
      "angular_separation_deg": 2.0,
      "polarization_isolation_db": -4.0
    },
    "effectiveness_thresholds": {
      "cinr_critical_db": 10.0,
      "cinr_acceptable_db": 15.0
    }
  }
}
```

## 🧭 Principios de Diseño
- **Transparencia numérica** (mostrar antes de sobre-abstraer).
- **Simplicidad antes de fidelidad física máxima** (ej. escalado orbital estético manteniendo física correcta).
- **Capas graduales**: cada nuevo término (pérdida, ruido, interferencia) acompañado de fundamento y fórmula.
- **Export estructurado** para hojas cálculo / notebooks científicos.
- **Suavizado realista**: Eliminación de discontinuidades artificiales en métricas críticas.

## 🚀 Extensibilidad Planificada (Resumen Técnico)

### 📈 Próximas Funcionalidades Técnicas
- **Doppler**: derivado de velocidad orbital y componente radial → ilustración compensación.
- **Modelo pérdidas**: suma dB flexible con toggles por componente y anotaciones rango típico.
- **Ruido**: descomposición T_sys = T_ant + T_rx + (∑ pérdidas × temperatura equivalente).
- **Interferencia**: densidad espectral configurable, múltiples fuentes agregadas linealmente.
- **Métricas avanzadas**: Eb/N0, margen, capacidad Shannon, utilización espectral.
- **Cobertura**: área por satélite y dimensionamiento constelación para elevación mínima.
- **Failover híbrido**: selección enlace automática basada en latencia, margen, interferencia.

### 🎯 Mejoras Dashboard CSV
- **Análisis Multi-Jammer**: Agregación interferencia de múltiples fuentes simultáneas
- **Series Temporales**: Tracking evolutivo de métricas críticas vs tiempo orbital
- **Estadísticas Avanzadas**: Percentiles, outage probability, availability metrics
- **Optimización Automática**: Recomendaciones basadas en análisis histórico

## 📤 Exportación Datos (Mejorada Significativamente)

### 📊 Estructura CSV Actual
**Campos organizados por secciones**: tiempo, modo, ángulo orbital/longitud GEO, elevación, visibilidad, distancia, FSPL, latencia, C/N0, C/N, EIRP, G/T, frecuencia, ancho banda, todos componentes pérdidas, valores back-off, parámetros temperatura, selección MODCOD, Eb/N0, análisis margen, capacidad Shannon, eficiencia espectral.

**Nuevos campos jamming**: C/I total, CINR con jamming, degradación jamming, efectividad, separación angular, discriminación FCC, EIRP jammer, tipo jammer.

**Métricas avanzadas**: Latencias RTT, cálculos Doppler, velocidad orbital, rates angulares, ventanas visibilidad, evaluación calidad enlace, utilización rendimiento vs límites teóricos.

### 💎 Formatos Export
- **CSV**: Datos estructurados (53/84/146 columnas según configuración)
- **XLSX**: Formato profesional con cabeceras negrita, columnas auto-ajustadas, paneles congelados (cuando `openpyxl` disponible)

## 🤝 Contribuciones
Mientras se estabiliza el núcleo, damos bienvenida a contribuciones enfocadas en:
- **Refactor modular** (paquetes cálculo externos).
- **Implementaciones pérdidas y ruido** (modelos simplificados inspirados ITU-R).
- **Unit tests para fórmulas** (pytest).
- **Visuales multi-satélite / handover**.
- **Internacionalización GUI básica** (i18n).

Por favor abrir issues describiendo: (1) propósito educativo, (2) fórmula y referencia, (3) impacto UI/export.

## ⚠️ Limitaciones Actuales
- **Geometría 2D simplificada** (estación terrestre en ecuador, sin modelado inclinación real aún).
- **Pérdidas atmosféricas limitadas** (lluvia y misc aplicadas como términos simples, no modelos ITU-R completos).
- **Validación entrada limitada** (rangos/tipos) presentemente.
- **Single-satellite focus** (multi-constelación preparado pero no completamente implementado).

## 🏁 Roadmap Corto Plazo (Próxima Implementación)

### 🎯 Prioridades Inmediatas
1. **Barrage Jamming**: Implementar jamming banda ancha con modeling de densidad espectral
2. **Smart/Adaptive Jamming**: Técnicas ML/SDR con respuesta dinámica
3. **Multi-Jammer Analytics**: Agregación interferencia y análisis coordinado
4. **Dashboard Avanzado**: Visualización métricas jamming en tiempo real
5. **Contramedidas Básicas**: Control potencia, frequency hopping, beam steering

### 📚 Investigación y Desarrollo
**Status investigación**: Análisis técnico preparado para research Perplexity sobre regulaciones FCC y técnicas jamming avanzadas.

**Focus técnico**: Modelado C/I preciso, geometría jammer terrestre, algoritmos tracking, scenarios ataques coordinados.

## 📄 Licencia
TBD (provisional). Recomendación: licencia permisiva (MIT / Apache-2.0) para fomentar adopción educativa.

---
Este README describe la dirección holística sin bloquearse en secciones "escenario" rígidas: la evolución es incremental y acumulativa, enfocada en hacer observable cada capa física y operacional de ecosistemas satelitales modernos mientras prepara fundación para análisis de amenazas y resistencia. **La versión 2.2.0 introduce mejoras significativas en dashboard CSV, suavizado CINR y sistema jamming modular que establecen las bases para análisis avanzado de interferencia.**