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



