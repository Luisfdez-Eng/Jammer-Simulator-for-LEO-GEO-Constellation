## **1. NORMATIVAS FCC PARA DISCRIMINACIÓN ANGULAR**

### Límites de Discriminación Angular ITU-R/FCC

Según las normativas encontradas, los límites críticos son:
```typescript
Función de Ganancia FCC Estandarizada:
G(θ°) = {
  29 - 25·log(θ)     para 1° ≤ θ ≤ 7°
  8                   para 7° < θ ≤ 9.2°  
  32 - 25·log(θ)     para 9.2° < θ ≤ 48°
  -10                 para 48° < θ ≤ 180°
}
```
### **Aplicación Práctica para tu Simulador:**
- **Separación mínima LEO**: 2-4° para evitar interferencia significativa
- **Separación mínima GEO**: 4-7° según ITU-R S.738
- **Umbral de coordinación**: ΔT/T > 6% requiere coordinación
- **Criterio C/I**: Para servicios digitales típicamente C/I > C/N + 12.2 dB

***

## **🎯 2. TIPOS DE JAMMERS TERRESTRES IMPLEMENTABLES**

### Clasificación por Técnica de Jamming

#### **A. Barrage Jamming (Jamming de Barrera)**
````typescript
Características:
- Banda Ancha: Cubre 100-1000 MHz simultáneamente
- Potencia Distribuida: EIRP 40-60 dBW total
- Efectividad: Baja densidad espectral pero amplia cobertura
- Uso: Contra múltiples frecuencias o frequency hopping
- Implementación: Noise-like signal across wide bandwidth
````

#### **B. Spot Jamming (Jamming Puntual)**  
````typescript
Características:
- Banda Estrecha: 1-10 MHz de ancho de banda
- Potencia Concentrada: EIRP 50-70 dBW en banda objetivo
- Efectividad: Alta densidad espectral, muy efectivo
- Uso: Contra frecuencia específica conocida
- Implementación: High-power CW o modulated signal
````

#### **C. Smart/Adaptive Jamming (Jamming Inteligente)**
````typescript
Características:  
- Respuesta Dinámica: Se adapta a contramedidas del objetivo
- Potencia Variable: Ajusta según efectividad detectada
- Técnicas: Frequency following, power control, pattern matching
- Uso: Contra sistemas con defensas anti-jamming
- Implementación: SDR-based con algoritmos ML
````

***

## **📡 3. MODELOS DE ANTENAS JAMMER**

### **Antenas Omnidireccionales**
````typescript
Características Típicas:
- Ganancia: 0-3 dBi (patrón circular horizontal)  
- Cobertura: 360° azimut, ~120° elevación
- VSWR: <2:1 en banda operación
- Polarización: Vertical/Horizontal/Circular
- Ventaja: Cobertura amplia sin apuntamiento
- Desventaja: Menor ganancia direccional
````

### **Antenas Direccionales**
````typescript
Características para Jammers:
- Ganancia: 15-30 dBi (parabólica/array) 
- Beamwidth: 3-15° según ganancia
- Side lobes: <-20 dB típico
- Tracking: Manual/automático
- Ventaja: Alta ganancia direccional, menor potencia requerida
- Desventaja: Requiere apuntamiento preciso
````

***

## **⚡ 4. PARÁMETROS TÉCNICOS REALISTAS PARA IMPLEMENTACIÓN**

### **Rangos de EIRP por Tipo de Jammer**

#### **Comerciales/Civiles (Prohibidos pero Disponibles)**
````typescript
Jammer Portátil:
- EIRP: 20-40 dBW (0.1-10 W)
- Alcance efectivo: 1-10 km vs satélites
- Bandas: GPS (1.5 GHz), WiFi (2.4/5 GHz), Cellular

Jammer Vehicular:
- EIRP: 40-50 dBW (10-100 W)  
- Alcance efectivo: 10-50 km vs satélites
- Bandas: Múltiples simultáneas
````

#### **Militares/Estatales**
````typescript
Jammer Táctico:
- EIRP: 50-70 dBW (100 W - 10 kW)
- Alcance efectivo: 50-500 km vs satélites
- Bandas: 2-18 GHz cobertura completa

Jammer Estratégico:
- EIRP: 70-90 dBW (10-100 kW)
- Alcance efectivo: 500+ km vs satélites  
- Bandas: Múltiples con beam steering
````

### **Parámetros para tu Simulador LEO (12 GHz)**
````typescript
Configuraciones Realistas:

Jammer Básico:
- EIRP: 43 dBW (20 W)
- Antena: Omnidireccional 3 dBi
- Potencia TX: 40 dBW
- Alcance vs LEO 550km: ~50 km radio terrestre

Jammer Avanzado:  
- EIRP: 63 dBW (2 kW)
- Antena: Direccional 20 dBi
- Potencia TX: 43 dBW  
- Alcance vs LEO 550km: ~500 km radio terrestre

Jammer Militar:
- EIRP: 73 dBW (20 kW)
- Antena: Array steering 25 dBi
- Potencia TX: 48 dBW
- Alcance vs LEO 550km: ~1000 km radio terrestre
````

***

## **🔢 5. CÁLCULOS DE INTERFERENCIA C/I**

### **Ecuación Fundamental C/I para tu Simulador**

````typescript
// Potencia señal útil (satelite → estación terrena)
C = EIRP_sat + G_rx - FSPL_sat_to_GS - L_atm - L_rain

// Potencia interferencia (jammer → estación terrena) 
I = EIRP_jammer + G_rx_jammer_direction - FSPL_jammer_to_GS - L_terrain

// Ratio C/I final
C_I_ratio = C - I  // en dB

// Discriminación angular (depende separación angular)
Angular_Discrimination = G_FCC(separation_angle)
C_I_effective = C_I_ratio + Angular_Discrimination
````

### **Modelo de Propagación Jammer→GS vs Sat→GS**
````typescript
Diferencias Críticas:

Enlace Satelital:
- Distancia: 550 km - 2000 km (LEO dinámico)
- Path Loss: 180-190 dB @ 12 GHz  
- Atmosférica: Minimal (espacio libre)
- Elevación: Variable 5-90°

Enlace Jammer:
- Distancia: 1 km - 1000 km (superficie terrestre)  
- Path Loss: 100-140 dB @ 12 GHz
- Terrain: Significant losses, shadowing
- Elevación: ~0° (horizontal)
````

***

## **📐 6. GEOMETRÍA Y POSICIONAMIENTO**

### **Coordenadas para Jammers en tu Simulador**

````typescript
// Conversión lat/lon a coordenadas cartesianas
function jammer_position_ECEF(lat, lon, alt_m) {
    const Re = 6371000; // Radio terrestre
    const x = (Re + alt_m) * cos(lat) * cos(lon);
    const y = (Re + alt_m) * cos(lat) * sin(lon);
    const z = (Re + alt_m) * sin(lat);
    return {x, y, z};
}

// Cálculo distancia jammer-GS (superficie terrestre)
function distance_jammer_GS(jammer_pos, GS_pos) {
    // Usando fórmula Haversine para distancias terrestres
    const R = 6371; // Radio terrestre en km
    const dLat = (GS_pos.lat - jammer_pos.lat) * Math.PI/180;
    const dLon = (GS_pos.lon - jammer_pos.lon) * Math.PI/180;
    
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(jammer_pos.lat * Math.PI/180) * 
              Math.cos(GS_pos.lat * Math.PI/180) * 
              Math.sin(dLon/2) * Math.sin(dLon/2);
              
    return 2 * R * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
}

// Ángulo de separación angular jammer-satelite desde GS
function angular_separation(sat_az_el, jammer_az_el) {
    // Conversión a coordenadas cartesianas unitarias
    const sat_vector = spherical_to_cartesian(sat_az_el);
    const jammer_vector = spherical_to_cartesian(jammer_az_el);
    
    // Producto punto para ángulo entre vectores
    const cos_angle = dot_product(sat_vector, jammer_vector);
    return Math.acos(cos_angle) * 180/Math.PI; // en grados
}
````

***

## **⚖️ 7. CRITERIOS DE ÉXITO/FALLO DE JAMMING**

### **Umbrales C/I para Diferentes Servicios**

````typescript
Umbrales de Jamming Exitoso:

Comunicaciones de Voz:
- C/I < 12 dB: Degradación notable
- C/I < 6 dB: Comunicación difícil  
- C/I < 0 dB: Jamming exitoso

Datos Digitales:
- C/I < 15 dB: Aumento BER notable
- C/I < 10 dB: Pérdida de paquetes significativa
- C/I < 3 dB: Jamming exitoso

Video/TV:
- C/I < 20 dB: Degradación de imagen
- C/I < 14 dB: Imagen inutilizable
- C/I < 8 dB: Jamming exitoso
````

### **Efectividad vs Elevación Satelital**

````typescript
Factores de Efectividad:

Elevación Baja (5-15°):
- Mayor distancia satelital → Menor C
- Menor discriminación angular → Mayor I_efect  
- Path Loss atmospheric mayor
- Resultado: Jamming MÁS efectivo

Elevación Alta (60-90°):
- Menor distancia satelital → Mayor C
- Mayor discriminación angular → Menor I_efect
- Path Loss atmospheric mínimo  
- Resultado: Jamming MENOS efectivo
````

***

## **🔧 8. IMPLEMENTACIÓN PRÁCTICA PARA TU SIMULADOR**

### **Estructura de Clase Jammer**

````typescript
class SatelliteJammer {
    constructor(config) {
        this.position = {lat: config.lat, lon: config.lon, alt: 0};
        this.power_tx = config.power_tx; // dBW
        this.antenna_gain = config.antenna_gain; // dBi
        this.antenna_type = config.antenna_type; // 'omni', 'directional'
        this.frequency = config.frequency; // Hz
        this.bandwidth = config.bandwidth; // Hz
        this.jamming_type = config.jamming_type; // 'barrage', 'spot', 'smart'
        this.target_satellite = config.target_satellite;
    }
    
    calculateEIRP(direction) {
        let antenna_gain_effective = this.antenna_gain;
        
        if (this.antenna_type === 'directional') {
            // Aplicar patrón direccional
            antenna_gain_effective += this.getDirectionalGain(direction);
        }
        
        return this.power_tx + antenna_gain_effective;
    }
    
    calculateInterference(ground_station, satellite_position) {
        // Distancia jammer → ground station
        const distance_km = this.calculateDistance(ground_station);
        
        // Path Loss
        const path_loss = this.calculatePathLoss(distance_km, this.frequency);
        
        // EIRP efectivo hacia ground station
        const eirp = this.calculateEIRP({target: ground_station});
        
        // Ganancia de antena receptora hacia jammer
        const rx_gain = ground_station.getGainTowards(this.position);
        
        // Discriminación angular
        const separation = this.calculateAngularSeparation(
            ground_station, satellite_position
        );
        const discrimination = this.getFCCDiscrimination(separation);
        
        // Potencia de interferencia recibida
        return eirp + rx_gain - path_loss - discrimination;
    }
    
    getFCCDiscrimination(angle_deg) {
        if (angle_deg >= 1 && angle_deg <= 7) {
            return 29 - 25 * Math.log10(angle_deg);
        } else if (angle_deg > 7 && angle_deg <= 9.2) {
            return 8;
        } else if (angle_deg > 9.2 && angle_deg <= 48) {
            return 32 - 25 * Math.log10(angle_deg);
        } else if (angle_deg > 48) {
            return -10;
        }
        return 0; // Sin discriminación para ángulos muy pequeños
    }
}
````

### **Integración con tu Link Budget Existente**

````typescript
// Extender tu función de link budget existente
function enhanced_link_budget_with_jamming(sat_params, gs_params, jammers) {
    // Cálculo C/N básico (tu código existente)
    const basic_CNR = calculate_basic_link(sat_params, gs_params);
    
    // Cálculo interferencia agregada de todos los jammers
    let total_interference = 0;
    
    jammers.forEach(jammer => {
        if (jammer.isActive && jammer.affectsFrequency(sat_params.frequency)) {
            const interference_power = jammer.calculateInterference(
                gs_params, sat_params.position
            );
            
            // Sumar interferencias en escala lineal
            total_interference += Math.pow(10, interference_power / 10);
        }
    });
    
    // Convertir de vuelta a dB
    const total_interference_dB = 10 * Math.log10(total_interference);
    
    // C/I ratio
    const carrier_power = sat_params.EIRP + gs_params.G_T + basic_path_loss;
    const C_I_ratio = carrier_power - total_interference_dB;
    
    // CINR combinado (C/(N+I))
    const noise_power = basic_CNR - carrier_power;
    const noise_plus_interference = Math.log10(
        Math.pow(10, noise_power/10) + Math.pow(10, total_interference_dB/10)
    ) * 10;
    
    const CINR = carrier_power - noise_plus_interference;
    
    return {
        CNR_clear: basic_CNR,
        C_I_ratio: C_I_ratio,
        CINR_jammed: CINR,
        interference_dB: total_interference_dB,
        jamming_margin: C_I_ratio - 10, // Assuming 10 dB threshold
        jamming_effective: C_I_ratio < 10
    };
}
````

### **Configuraciones de Dashboard**

````typescript
// Métricas adicionales para mostrar en interfaz
const jamming_metrics = {
    // Métricas por jammer individual
    jammer_status: jammers.map(j => ({
        id: j.id,
        active: j.isActive,
        type: j.jamming_type,
        power: j.power_tx,
        distance_km: j.calculateDistance(ground_station),
        effectiveness: j.calculateEffectiveness()
    })),
    
    // Métricas del enlace
    link_degradation: {
        CNR_degradation_dB: basic_CNR - CINR,
        throughput_loss_percent: calculateThroughputLoss(CINR),
        service_available: CINR > minimum_threshold,
        dominant_jammer: findDominantJammer(jammers)
    },
    
    // Recomendaciones adaptativas
    countermeasures: {
        power_control: CINR < 15 ? "Increase power +3dB" : "Current power OK",
        frequency_hop: C_I_ratio < 12 ? "Consider frequency change" : "Current freq OK",
        beam_steering: "Null towards " + dominant_jammer.position
    }
};
````

***

## **📊 9. VALIDACIÓN Y CASOS DE PRUEBA**

### **Escenarios de Validación Críticos**

````typescript
Test Case 1: Separación Angular
- Jammer a 2° del satélite → Discrimination = 21.47 dB
- Jammer a 4° del satélite → Discrimination = 17.96 dB  
- Diferencia esperada: +3.51 dB (confirmar implementación FCC)

Test Case 2: Efectividad vs Distancia  
- Jammer a 10 km → Expected C/I ≈ -20 dB (jamming exitoso)
- Jammer a 100 km → Expected C/I ≈ 0 dB (jamming marginal)
- Jammer a 1000 km → Expected C/I ≈ +20 dB (jamming inefectivo)

Test Case 3: LEO vs GEO Vulnerability
- LEO (550 km): Mayor vulnerabilidad por menor C
- GEO (35,786 km): Menor vulnerabilidad por mayor C
- Factor esperado: ~30 dB diferencia en resistencia
````

### **Benchmarks de Rendimiento**
````typescript
Performance Requirements:
- Cálculo C/I: <10ms por jammer
- Update rate: 10 Hz para simulación en tiempo real
- Múltiples jammers: Soportar hasta 10 simultáneos
- Precision: ±0.5 dB vs cálculos analíticos
````

***

## **🎯 10. RECOMENDACIONES FINALES PARA IMPLEMENTACIÓN**

### **Arquitectura Modular Propuesta**
1. **JammerEngine**: Gestión de múltiples jammers
2. **InterferenceCalculator**: Cálculos C/I con discriminación angular
3. **GeometryHandler**: Coordenadas, distancias, separaciones angulares
4. **DashboardMetrics**: Métricas en tiempo real y recomendaciones

### **Fases de Implementación Sugeridas**
1. **Fase 1**: Jammer único, tipo spot, antena omnidireccional
2. **Fase 2**: Múltiples jammers, discriminación angular FCC
3. **Fase 3**: Tipos de jamming (barrage, smart), antenas direccionales  
4. **Fase 4**: Contramedidas adaptativas y optimización

### **Integración con tu Simulador Actual**
- Mantener tu arquitectura LEO/GEO existente
- Extender cálculos de link budget con componente I (interferencia)
- Añadir controles de interfaz para posicionar/configurar jammers
- Implementar visualización de cobertura de jamming en tu canvas 2D

**Con esta implementación tendrás un simulador de jamming realista que cumple con estándares técnicos internacionales y proporciona análisis cuantitativos precisos del impacto de interferencias terrestres en enlaces satelitales LEO/GEO.**
