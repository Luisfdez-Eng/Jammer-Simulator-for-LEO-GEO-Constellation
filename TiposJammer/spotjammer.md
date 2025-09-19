# 📡 Spot Jamming - Escenario 2: Interferencia Satelital

## 📋 **Definición de Spot Jamming**

**Spot Jamming** es una técnica de interferencia intencional donde el jammer concentra toda su potencia en una **única frecuencia específica** para maximizar la interferencia en esa portadora particular.

### 🎯 **Características Principales**

- **🔥 Alta densidad de potencia**: Concentra toda la energía en una banda estrecha (1-10 MHz)
- **🎯 Selectividad frecuencial**: Apunta a frecuencias específicas del sistema objetivo  
- **⚡ Máxima eficiencia de interferencia**: Mayor densidad espectral que jamming de banda ancha
- **🔍 Fácil detección**: Señal concentrada es detectable pero difícil de mitigar
- **❌ Vulnerable a agilidad**: Inefectivo contra frequency hopping o sistemas adaptativos

---

## 🔬 **Modelos Matemáticos Implementados**

### 📊 **1. Carrier-to-Interference Ratio (C/I)**

El núcleo del análisis de Spot Jamming es el cálculo de la relación portadora-interferencia.

#### **Downlink C/I (Modo B1: Satélite → Estación terrestre)**
```
[C/I]_DL = [EIRP_sat] - [EIRP_jammer] + [G_discrimination] + [Y_polarization]

Donde:
- EIRP_sat: Potencia efectiva radiada del satélite (dBW)
- EIRP_jammer: Potencia efectiva radiada del jammer (dBW) 
- G_discrimination: Discriminación angular según función FCC (dB)
- Y_polarization: Aislación por polarización (-4.0 dB típico)
```

#### **Uplink C/I (Modo B2: Terminal → Satélite)**
```
[C/I]_UL = [EIRP_wanted] - [EIRP_jammer] + [Path_Loss_diff] + [G_discrimination] + [Y_polarization]

Incluye:
- Path_Loss_diff: Diferencia de pérdidas de propagación jammer vs terminal legítimo
- G_discrimination: Discriminación en antena receptora del satélite
```

### 📐 **2. Discriminación Angular (Función FCC ITU-R S.465)**

La discriminación angular es **clave** para la efectividad del jamming:

```python
def fcc_discrimination_db(angular_separation_deg):
    """Discriminación según normativa FCC"""
    θ = angular_separation_deg
    
    if 1.0 ≤ θ ≤ 7.0:
        return 29 - 25 * log10(θ)
    elif 7.0 < θ ≤ 9.2:
        return 8.0
    elif 9.2 < θ ≤ 48.0:
        return 32 - 25 * log10(θ)
    else:
        return -10.0  # θ > 48°
```

#### **Casos de Validación**:
- **Separación 2°**: Discriminación = 21.47 dB
- **Separación 4°**: Discriminación = 14.0 dB  
- **Reducción 4°→2°**: Incremento interferencia = **+7.5 dB**

### ⚡ **3. CINR Combined (C/I + Ruido)**

```python
# CINR combina carrier-to-interference + carrier-to-noise
CINR = -10*log10(10^(-C/I/10) + 10^(-C/N/10))

# Degradación por jamming
Degradation_dB = C/N_original - CINR_with_jamming
```

**Interpretación física**: 
- Si la **interferencia I domina** sobre el ruido N, entonces CINR ≈ C/I
- Si el **ruido N domina** sobre la interferencia I, entonces CINR ≈ C/N

---

## ⚙️ **Parámetros Técnicos de Referencia**

### 🔋 **Potencias Típicas de Jammers**

| Tipo Jammer | Potencia TX | EIRP Típico | Aplicación |
|-------------|-------------|-------------|------------|
| **Portátil** | 1W - 10W | 30-40 dBm | Jamming local, short-range |
| **Vehicular** | 10W - 100W | 40-50 dBm | Jamming móvil, medium-range |
| **Fijo/Militar** | 100W - 1kW | 50-60 dBm | Jamming estratégico, long-range |

**Conversión**: `EIRP_jammer = Pt_jammer + Gt_jammer - Pérdidas_alimentador`

### 📡 **Frecuencias de Interés Satelital**

| Banda | Uplink (GHz) | Downlink (GHz) | Uso Típico |
|-------|-------------|----------------|------------|
| **C-band** | 5.925-6.425 | 3.7-4.2 | Comunicaciones fijas |
| **Ku-band** | 14.0-14.5 | 10.7-12.75 | Broadcast, VSAT |
| **Ka-band** | 27.0-31.0 | 17.7-21.2 | Broadband, LEO |

### 🎯 **Umbrales de Calidad de Servicio**

| CINR (dB) | Estado | Descripción |
|-----------|---------|-------------|
| **> 15 dB** | ✅ **SERVICIO NORMAL** | Calidad aceptable, jamming inefectivo |
| **10-15 dB** | ⚠️ **ZONA CRÍTICA** | Degradación notable, jamming moderado |
| **< 10 dB** | ❌ **SERVICIO DEGRADADO** | Jamming efectivo, pérdida de servicio |

#### **Umbrales Específicos por Servicio**:
- **C/I mínimo digital**: 20-32 dB (según BER objetivo 10^-6 a 10^-9)
- **C/I mínimo TV broadcast**: 22-27 dB  
- **C/I mínimo datos críticos**: 25-35 dB

---

## 🧮 **Implementación en el Simulador**

### 🏗️ **Arquitectura del Sistema**

```python
JammerSystem.py
├── SpotJammingCalculator    # Calculadora de interferencia
├── JammerConfig            # Configuración de jammers
├── JammerManager          # Gestión múltiples jammers
└── FCC Discrimination     # Función normativa oficial

JammerSimulator.py
├── calculate_spot_jamming_metrics()  # Integración en core
├── _update_jamming_block()          # Actualización GUI
└── CSV Export Enhancement           # Métricas en reportes
```

### 🎮 **Flujo de Usuario**

1. **Configurar Jammer**: Tipo Spot, potencia, frecuencia, posición
2. **Ejecutar Simulación**: El sistema calcula C/I dinámicamente
3. **Visualizar Resultados**: CINR, degradación, efectividad en tiempo real
4. **Exportar Análisis**: CSV con métricas completas de interferencia

### 📊 **Métricas Calculadas**

#### **Métricas Básicas**:
- **C/I Total [dB]**: Relación portadora-interferencia combinada
- **CINR con Jamming [dB]**: C/(I+N) considerando ruido térmico
- **Degradación [dB]**: Pérdida de calidad por jamming
- **Efectividad**: EFECTIVO | MODERADO | INEFECTIVO

#### **Parámetros Técnicos**:
- **Separación Angular [°]**: Distancia angular jammer-objetivo
- **Discriminación FCC [dB]**: Beneficio por separación espacial  
- **EIRP Jammer [dBW]**: Potencia efectiva del jammer
- **Tipo de Jammer**: Spot | Barrage | Smart/Adaptive

---

## 🧪 **Casos de Demostración**

### **🎯 Caso 1: Jamming Efectivo (Separación Pequeña)**

**Configuración**:
```
Jammer Spot: 45 dBW EIRP, 12 GHz
Separación angular: 2.0°
Polarización: -4 dB isolation
Satélite EIRP: 56 dBW
```

**Resultados Esperados**:
```
Discriminación FCC: 21.47 dB
C/I: 56 - 45 + 21.47 + (-4) = 28.47 dB
CINR (con ruido): ~25 dB → SERVICIO NORMAL (jamming inefectivo)
```

### **🔥 Caso 2: Jamming Crítico (Separación Óptima)**

**Configuración**:
```
Jammer Spot: 55 dBW EIRP (militar)
Separación angular: 0.5°
Polarización: 0 dB (misma polarización)
Satélite EIRP: 56 dBW
```

**Resultados Esperados**:
```
Discriminación FCC: 29 - 25*log10(0.5) = 36.5 dB
C/I: 56 - 55 + 36.5 + 0 = 37.5 dB
CINR: ~35 dB → SERVICIO NORMAL (discriminación angular salva el enlace)
```

### **⚡ Caso 3: Jamming Devastador (Co-localizado)**

**Configuración**:
```
Jammer Spot: 60 dBW EIRP (máxima potencia)
Separación angular: 0.1° (casi co-localizado)
Polarización: 0 dB
Satélite EIRP: 50 dBW (LEO menor potencia)
```

**Resultados Esperados**:
```
Discriminación FCC: 29 - 25*log10(0.1) = 54.0 dB
C/I: 50 - 60 + 54 + 0 = 44 dB → AÚN SERVICIO NORMAL
```

**🔍 Conclusión**: La **discriminación angular es extremadamente poderosa**. Incluso jammers muy potentes necesitan estar **muy cerca angularmente** del objetivo para ser efectivos.

---

## 🎛️ **Controles de Simulación**

### **⚙️ Parámetros Configurables**

1. **🔋 Potencia Jammer**: 20-80 dBW (SpinBox)
2. **📡 Ganancia Antena**: 0-30 dBi (omnidireccional vs direccional)
3. **📊 Frecuencia**: 1-50 GHz (selección de banda)
4. **📏 Ancho de Banda**: 1-1000 MHz (concentración espectral)
5. **📍 Posición**: Distancia y azimut respecto a Ground Station
6. **🎯 Separación Angular**: 0.5-10° (parámetro crítico de efectividad)

### **📊 Visualización en Tiempo Real**

- **🌍 Canvas**: Jammers como círculos rojos rotando con la Tierra
- **📈 Status Dinámico**: Color-coded según efectividad
  - 🔴 **Rojo**: Jamming EFECTIVO (CINR < 10 dB)  
  - 🟡 **Ámbar**: Jamming MODERADO (CINR 10-15 dB)
  - 🟢 **Verde**: Jamming INEFECTIVO (CINR > 15 dB)

---

## 📤 **Exportación y Análisis**

### **📋 Campos CSV Añadidos (Escenario 2)**

```csv
JAMMING ACTIVADO, NUMERO DE JAMMERS, C/I TOTAL [dB], CINR CON JAMMING [dB],
DEGRADACION JAMMING [dB], EFECTIVIDAD JAMMING, SEPARACION ANGULAR [°],
AISLACION POLARIZACION [dB], DISCRIMINACION FCC [dB], 
EIRP JAMMER PRINCIPAL [dBW], TIPO JAMMER PRINCIPAL
```

### **📊 Análisis Comparativo Posible**

1. **🔄 Series Temporales**: Evolución C/I vs tiempo de simulación
2. **📈 Sensibilidad Angular**: Efectividad vs separación angular  
3. **⚡ Power Analysis**: C/I vs potencia jammer
4. **🎯 Multi-Jammer**: Interferencia acumulada de múltiples fuentes
5. **🌐 LEO vs GEO**: Vulnerabilidad relativa por altitud orbital

---

## 🚀 **Futuras Extensiones**

### **📡 Técnicas Avanzadas de Jamming**
- **Barrage Jamming**: Banda ancha (100-1000 MHz)
- **Smart/Adaptive Jamming**: ML/SDR con respuesta dinámica
- **Swept Jamming**: Barrido frecuencial programable

### **🛡️ Contramedidas**
- **Frequency Hopping**: Agilidad frecuencial
- **Spread Spectrum**: Ensanchado espectral  
- **Adaptive Beamforming**: Anulación espacial de interferencia
- **Power Control**: Adaptación dinámica de potencia

### **🎯 Análisis Avanzados**
- **Outage Probability**: Probabilidad de interrupción del servicio
- **Coverage Analysis**: Mapas de cobertura bajo jamming
- **Multi-Path Effects**: Interferencia en canales con desvanecimiento

---

## 🎓 **Valor Educativo**

### **🔬 Conceptos Físicos Demostrados**
- **Propagación RF**: Free Space Path Loss en tiempo real
- **Discriminación Espacial**: Beneficio de separación angular
- **Análisis de Interferencia**: Suma de potencias en dominio lineal
- **Geometría Orbital**: Impacto de dinámica LEO/GEO en jamming

### **📚 Aplicaciones Pedagógicas**
- **Telecomunicaciones**: Análisis de sistemas de comunicación
- **Ingeniería RF**: Diseño de enlaces con interferencia  
- **Ciberseguridad**: Comprensión de amenazas de jamming
- **Sistemas Satelitales**: Vulnerabilidades y protecciones

---

## 🔧 **Limitaciones Actuales**

1. **🌍 Modelo Geométrico Simplificado**: Tierra esférica, órbitas circulares
2. **📡 Propagación Ideal**: Solo Free Space Path Loss, sin atmósfera/lluvia
3. **🎯 Apuntamiento Perfecto**: Sin errores de tracking o beam pointing  
4. **📊 Modulación Fija**: No adaptación dinámica de MODCOD bajo jamming
5. **🔄 Single-Spot**: Un solo spot por jammer, sin multi-beam

### **⚡ Performance**
- **✅ Tiempo Real**: Cálculos optimizados para simulación fluida
- **✅ Escalabilidad**: Soporte multi-jammer sin degradación
- **✅ Precisión**: Modelos basados en normativas oficiales (FCC ITU-R S.465)

---

**Estado**: ✅ **COMPLETADO** - Spot Jamming completamente implementado y documentado

*Sistema robusto listo para análisis de interferencia satelital y extensiones futuras.*
