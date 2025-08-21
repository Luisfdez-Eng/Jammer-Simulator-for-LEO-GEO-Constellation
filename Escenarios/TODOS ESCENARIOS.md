# ESCENARIO 1. Validación Fundamental LEO. Tx-Rx Simple
La pregunta fundamental que aborda este escenario es aparentemente simple: 

*"¿Puede un satélite comunicarse efectivamente con un terminal terrestre?"*

 Sin embargo, la respuesta depende dramáticamente de si ese satélite está en órbita LEO (550 km de altitud) o GEO (35,786 km de altitud). Este escenario establece las bases técnicas para entender por qué las mega-constelaciones LEO como Starlink han revolucionado las comunicaciones satelitales, mientras que los sistemas GEO tradicionales siguen siendo dominantes para aplicaciones específicas.

Externamente, estamos evaluando la viabilidad básica de comunicación satelital bajo dos paradigmas completamente diferentes: un sistema donde el satélite se mueve constantemente requiriendo handovers frecuentes (LEO), versus un sistema donde el satélite permanece fijo en el cielo desde la perspectiva terrestre (GEO). La pregunta real es: **¿cuál funciona mejor y bajo qué circunstancias?**

![[Pasted image 20250814194904.png]]

### Arquitectura LEO: Proximidad y Dinamismo

En LEO, la geometría del enlace cambia continuamente. Un satélite a 550 km de altitud experimenta distancias que varían desde 550 km cuando está directamente arriba (90° de elevación) hasta 1,815 km cuando está en el horizonte (10° de elevación). Esta variación de **3.3:1 en distancia** se traduce en **10.4 dB de variación en pérdidas de propagación**, creando un enlace inherentemente dinámico.

La ecuación fundamental que rige esta geometría es
```typescript
d = -Re×sin(φ) + √((Re×sin(φ))² + h² + 2hRe)

donde:
- φ es el ángulo de elevación 
- Re el radio terrestre. 
```
 
 
 Esta ecuación revela por qué LEO requiere gestión activa del enlace: las condiciones cambian constantemente.

## **Ventajas Físicas Fundamentales de LEO**

Las **pérdidas de espacio libre** en LEO van desde -153.8 dB (elevación 90°) hasta -163.9 dB (elevación 10°) para frecuencia de 12 GHz. Estos valores son **37.8 a 47.8 dB menores** que GEO, lo que significa que LEO requiere entre **6,000 y 60,000 veces menos potencia** para lograr la misma calidad de enlace. Esta es la ventaja fundamental que ha hecho económicamente viables las mega-constelaciones.

El parámetro EIRP requerido para LEO es dramáticamente menor. Para conseguir C/N = 20 dB, LEO necesita EIRP = -4.0 dBW (0.4 W) mientras que GEO requiere EIRP = 38.0 dBW (6,310 W). Esta diferencia de **42 dB** explica por qué los satélites LEO pueden ser más pequeños, baratos y numerosos.

Sin embargo, LEO introduce complejidades únicas. La **cobertura individual** de cada satélite es minúscula: solo 0.4% de la superficie terrestre con ángulo mínimo de elevación de 30°. Esto requiere **constelaciones masivas** - necesitas aproximadamente 2,500 satélites para cobertura global básica.

Los **handovers** son inevitables cada 5-10 minutos, requiriendo algoritmos sofisticados de gestión de conectividad. Los **efectos Doppler** alcanzan ±304 kHz a 12 GHz, necesitando compensación activa. La **variabilidad temporal** del enlace significa que la calidad oscila entre C/N = 17.4 dB (peor caso) y 27.8 dB (mejor caso).

### Arquitectura GEO: Estabilidad y Simplicidad

**GEO** presenta una geometría fundamentalmente estática. La distancia permanece prácticamente constante en ~40,000 km (variaciones <3%), el ángulo de elevación se mantiene fijo determinado solo por la diferencia de latitud entre la estación terrena y la posición subsatelital. Esta estabilidad simplifica enormemente el diseño del sistema.

Las **pérdidas de espacio libre** en GEO son constantes alrededor de **-201.6 dB** para 12 GHz. Aunque son significativamente mayores que LEO, esta predictibilidad permite diseños optimizados sin necesidad de márgenes dinámicos extensos.


En cuanto a la cobertura, un solo satélite GEO cubre aproximadamente **38% de la superficie terrestre**, proporcionando cobertura continental con solo 3-4 satélites para cobertura global. Esta eficiencia geométrica compensa parcialmente las desventajas de potencia. Los **footprints** son enormes (diámetros de miles de kilómetros), permitiendo servir millones de usuarios simultáneamente.

La **ausencia de handovers** para el mismo servicio simplifica la arquitectura de red. Los **efectos Doppler** son despreciables (<100 Hz), eliminando necesidad de compensación. La **calidad de servicio** es predecible y constante, facilitando planificación de capacidad.

Pero tambien tiene sus limitaciones. El **EIRP requerido** es masivo. Para el mismo C/N = 20 dB que LEO logra con 0.4 W, GEO necesita 6,310 W con antena isotrópica, o 63 W con antena de 20 dB de ganancia. Esta diferencia fundamental limita el número de transponders por satélite y aumenta dramáticamente los costos.

Los **requerimientos G/T** son mucho más estrictos. LEO puede funcionar con G/T = -79.7 dB/K (antena simple, receptor básico), mientras GEO requiere G/T = -42.0 dB/K (antena de 3m, receptor criogénico). Esta diferencia de **37.7 dB** impacta significativamente los costos del terminal de usuario.

### Efectos Atmosféricos Diferenciados

#### **Rain Fading: Impacto Variable**

En LEO, el **path atmosférico** varía con la elevación: desde 10 km (vertical, 90°) hasta 57 km (slant, 10°). Esto permite **márgenes adaptativos**: +2 dB para elevaciones altas, +8 dB para elevaciones bajas. La optimización dinámica es posible.

En GEO, el **path atmosférico** es aproximadamente constante (40-50 km slant). Requiere **margen fijo** de +6 dB típico para 99.9% de disponibilidad. No hay optimización posible - el sistema está sobre-diseñado para buen tiempo y sub-diseñado para condiciones extremas.

#### **Latencia: Factor Crítico Diferenciador**

LEO proporciona **latencias inherentemente bajas**: 3.7 ms (mejor caso) a 12.1 ms (peor caso) solo por propagación. Con enlaces inter-satelitales, Starlink proyecta 16-19 ms end-to-end, **competitivo con fibra terrestre**.

GEO sufre **latencia física inevitable**: ~250 ms mínimo solo por propagación (2×40,000 km a velocidad de luz). Esto hace GEO inadecuado para aplicaciones interactivas, gaming, o comunicaciones en tiempo real.

### Análisis Comparativo de Parámetros Críticos

#### Power Budget Comparison
Para mismo objetivo de calidad (C/N = 20 dB, G/T = 15 dB/K):

**LEO Requirements:**
````typescript
EIRP_LEO = 20 - 15 + 159.6 - 228.6 + 60 = -4.0 dBW
Potencia con antena 0 dBi: 0.4 W
Distancia: 1,100 km (elevación 30°)
Path Loss: -159.6 dB
````

**GEO Requirements:**
````typescript
EIRP_GEO = 20 - 15 + 201.6 - 228.6 + 60 = 38.0 dBW  
Potencia con antena 0 dBi: 6,310 W
Potencia con antena 20 dB: 63 W
Distancia: 40,000 km
Path Loss: -201.6 dB
````



La **ventaja LEO es de 15,848 veces menos potencia requerida** - esto es lo que ha hecho posible la revolución de las mega-constelaciones.

#### Eficiencia de Cobertura Trade-offs

**LEO Coverage:**
- Área por satélite: 0.4% superficie terrestre (φmin = 30°)
- Satélites para cobertura global: ~2,500
- Handover frequency: Cada 5-10 minutos
- Constellation cost: Alto (muchos satélites)

**GEO Coverage:**
- Área por satélite: 38% superficie terrestre
- Satélites para cobertura global: 3-4
- Handover frequency: Nunca (mismo satélite)
- Constellation cost: Bajo (pocos satélites)

#### Arquitectura del Simulado

### **Framework Común Reutilizable**
Este escenario debe establecer un **framework modular** que permita análisis tanto LEO como GEO con la misma base de código. Los elementos comunes incluyen:

- La **ecuación de Friis** fundamental que aplicará a ambos:
````typescript
[Pr] = [EIRP] + [Gr] + [Lp] + [Lsys]
````

- Los **cálculos de EIRP** que usan independientemente de la órbita:
````typescript
[EIRP] = [Gt] + [Pt]
````

 - Los **modelos de ruido** basados en **PN** que son universales:
 ````typescript
PN = kTNBN
````
  


#### Módulos Específicos por Órbita

**LEO Module:** 
- Debe incluir cálculos geométricos dinámicos con `calculate_slant_range(elevation_angle, altitude)`
- gestión de handovers con `determine_handover_triggers(elevation_threshold)`
- efectos Doppler con `calculate_doppler_shift(orbital_velocity, elevation)`

**GEO Module:** Debe incluir cálculos geométricos estáticos con distancia fija, análisis de cobertura continental, y márgenes de desvanecimiento constantes.



El simulador debe generar **métricas comparativas directas**: diferencias de EIRP requerido (esperado ~42 dB ventaja LEO), diferencias de cobertura (LEO ~95x más satélites), diferencias de latencia (LEO ~20x mejor), diferencias de complejidad operativa (GEO mucho más simple).

#### Casos de Validación Críticos

- [ ] **LEO Validation:** Distancias 550-1,815 km ✓, Path loss -153.8 a -163.9 dB ✓, Ventaja vs GEO 37.8-47.8 dB ✓
- [ ] **GEO Validation:** Distancia ~40,000 km ✓, Path loss ~-201.6 dB ✓, Referencia clásica -200 dB ✓
- [ ] **Comparative Validation:** EIRP_LEO < EIRP_GEO - 35 dB ✓, Latency_LEO < Latency_GEO / 10 ✓


Este escenario debe reproducir **casos conocidos de la literatura**: Enlace Starlink típico (EIRP 48 dBW, G/T 0 dB/K, resultado C/N 17-28 dB), Enlace GEO típico (EIRP 55 dBW, G/T 25 dB/K, resultado C/N 15-20 dB).

#### Extensibilidad para Escenarios Futuros

##### **Preparación para Jamming Analysis**

La arquitectura debe permitir **inserción futura de jammers** sin reescribir la física básica. Los cálculos de C/N base deben ser fácilmente extensibles a C/I y CINR. Los modelos geométricos deben soportar **múltiples elementos** (satélites, usuarios, jammers).

##### **Preparación para Constelaciones Híbridas**

El framework debe facilitar **análisis LEO+GEO simultáneo** para escenarios futuros de backup y redundancia. Los módulos deben ser **componibles** para análisis de sistemas híbridos.

Este Escenario 1 establece los **cimientos técnicos sólidos** sobre los cuales se construirán todos los escenarios posteriores, desde jamming simple hasta arquitecturas militares avanzadas, asegurando que cada extensión herede la precisión y validación de estos fundamentos básicos.



# ESCENARIO 2: Primer Contacto con el Enemigo - Jammer Terrestre Básico

## **Objetivo Central**

Introducir el concepto de interferencia maliciosa mediante un **jammer terrestre simple** atacando enlaces LEO y GEO, cuantificando el impacto inicial del jamming en comunicaciones satelitales.

## **Componentes Técnicos**

- **Modelo de Jammer**: Transmisor terrestre con potencia configurable (1W - 1kW)
    
- **Discriminación Angular**: Implementación función FCC `G(θ°) = 29 - 25log(θ)` para separaciones 1°-7°
    
- **Métricas C/I**: Cálculo carrier-to-interference ratio según posición angular jammer-satélite
    
- **Tipos de Ataque**: Barrage jamming (banda completa), Spot jamming (frecuencias específicas)
    

## **Casos de Validación**

- Separación 2° → discriminación 21.47 dB vs jammer
    
- Reducción separación 4°→2° → incremento interferencia +7.5 dB
    
- Combinación interferencia: `(I/C)total = (I/C)uplink + (I/C)downlink`
    

## **Resultados Esperados**

Determinar **umbrales de potencia críticos** donde jammer interrumpe comunicación y comparar vulnerabilidad relativa LEO vs GEO.

---

# ESCENARIO 3: Jammer Inteligente Adaptativo - Smart Jamming

## **Objetivo Central**

Analizar **jammers que se adaptan dinámicamente** al sistema satelital, detectando patrones de comunicación y optimizando su estrategia de ataque en tiempo real.

## **Componentes Técnicos**

- **Smart Jammer**: Sensor espectral + algoritmo de targeting adaptativo
    
- **Detection Algorithms**: Detección automática de portadoras activas y patrones de tráfico
    
- **Adaptive Power**: Distribución dinámica de potencia jamming según efectividad
    
- **Frequency Following**: Seguimiento y ataque a frequency hopping básico
    

## **Escenarios de Ataque**

- **Pulse Jamming**: Ataques sincronizados con detección de transmisiones
    
- **Swept Jamming**: Barrido espectral inteligente siguiendo actividad
    
- **Protocol Exploitation**: Aprovechamiento de períodos de sincronización y handover
    

## **Métricas de Efectividad**

- Tiempo de detección del jammer: objetivo <1 segundo
    
- Degradación C/I bajo ataque adaptativo vs ataque fijo
    
- Capacidad residual del enlace bajo jamming inteligente
    

---

# ESCENARIO 4: Guerra Atmosférica - Jamming + Condiciones Adversas**

## **Objetivo Central**

Modelar cómo **condiciones atmosféricas extremas potencian la efectividad del jamming**, creando escenarios de vulnerabilidad máxima donde factores naturales y artificiales se combinan.

## **Componentes Técnicos**

- **Rain Attenuation**: Modelos ITU-R para Ku-band (-6.22 dB @ 42mm/h) y C-band (-0.64 dB)
    
- **Ionospheric Effects**: Scintillation, absorción, efectos de tormenta solar
    
- **Combined Degradation**: `[C/N]total = [C/N]clear - [Rain] - [Atmospheric] - [Jamming]`
    
- **Opportunistic Jamming**: Jammer que incrementa potencia durante condiciones adversas
    

## **Escenarios Críticos**

- Lluvia intensa + jamming de alta potencia
    
- Tormenta ionosférica + smart jamming coordinado
    
- Múltiples degradantes simultáneos + ataque oportunista
    

## **Objetivos de Análisis**

Determinar **márgenes de supervivencia** mínimos y identificar condiciones donde la comunicación se vuelve imposible.

---

# ESCENARIO 5: Enjambre de Jammers - Ataque Coordinado Masivo**

## **Objetivo Central**

Evaluar sistemas satelitales bajo **ataque coordinado de múltiples jammers** distribuidos geográficamente, simulando guerra electrónica a gran escala.

## **Componentes Técnicos**

- **Multi-Jammer Network**: 3-20 jammers distribuidos geográficamente
    
- **Cooperative Jamming**: Coordinación temporal y espectral entre jammers
    
- **Aggregate Interference**: `I_total = Σ(Pi × Gi × Li)` para todos los jammers
    
- **Geometric Optimization**: Posicionamiento óptimo de jammers para máximo impacto
    

## **Estrategias de Ataque**

- **Surrounding Attack**: Jammers rodeando área objetivo
    
- **Sequential Attack**: Activación temporal secuencial para evadir detección
    
- **Focused Attack**: Concentración de potencia en enlaces críticos
    
- **Distributed Attack**: Dispersión para saturar capacidad de mitigación
    

## **Métricas de Supervivencia**

- Número mínimo de jammers para interrupción completa
    
- Degradación gradual de QoS vs número de jammers activos
    
- Efectividad relativa de diferentes configuraciones geométricas
    

---

# ESCENARIO 6: LEO en Movimiento - Jamming vs Constelación Dinámica**

## **Objetivo Central**

Analizar vulnerabilidades específicas de **constelaciones LEO móviles** donde handovers frecuentes y efectos Doppler crean ventanas de oportunidad para jamming efectivo.

## **Componentes Técnicos**

- **Orbital Dynamics**: Velocidad ~7.5 km/s, período ~90 min, handovers cada 5-10 min
    
- **Doppler Effects**: Shift hasta ±304 kHz @ 12 GHz requiriendo compensación
    
- **Handover Windows**: Períodos de vulnerabilidad durante cambio de satélite
    
- **Mobile Jamming**: Jammers que siguen trayectorias satelitales
    

## **Vulnerabilidades Dinámicas**

- **Handover Jamming**: Ataque durante transiciones satélite-terminal
    
- **Doppler Exploitation**: Jammers que aprovechan compensación de frecuencia
    
- **Tracking Jamming**: Seguimiento de satélites específicos
    
- **Constellation Gaps**: Aprovechamiento de ventanas sin cobertura
    

## **Defensas Dinámicas**

- Selección inteligente de satélite basada en threat assessment
    
- Handover anticipado para evadir jammers conocidos
    
- Diversidad espacial usando múltiples satélites simultáneos
    

---

# ESCENARIO 7: Primeras Defensas - Contramedidas Básicas Anti-Jamming**

## **Objetivo Central**

Implementar y evaluar **técnicas básicas de mitigación** contra jamming: control de potencia, beam steering elemental, y frequency diversity.

## **Técnicas Implementadas**

- **Adaptive Power Control**: Incremento automático de EIRP bajo ataque
    
- **Basic Beam Steering**: Nulling direccional hacia fuentes de interferencia
    
- **Frequency Diversity**: Salto entre frecuencias disponibles
    
- **Satellite Selection**: Elección dinámica del satélite menos interferido
    

## **Algoritmos de Detección**

- **SINR Monitoring**: Detección de degradación anómala
    
- **Spectral Analysis**: Identificación de patrones de interferencia
    
- **Threshold-Based**: Activación de contramedidas por umbrales C/I
    

## **Métricas de Efectividad**

- Tiempo respuesta: <30 segundos para activar contramedidas
    
- Mejora C/I: objetivo +6 dB recuperación mínima
    
- False positive rate: <5% activaciones incorrectas
    

---

# ESCENARIO 8: Guerra Electrónica Militar - Técnicas Avanzadas Anti-Jamming**

## **Objetivo Central**

Implementar **arsenal completo militar anti-jamming**: A-FFHR (Adaptive Frequency-Frequency Hopping and Remapping), beam steering coordinado, y técnicas de camuflaje espectral.

## **Técnicas Militares Avanzadas**

- **A-FFHR Implementation**: Algoritmo de remapping `Ccur,i,j = CA,i[(i + Cpre,i,j) % NA]`
    
- **Coordinated Beam Steering**: Nulling sincronizado multi-satélite
    
- **Spectral Camouflage**: Enmascaramiento de señales como ruido
    
- **Anti-Detection**: Técnicas LPI (Low Probability of Intercept)
    

## **Parámetros A-FFHR**

- Banda n257: 26.5-29.5 GHz, NT=60 canales × 50 MHz
    
- Detección jamming: umbral γ colisiones en NP pulsos
    
- Probability of detection failure: `βfail = Σ(NP choose k)(1/NA)^k(1-1/NA)^(NP-k)`
    
- Objetivo: 35% reducción en PC con NJ=40 canales jammeados
    

## **Validación Militar**

Reproducir condiciones de conflicto real con jammers sofisticados y contramedidas militares estándar.

---

# ESCENARIO 9: Sistema Híbrido LEO-GEO - Redundancia Estratégica**

## **Objetivo Central**

Desarrollar **arquitectura híbrida** donde LEO proporciona servicio primario y GEO actúa como backup robusto cuando LEO está bajo ataque intenso.

## **Arquitectura Dual**

- **LEO Primary**: Servicio normal, baja latencia, alta capacidad
    
- **GEO Backup**: Activación automática cuando LEO falla
    
- **Seamless Handover**: Transición transparente LEO↔GEO
    
- **Load Balancing**: Distribución inteligente según amenazas
    

## **Algoritmos de Failover**

- **Threat Assessment**: Evaluación continua de vulnerabilidad LEO
    
- **Automatic Switching**: Cambio LEO→GEO por umbrales de degradación
    
- **Service Prioritization**: QoS diferenciado por criticidad de aplicación
    
- **Recovery Planning**: Estrategia de retorno LEO cuando amenaza cesa
    

## **Métricas de Resiliencia**

- Tiempo de conmutación: objetivo <10 segundos
    
- Degradación temporal durante handover: <30 dB
    
- Probabilidad de interrupción total: <0.1%
    

---

# ESCENARIO 10: Mega-Constelación Bajo Asedio - Resiliencia Industrial**

## **Objetivo Central**

Simular **ataques masivos coordinados** contra mega-constelaciones (2,000+ satélites) y evaluar resiliencia sistémica usando teoría de percolación y análisis de vulnerabilidad en red.

## **Escala Industrial**

- **Constellation Size**: 2,000-5,000 satélites activos simultáneos
    
- **Massive Jamming**: 50-200 jammers coordinados globalmente
    
- **Network Theory**: Análisis de connectividad y percolación
    
- **System-Level Metrics**: Capacidad residual, fragmentación de red
    

## **Ataques Sistémicos**

- **Infrastructure Targeting**: Ataque a nodos críticos de la constelación
    
- **Cascade Failures**: Fallas en cascada por sobrecarga de tráfico
    
- **Distributed Denial**: Saturación distribuida de la red satelital
    
- **Economic Warfare**: Impacto en viabilidad comercial del sistema
    

## **Resiliencia Emergente**

- **Self-Healing Networks**: Reparación automática de conectividad
    
- **Adaptive Routing**: Enrutamiento dinámico evitando zonas atacadas
    
- **Swarm Intelligence**: Comportamiento colectivo de la constelación
    
- **Economic Sustainability**: Análisis costo-beneficio bajo amenaza continua
    

## **Validación con Casos Reales**

- Starlink en Ucrania: análisis post-mortem de ataques documentados
    
- Parámetros operativos reales: EIRP 48 dBW, >2,300 satélites
    
- Effectiveness de software updates remotas como contramedida
    

---

## **Progresión Lógica del Proyecto**

1. **Escenarios 1-2**: Fundamentos y primer contacto con jamming
    
2. **Escenarios 3-4**: Jammers sofisticados y condiciones adversas
    
3. **Escenarios 5-6**: Sistemas dinámicos y vulnerabilidades móviles
    
4. **Escenarios 7-8**: Contramedidas básicas y militares avanzadas
    
5. **Escenarios 9-10**: Sistemas híbridos y resiliencia a gran escala
    

Cada escenario construye sobre el anterior, incrementando complejidad técnica y realismo operacional, culminando en un análisis completo de guerra electrónica satelital moderna.