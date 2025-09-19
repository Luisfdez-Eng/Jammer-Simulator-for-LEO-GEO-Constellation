"""
Sistema de Jammers para Simulador LEO/GEO
Módulo independiente para gestión de jammers terrestres
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import math
import json
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

# Constante física
SPEED_OF_LIGHT = 299_792_458  # metros/segundo
from enum import Enum

# Alturas y períodos orbitales preestablecidos
class AltitudeType(Enum):
    """Tipos de altitudes para jammers - OPTIMIZADO PARA REALISMO FÍSICO"""
    SURFACE = "Superficie (0-1.5 km)"

# Configuraciones orbitales REALISTAS (eliminadas opciones inviables)
ORBITAL_CONFIGURATIONS = {
    AltitudeType.SURFACE: {
        'altitude_km': 0.001,  # Nivel del mar por defecto
        'orbital_period_min': 0.0,  # Sin movimiento orbital
        'angular_velocity_deg_per_min': 0.25,  # Rotación terrestre: 360°/24h = 0.25°/min
        'viability': 'ALTA',  # Torres, montañas, aviones, estratosférico hasta 1.5km
        'cost_range': '$100K-$10M',
        'deployment_time': 'Días-Semanas',
        'altitude_range_km': [0.0, 1.5],  # Rango realista
        'typical_platforms': ['Torre', 'Montaña', 'Edificio', 'Drone', 'Globo']
    }
    # ELIMINADAS: LEO_TEORICO, MEO, GEO, SUPER_GEO por inviabilidad física/económica
    # Análisis enfocado en altitudes realistas 0-1.5 km solamente
}

class SpotJammingCalculator:
    """Calculadora específica para Spot Jamming con modelos FCC"""
    
    @staticmethod
    def calculate_ci_ratio_downlink(jammer_config: 'JammerConfig', 
                                   satellite_eirp_dbw: float,
                                   satellite_distance_km: float,
                                   jammer_distance_km: float,
                                   frequency_hz: float,
                                   discrimination_angular_real_db: float,
                                   polarization_isolation_db: float = -4.0) -> Dict[str, float]:
        """
        Calcula C/I ratio para downlink (Modo B1: Satélite → Estación terrestre)
        Interferencia: Jammer terrestre → Estación terrestre
        
        CORREGIDO: Usa discriminación angular real en lugar de FCC fija
        """
        # Pérdidas de propagación - Free Space Path Loss
        def calculate_fspl_db(distance_km, freq_hz):
            # Usar fórmula estándar consistente con JammerSimulator.py
            distance_m = distance_km * 1000
            if distance_m <= 0 or freq_hz <= 0:
                return float('inf')
            return 20 * math.log10(4 * math.pi * distance_m * freq_hz / SPEED_OF_LIGHT)
        
        # Potencia recibida de la señal útil (C) - Satélite
        satellite_fspl_db = calculate_fspl_db(satellite_distance_km, frequency_hz)
        C_received_dbw = satellite_eirp_dbw - satellite_fspl_db
        
        # Potencia recibida de interferencia (I) - Jammer terrestre  
        jammer_fspl_db = calculate_fspl_db(jammer_distance_km, frequency_hz)
        I_received_dbw = jammer_config.eirp_dbw - jammer_fspl_db
        
        # CORRECCIÓN: Usar discriminación angular real calculada dinámicamente
        discrimination_db = discrimination_angular_real_db
        
        # C/I ratio (dB) = Potencias recibidas + discriminación + polarización
        ci_db = C_received_dbw - I_received_dbw + discrimination_db + polarization_isolation_db
        
        return {
            "ci_db": ci_db,
            "carrier_power_dbw": C_received_dbw,
            "interference_power_dbw": I_received_dbw,
            "satellite_fspl_db": satellite_fspl_db,
            "jammer_fspl_db": jammer_fspl_db,
            "discrimination_db": discrimination_db,
            "polarization_isolation_db": polarization_isolation_db,
            "jammer_eirp_dbw": jammer_config.eirp_dbw,
            "satellite_distance_km": satellite_distance_km,
            "jammer_distance_km": jammer_distance_km
        }
    
    @staticmethod
    def calculate_ci_ratio_uplink(jammer_config: 'JammerConfig',
                                 wanted_terminal_eirp_dbw: float,
                                 terminal_distance_km: float,
                                 jammer_distance_km: float,
                                 frequency_hz: float,
                                 discrimination_angular_real_db: float,
                                 polarization_isolation_db: float = -4.0) -> Dict[str, float]:
        """
        Calcula C/I ratio para uplink (Modo B2: Terminal → Satélite)
        Interferencia: Jammer terrestre → Satélite
        
        CORREGIDO: Usa discriminación angular real en lugar de FCC fija
        """
        # Pérdidas de propagación - Free Space Path Loss
        def calculate_fspl_db(distance_km, freq_hz):
            # Usar fórmula estándar consistente con JammerSimulator.py
            distance_m = distance_km * 1000
            if distance_m <= 0 or freq_hz <= 0:
                return float('inf')
            return 20 * math.log10(4 * math.pi * distance_m * freq_hz / SPEED_OF_LIGHT)
        
        # Potencia recibida de la señal útil (C) - Terminal → Satélite
        terminal_fspl_db = calculate_fspl_db(terminal_distance_km, frequency_hz)
        C_received_dbw = wanted_terminal_eirp_dbw - terminal_fspl_db
        
        # Potencia recibida de interferencia (I) - Jammer → Satélite
        jammer_fspl_db = calculate_fspl_db(jammer_distance_km, frequency_hz)
        I_received_dbw = jammer_config.eirp_dbw - jammer_fspl_db
        
        # CORRECCIÓN: Usar discriminación angular real calculada dinámicamente
        discrimination_db = discrimination_angular_real_db
        
        # C/I ratio (dB) = Potencias recibidas + discriminación + polarización
        ci_db = C_received_dbw - I_received_dbw + discrimination_db + polarization_isolation_db
        
        return {
            "ci_db": ci_db,
            "carrier_power_dbw": C_received_dbw,
            "interference_power_dbw": I_received_dbw,
            "terminal_fspl_db": terminal_fspl_db,
            "jammer_fspl_db": jammer_fspl_db,
            "discrimination_db": discrimination_db,
            "polarization_isolation_db": polarization_isolation_db,
            "jammer_eirp_dbw": jammer_config.eirp_dbw,
            "terminal_distance_km": terminal_distance_km,
            "jammer_distance_km": jammer_distance_km
        }
    
    @staticmethod
    def calculate_cinr_with_jamming(cn_db: float, ci_db: float) -> Dict[str, float]:
        """
        Combina C/N térmico con C/I de jamming para obtener CINR total
        CINR = -10*log10(10^(-C/N/10) + 10^(-C/I/10))
        """
        if math.isinf(ci_db):
            # Sin jamming
            return {
                "cinr_db": cn_db,
                "degradation_db": 0.0,
                "jamming_effective": False
            }
        
        # Conversión a lineal
        nc_linear = 10**(-cn_db/10)
        ic_linear = 10**(-ci_db/10)
        total_interference = nc_linear + ic_linear
        
        # CINR combinado
        cinr_db = -10 * math.log10(total_interference) if total_interference > 0 else float('inf')
        degradation_db = cn_db - cinr_db
        
        # Jamming efectivo si degrada más de 1 dB
        jamming_effective = degradation_db > 1.0
        
        return {
            "cinr_db": cinr_db,
            "degradation_db": degradation_db,
            "jamming_effective": jamming_effective,
            "ci_db": ci_db,
            "cn_db": cn_db
        }
    
    @staticmethod
    def assess_jamming_effectiveness(cinr_db: float, ci_db: float) -> str:
        """
        Evalúa la efectividad del jamming con modelo físico gradual.
        Evita transiciones binarias irreales (3.01 dB vs 27.68 dB).
        """
        if math.isinf(ci_db):
            return "SIN_JAMMING"
        
        # === MODELO GRADUAL BASADO EN FÍSICA ===
        # Usar relación J/S (Jamming to Signal ratio) para determinar efectividad
        j_over_s_db = -ci_db  # C/I negativo = J/S positivo
        
        if j_over_s_db >= 20.0:
            return "CRITICO"      # Jammer domina completamente (>100:1)
        elif j_over_s_db >= 10.0:
            return "EFECTIVO"     # Jammer significativo (>10:1)
        elif j_over_s_db >= 3.0:
            return "MODERADO"     # Interferencia notable (>2:1)
        elif j_over_s_db >= 0.0:
            return "LEVE"         # Interferencia detectable pero manejable
        else:
            return "INEFECTIVO"   # Signal domina sobre jammer
    
    @staticmethod  
    def calculate_realistic_degradation(satellite_power_dbw: float, jammer_power_dbw: float,
                                      sat_distance_km: float, jam_distance_km: float,
                                      frequency_hz: float, angular_separation_deg: float) -> float:
        """
        Calcula degradación de jamming con modelo físico gradual.
        Reemplaza lógica binaria problemática por transiciones suaves.
        """
        # Path loss para ambos enlaces
        def fspl_db(dist_km, freq_hz):
            freq_mhz = freq_hz / 1e6
            return 20*math.log10(dist_km) + 20*math.log10(freq_mhz) + 32.45
        
        sat_fspl = fspl_db(sat_distance_km, frequency_hz)
        jam_fspl = fspl_db(jam_distance_km, frequency_hz)
        
        # Potencias recibidas
        signal_received = satellite_power_dbw - sat_fspl
        jammer_received = jammer_power_dbw - jam_fspl
        
        # Discriminación angular (FCC ITU-R S.465)
        if angular_separation_deg <= 2.0:
            discrimination_db = 29 - 25*math.log10(angular_separation_deg) if angular_separation_deg > 0.1 else 29
        else:
            discrimination_db = 32 - 25*math.log10(angular_separation_deg)
        
        # Aplicar discriminación y polarización cruzada
        jammer_effective = jammer_received - discrimination_db - 4.0  # -4 dB polarización
        
        # Relación J/S efectiva
        j_over_s_db = jammer_effective - signal_received
        
        # === MODELO DE DEGRADACIÓN GRADUAL ===
        if j_over_s_db >= 20.0:
            # Saturación: degradación máxima física
            return min(30.0, 15.0 + j_over_s_db * 0.5)
        elif j_over_s_db >= 10.0:
            # Degradación significativa proporcional
            return 8.0 + (j_over_s_db - 10.0) * 0.8
        elif j_over_s_db >= 3.0:
            # Degradación moderada
            return 3.0 + (j_over_s_db - 3.0) * 0.7
        elif j_over_s_db >= 0.0:
            # Degradación leve proporcional
            return 0.5 + j_over_s_db * 0.8
        else:
            # Jamming negligible
            return max(0.1, 0.5 + j_over_s_db * 0.2)


class SpotJammerFrequencySelective:
    """
    Spot Jammer con selectividad de frecuencia realista.
    Concentra energía en banda estrecha específica para maximizar interferencia.
    """
    
    def __init__(self, center_freq_ghz: float, bandwidth_mhz: float, eirp_dbw: float):
        self.center_freq_ghz = center_freq_ghz
        self.bandwidth_mhz = bandwidth_mhz
        self.eirp_dbw = eirp_dbw
        self.target_link = None
        
    def _calculate_spectral_overlap(self, jammer_freq: float, jammer_bw: float, 
                                   target_freq: float, target_bw: float) -> float:
        """
        Calcula el solapamiento espectral entre jammer y enlace objetivo.
        Retorna factor 0.0-1.0 indicando porcentaje de solapamiento.
        """
        # Convertir todo a MHz para cálculos
        jammer_freq_mhz = jammer_freq * 1000
        target_freq_mhz = target_freq * 1000
        
        # Límites de las bandas
        jammer_min = jammer_freq_mhz - jammer_bw / 2
        jammer_max = jammer_freq_mhz + jammer_bw / 2
        target_min = target_freq_mhz - target_bw / 2
        target_max = target_freq_mhz + target_bw / 2
        
        # Calcular solapamiento
        overlap_min = max(jammer_min, target_min)
        overlap_max = min(jammer_max, target_max)
        
        if overlap_max <= overlap_min:
            return 0.0  # Sin solapamiento
            
        overlap_bandwidth = overlap_max - overlap_min
        target_bandwidth = target_max - target_min
        
        # Factor de solapamiento (0.0 = sin overlap, 1.0 = overlap completo)
        overlap_factor = min(1.0, overlap_bandwidth / target_bandwidth)
        
        return overlap_factor
    
    def calculate_jamming_effectiveness(self, ul_freq_ghz: float, dl_freq_ghz: float,
                                      ul_bandwidth_mhz: float, dl_bandwidth_mhz: float) -> dict:
        """
        Calcula efectividad de jamming basada en solapamiento espectral real.
        
        Returns:
            dict: {
                "target_link": "UL"|"DL"|"NONE",
                "spectral_overlap": float 0.0-1.0,
                "jamming_degradation_db": float,
                "frequency_offset_mhz": float,
                "effectiveness_level": str
            }
        """
        # Calcular solapamiento con cada enlace
        ul_overlap = self._calculate_spectral_overlap(
            self.center_freq_ghz, self.bandwidth_mhz, ul_freq_ghz, ul_bandwidth_mhz
        )
        dl_overlap = self._calculate_spectral_overlap(
            self.center_freq_ghz, self.bandwidth_mhz, dl_freq_ghz, dl_bandwidth_mhz
        )
        
        # Determinar enlace objetivo con tie-breaker para UL
        if ul_overlap > dl_overlap and ul_overlap > 0.01:  # Umbral mínimo 1%
            self.target_link = "UL"
            effectiveness = ul_overlap
            target_freq_ghz = ul_freq_ghz
            base_degradation = 5.56  # dB máximo según datos actuales
        elif ul_overlap == dl_overlap and ul_overlap > 0.01:  # TIE-BREAKER: Preferir UL
            # Si overlap es igual, preferir UL basado en distancia de frecuencia
            ul_freq_distance = abs(self.center_freq_ghz - ul_freq_ghz)
            dl_freq_distance = abs(self.center_freq_ghz - dl_freq_ghz)
            
            if ul_freq_distance <= dl_freq_distance:
                self.target_link = "UL"
                effectiveness = ul_overlap
                target_freq_ghz = ul_freq_ghz
            else:
                self.target_link = "DL"
                effectiveness = dl_overlap
                target_freq_ghz = dl_freq_ghz
            base_degradation = 5.56
        elif dl_overlap > 0.01:  # Umbral mínimo 1%
            self.target_link = "DL"
            effectiveness = dl_overlap
            target_freq_ghz = dl_freq_ghz
            base_degradation = 5.56  # dB máximo según datos actuales
        else:
            self.target_link = "NONE"
            effectiveness = max(ul_overlap, dl_overlap, 0.02)  # Interferencia residual mínima
            target_freq_ghz = ul_freq_ghz  # Referencia arbitraria
            base_degradation = 0.11  # Mínimo según datos actuales
        
        # Calcular degradación escalada por solapamiento
        jamming_degradation = base_degradation * effectiveness
        
        # Offset de frecuencia para análisis
        frequency_offset_mhz = abs(self.center_freq_ghz * 1000 - target_freq_ghz * 1000)
        
        # Niveles de efectividad cualitativos
        if effectiveness >= 0.95:
            effectiveness_level = "MAXIMA"
        elif effectiveness >= 0.60:
            effectiveness_level = "ALTA"
        elif effectiveness >= 0.20:
            effectiveness_level = "PARCIAL"
        elif effectiveness >= 0.05:
            effectiveness_level = "MINIMA"
        else:
            effectiveness_level = "NEGLIGIBLE"
        
        return {
            "target_link": self.target_link,
            "spectral_overlap": effectiveness,
            "jamming_degradation_db": jamming_degradation,
            "frequency_offset_mhz": frequency_offset_mhz,
            "effectiveness_level": effectiveness_level,
            "jammer_center_freq_ghz": self.center_freq_ghz,
            "jammer_bandwidth_mhz": self.bandwidth_mhz
        }


class PhysicalValidation:
    """
    Sistema de validación de coherencia física sin bloquear simulación.
    Identifica resultados problemáticos para análisis posterior.
    """
    
    @staticmethod
    def validate_link_coherence(ul_cinr_db: float, dl_cinr_db: float, e2e_cinr_db: float) -> dict:
        """Valida coherencia entre enlaces UL/DL/E2E"""
        flags = []
        severity = "NORMAL"
        
        if not (math.isnan(ul_cinr_db) or math.isnan(dl_cinr_db) or math.isnan(e2e_cinr_db)):
            # E2E no puede ser mejor que el peor enlace individual
            worst_individual = min(ul_cinr_db, dl_cinr_db)
            if e2e_cinr_db > worst_individual + 0.5:  # Tolerancia de 0.5 dB
                flags.append("E2E_MEJOR_QUE_INDIVIDUAL")
                severity = "CRITICO"
            
            # E2E debería estar cerca del peor enlace
            expected_e2e = worst_individual - 1.0  # Pérdida típica combinación
            if abs(e2e_cinr_db - expected_e2e) > 3.0:
                flags.append("E2E_DESVIACION_EXCESIVA")
                severity = max(severity, "ADVERTENCIA", key=["NORMAL", "ADVERTENCIA", "CRITICO"].index)
        
        return {
            "coherencia_enlaces": "PASS" if not flags else "FAIL",
            "flags_coherencia": flags,
            "severidad": severity
        }
    
    @staticmethod
    def validate_margin_feasibility(cinr_db: float, ebn0_margin_db: float, ebn0_req_db: float) -> dict:
        """Valida que los márgenes Eb/N0 sean físicamente posibles"""
        flags = []
        severity = "NORMAL"
        
        if not (math.isnan(cinr_db) or math.isnan(ebn0_margin_db) or math.isnan(ebn0_req_db)):
            # Margen no puede ser mucho mayor que CINR disponible
            if ebn0_margin_db > cinr_db + 5.0:
                flags.append("MARGEN_IMPOSIBLE")
                severity = "CRITICO"
            
            # CINR muy negativo indica enlace destruido
            if cinr_db < -10.0:
                flags.append("ENLACE_DESTRUIDO")
                severity = "CRITICO"
            elif cinr_db < 0.0:
                flags.append("CINR_NEGATIVO")
                severity = "ADVERTENCIA"
            
            # Margen extremadamente negativo
            if ebn0_margin_db < -20.0:
                flags.append("MARGEN_EXTREMO")
                severity = max(severity, "ADVERTENCIA", key=["NORMAL", "ADVERTENCIA", "CRITICO"].index)
        
        return {
            "viabilidad_margen": "PASS" if not flags else "FAIL", 
            "flags_margen": flags,
            "severidad": severity
        }
    
    @staticmethod
    def validate_jamming_realism(ci_db: float, degradation_db: float, jammer_distance_km: float, 
                                satellite_distance_km: float) -> dict:
        """Valida realismo de efectos de jamming"""
        flags = []
        severity = "NORMAL"
        
        if not (math.isnan(ci_db) or math.isnan(degradation_db)):
            # Degradación excesiva sin justificación física
            if degradation_db > 25.0:
                flags.append("DEGRADACION_EXCESIVA")
                severity = "ADVERTENCIA"
            
            # C/I extremadamente bajo (J/S > 1000:1)
            if ci_db < -30.0:
                flags.append("CI_EXTREMO")
                severity = "CRITICO"
            
            # Verificar coherencia distancia vs degradación
            if jammer_distance_km and satellite_distance_km:
                distance_advantage = 20 * math.log10(satellite_distance_km / jammer_distance_km)
                if degradation_db > distance_advantage + 20.0:  # +20 dB margen por EIRP
                    flags.append("DEGRADACION_INCOHERENTE_DISTANCIA")
                    severity = max(severity, "ADVERTENCIA", key=["NORMAL", "ADVERTENCIA", "CRITICO"].index)
                
                # VALIDACIÓN ESPECÍFICA PARA JAMMER SUPER-GEO
                if jammer_distance_km >= 45000.0:  # Super-GEO range
                    # Para jammer a 50,000 km vs satélite LEO a 550 km:
                    # Ventaja de distancia: 20*log10(50000/550) = ~39 dB
                    # Esto significa que el jammer está ~39 dB más lejos que el satélite
                    distance_disadvantage = 20 * math.log10(jammer_distance_km / satellite_distance_km)
                    
                    # Para superar esta desventaja de distancia, el jammer necesitaría
                    # al menos 39 dB más EIRP que el satélite para ser efectivo
                    if degradation_db > 10.0 and distance_disadvantage > 30.0:
                        flags.append("SUPER_GEO_IRREALISTA")
                        severity = "CRITICO"
                    elif degradation_db > 5.0 and distance_disadvantage > 35.0:
                        flags.append("SUPER_GEO_ALTAMENTE_IMPROBABLE")
                        severity = "ADVERTENCIA"
                    
                    # Verificar si la efectividad es físicamente plausible
                    # Un jammer Super-GEO necesitaría EIRP extremo para ser efectivo
                    required_advantage_db = distance_disadvantage + degradation_db
                    if required_advantage_db > 60.0:  # >60 dB de ventaja necesaria es muy improbable
                        flags.append("SUPER_GEO_EIRP_IMPOSIBLE")
                        severity = "CRITICO"
                
                # Verificación general para jammers muy distantes
                if jammer_distance_km > satellite_distance_km * 10:  # Jammer >10x más lejos que satélite
                    extreme_distance_factor = jammer_distance_km / satellite_distance_km
                    if degradation_db > 15.0:
                        flags.append(f"JAMMER_EXTREMADAMENTE_DISTANTE_{extreme_distance_factor:.0f}X")
                        severity = "ADVERTENCIA"
        
        return {
            "realismo_jamming": "PASS" if not flags else "FAIL",
            "flags_jamming": flags, 
            "severidad": severity
        }
    
    @staticmethod
    def analyze_super_geo_jammer_coherence(jammer_altitude_km: float, satellite_altitude_km: float,
                                          jammer_eirp_dbw: float, satellite_eirp_dbw: float,
                                          degradation_db: float, ci_db: float) -> dict:
        """
        Análisis específico de coherencia física para jammer Super-GEO
        
        Args:
            jammer_altitude_km: Altura del jammer (ej: 50,000 km)
            satellite_altitude_km: Altura del satélite (ej: 550 km para LEO)
            jammer_eirp_dbw: EIRP del jammer en dBW
            satellite_eirp_dbw: EIRP del satélite en dBW
            degradation_db: Degradación observada en dB
            ci_db: Relación C/I observada en dB
        
        Returns:
            dict: Análisis detallado de coherencia física
        """
        
        # Calcular ventaja/desventaja de distancia
        distance_factor = jammer_altitude_km / satellite_altitude_km
        distance_disadvantage_db = 20 * math.log10(distance_factor)
        
        # Calcular ventaja de potencia del jammer
        eirp_advantage_db = jammer_eirp_dbw - satellite_eirp_dbw
        
        # Balance neto de potencia vs distancia
        net_advantage_db = eirp_advantage_db - distance_disadvantage_db
        
        # Análisis de coherencia
        coherence_flags = []
        coherence_level = "COHERENTE"
        
        # Verificar si la degradación es consistente con el balance de potencia
        expected_max_degradation = max(0, net_advantage_db)
        
        if degradation_db > expected_max_degradation + 15.0:  # Margen de 15 dB por incertidumbres
            coherence_flags.append("DEGRADACION_EXCEDE_BALANCE_FISICO")
            coherence_level = "INCOHERENTE"
        elif degradation_db > expected_max_degradation + 10.0:
            coherence_flags.append("DEGRADACION_ALTAMENTE_OPTIMISTA")
            coherence_level = "DUDOSO"
        
        # Verificar requerimientos extremos de EIRP para Super-GEO
        if jammer_altitude_km >= 45000.0:
            required_eirp_for_effectiveness = satellite_eirp_dbw + distance_disadvantage_db + degradation_db
            
            if required_eirp_for_effectiveness > 85.0:  # >85 dBW es extremadamente alto
                coherence_flags.append("EIRP_REQUERIDO_EXTREMO")
                coherence_level = "INCOHERENTE"
            elif required_eirp_for_effectiveness > 75.0:  # >75 dBW es muy alto
                coherence_flags.append("EIRP_REQUERIDO_MUY_ALTO")
                coherence_level = "DUDOSO" if coherence_level != "INCOHERENTE" else coherence_level
        
        # Análisis de C/I
        if not math.isinf(ci_db):
            # J/S = -C/I
            js_ratio_db = -ci_db
            
            # Para jammer Super-GEO, J/S > 20 dB es muy difícil de lograr
            if js_ratio_db > 25.0 and jammer_altitude_km >= 45000.0:
                coherence_flags.append("JS_RATIO_IRREALISTA_SUPER_GEO")
                coherence_level = "INCOHERENTE"
            elif js_ratio_db > 20.0 and jammer_altitude_km >= 45000.0:
                coherence_flags.append("JS_RATIO_OPTIMISTA_SUPER_GEO")
                coherence_level = "DUDOSO" if coherence_level != "INCOHERENTE" else coherence_level
        
        # Generar recomendaciones
        recommendations = []
        
        if "EIRP_REQUERIDO_EXTREMO" in coherence_flags:
            recommendations.append(f"Reducir altura jammer o degradación esperada. EIRP requerido: {required_eirp_for_effectiveness:.1f} dBW")
        
        if distance_factor > 50:  # Jammer >50x más lejos que satélite
            recommendations.append(f"Considerar jammer más cercano. Factor distancia: {distance_factor:.0f}x")
        
        if degradation_db > 10.0 and jammer_altitude_km >= 45000.0:
            recommendations.append("Para jammer Super-GEO, degradación >10 dB requiere potencias irrealistas")
        
        # Calcular métricas físicas clave
        physics_metrics = {
            "distance_factor": round(distance_factor, 1),
            "distance_disadvantage_db": round(distance_disadvantage_db, 1),
            "eirp_advantage_db": round(eirp_advantage_db, 1),
            "net_advantage_db": round(net_advantage_db, 1),
            "expected_max_degradation_db": round(expected_max_degradation, 1),
            "required_eirp_dbw": round(required_eirp_for_effectiveness, 1) if jammer_altitude_km >= 45000.0 else None,
            "js_ratio_db": round(-ci_db, 1) if not math.isinf(ci_db) else None
        }
        
        return {
            "coherence_level": coherence_level,
            "coherence_flags": coherence_flags,
            "recommendations": recommendations,
            "physics_metrics": physics_metrics,
            "summary": f"Jammer a {jammer_altitude_km:.0f}km vs satélite a {satellite_altitude_km:.0f}km: {coherence_level}"
        }

    @staticmethod
    def validate_overall_scenario(ul_cinr: float, dl_cinr: float, e2e_cinr: float,
                                 ebn0_margin: float, ebn0_req: float, ci_db: float, 
                                 degradation_db: float, jam_dist: float, sat_dist: float) -> dict:
        """Validación integral del escenario"""
        
        # Ejecutar todas las validaciones
        coherencia = PhysicalValidation.validate_link_coherence(ul_cinr, dl_cinr, e2e_cinr)
        margen = PhysicalValidation.validate_margin_feasibility(ul_cinr, ebn0_margin, ebn0_req)
        jamming = PhysicalValidation.validate_jamming_realism(ci_db, degradation_db, jam_dist, sat_dist)
        
        # Combinar resultados
        all_flags = coherencia["flags_coherencia"] + margen["flags_margen"] + jamming["flags_jamming"]
        severities = [coherencia["severidad"], margen["severidad"], jamming["severidad"]]
        overall_severity = max(severities, key=["NORMAL", "ADVERTENCIA", "CRITICO"].index)
        
        # Generar resumen
        if overall_severity == "CRITICO":
            realismo_general = "INVIABLE"
        elif overall_severity == "ADVERTENCIA":
            realismo_general = "DUDOSO"
        else:
            realismo_general = "PLAUSIBLE"
        
        return {
            "realismo_general": realismo_general,
            "coherencia_fisica": "PASS" if not all_flags else "FAIL",
            "flags_totales": all_flags,
            "severidad_maxima": overall_severity,
            "numero_problemas": len(all_flags)
        }

class JammerType(Enum):
    """Tipos de jammers según escenario 2"""
    BARRAGE = "Barrage Jamming"
    SPOT = "Spot Jamming" 
    SMART = "Smart/Adaptive Jamming"

class AntennaType(Enum):
    """Tipos de antenas para jammers"""
    OMNIDIRECTIONAL = "Omnidireccional"
    DIRECTIONAL = "Direccional"

@dataclass
class JammerConfig:
    """Configuración de un jammer individual"""
    id: str
    name: str
    jammer_type: JammerType
    antenna_type: AntennaType
    
    # Parámetros técnicos
    power_tx_dbw: float = 27.0  # dBW (realista: 500W)
    antenna_gain_dbi: float = 3.0  # dBi  
    frequency_ghz: float = 12.0  # GHz
    bandwidth_mhz: float = 20.0  # MHz
    
    # Nuevos parámetros para Spot Jamming Selectivo
    center_freq_ghz: float = 20.0  # Frecuencia central del spot jammer
    target_link_preference: str = "AUTO"  # "UL", "DL", "AUTO"
    
    # Posición geográfica mejorada (separación superficie vs altura)
    distance_from_gs_km: float = 50.0  # Distancia angular en perímetro terrestre (km)
    azimuth_deg: float = 0.0  # Ángulo inicial desde GS
    altitude_type: AltitudeType = AltitudeType.SURFACE  # Altura preestablecida
    custom_altitude_km: float = 0.05  # Altura personalizada para Surface (50 metros por defecto)
    
    @property
    def altitude_km(self) -> float:
        """Altura sobre superficie terrestre según tipo seleccionado"""
        if self.altitude_type == AltitudeType.SURFACE:
            # Para Surface, usar altura personalizada (0-1.5 km)
            return self.custom_altitude_km
        else:
            # Solo superficie disponible ahora
            return self.custom_altitude_km
    
    @property 
    def orbital_period_min(self) -> float:
        """Período orbital en minutos según altura"""
        return ORBITAL_CONFIGURATIONS[self.altitude_type]['orbital_period_min']
    
    @property
    def angular_velocity_deg_per_min(self) -> float:
        """Velocidad angular en grados por minuto según altura"""
        return ORBITAL_CONFIGURATIONS[self.altitude_type]['angular_velocity_deg_per_min']
    
    def get_current_azimuth_deg(self, simulation_time_min: float) -> float:
        """Calcular azimuth actual considerando movimiento orbital"""
        # SIMPLIFICADO: Solo superficie - jammer anclado a Tierra
        # Azimut relativo al GS constante (ambos rotan con la Tierra)
        return self.azimuth_deg
    
    def get_surface_distance_km(self) -> float:
        """Distancia proyectada en superficie terrestre"""
        # SIMPLIFICADO: Solo superficie - distancia directa
        return self.distance_from_gs_km
    
    @property
    def effective_distance_3d_km(self) -> float:
        """Distancia 3D real considerando altura y posición orbital"""
        surface_dist = self.get_surface_distance_km()
        return math.sqrt(surface_dist**2 + self.altitude_km**2)
    
    @property
    def elevation_angle_deg(self) -> float:
        """Ángulo de elevación desde GS hacia jammer"""
        surface_dist = self.get_surface_distance_km()
        if surface_dist == 0:
            return 90.0 if self.altitude_km > 0 else 0.0
        return math.degrees(math.atan(self.altitude_km / surface_dist))
    
    # Estado
    active: bool = True
    
    @property
    def eirp_dbw(self) -> float:
        """EIRP calculado"""
        return self.power_tx_dbw + self.antenna_gain_dbi
    
    def calculate_fcc_discrimination_db(self, angular_separation_deg: float) -> float:
        """Discriminación angular según función FCC ITU-R S.465 - CORREGIDA para ángulos pequeños"""
        theta = angular_separation_deg
        if theta < 0.1:
            # Muy cerca: discriminación mínima (jammer muy efectivo)
            return 0.0
        elif 0.1 <= theta < 1.0:
            # Interpolación lineal para ángulos pequeños: 0° = 0dB, 1° = 29dB
            return 29.0 * theta  # θ en grados: 0.1° → 2.9dB, 0.5° → 14.5dB
        elif 1.0 <= theta <= 7.0:
            return 29 - 25 * math.log10(theta)
        elif 7.0 < theta <= 9.2:
            return 8.0
        elif 9.2 < theta <= 48.0:
            return 32 - 25 * math.log10(theta)
        else:
            return -10.0
    
    def calculate_path_loss_to_satellite(self, distance_sat_km: float, frequency_ghz: float) -> float:
        """Calcula path loss desde jammer hasta satélite (Free Space Path Loss)"""
        distance_m = distance_sat_km * 1000
        frequency_hz = frequency_ghz * 1e9
        c = 299792458  # m/s
        fspl_db = 20 * math.log10(4 * math.pi * distance_m * frequency_hz / c)
        return fspl_db
    
    @property
    def type_description(self) -> str:
        """Descripción del tipo de jammer"""
        descriptions = {
            JammerType.BARRAGE: "Banda Ancha (100-1000 MHz)",
            JammerType.SPOT: "Banda Estrecha (1-10 MHz)", 
            JammerType.SMART: "Adaptativo con ML"
        }
        return descriptions.get(self.jammer_type, "Desconocido")
    
    def calculate_selective_spot_jamming(self, ul_freq_ghz: float, dl_freq_ghz: float,
                                       ul_bandwidth_mhz: float, dl_bandwidth_mhz: float) -> dict:
        """
        Calcula efectividad de Spot Jamming con selectividad de frecuencia.
        Utiliza la nueva clase SpotJammerFrequencySelective para realismo.
        """
        if self.jammer_type != JammerType.SPOT:
            # Para jammers no-spot, usar lógica genérica tradicional
            return {
                "target_link": "BOTH",
                "spectral_overlap": 0.8,  # Genérico
                "jamming_degradation_db": 3.38,  # Promedio actual
                "frequency_offset_mhz": 0.0,
                "effectiveness_level": "GENERICO"
            }
        
        # Crear instancia de Spot Jammer selectivo
        spot_jammer = SpotJammerFrequencySelective(
            center_freq_ghz=self.center_freq_ghz,
            bandwidth_mhz=self.bandwidth_mhz,
            eirp_dbw=self.eirp_dbw
        )
        
        # Calcular efectividad con selectividad real
        effectiveness = spot_jammer.calculate_jamming_effectiveness(
            ul_freq_ghz, dl_freq_ghz, ul_bandwidth_mhz, dl_bandwidth_mhz
        )
        
        return effectiveness


def select_adaptive_modcod_spot_jamming(cinr_db: float, jamming_active: bool = True) -> dict:
    """
    Selección automática de MODCOD considerando degradación por Spot Jamming.
    Optimiza eficiencia espectral 1.0-4.5x según condiciones reales.
    
    Args:
        cinr_db: CINR en dB después de aplicar jamming
        jamming_active: Si hay jamming activo (afecta margen)
        
    Returns:
        dict: {
            "modcod": str,
            "ebn0_req": float,
            "efficiency": float,
            "robust": bool,
            "throughput_factor": float
        }
    """
    # Factor de margen adicional bajo jamming activo (reducido para ser menos conservador)
    jamming_margin = 1.0 if jamming_active else 0.0
    effective_cinr = cinr_db - jamming_margin
    
    # Selección MODCOD basada en CINR efectivo
    if effective_cinr >= 18.0:
        # Máxima eficiencia - condiciones excelentes
        return {
            "modcod": "32APSK_9_10", 
            "ebn0_req": 1.0, 
            "efficiency": 4.5, 
            "robust": False,
            "throughput_factor": 4.5,
            "cinr_margin": effective_cinr - 18.0
        }
    elif effective_cinr >= 15.0:
        # Alta eficiencia - condiciones buenas
        return {
            "modcod": "16APSK_5_6", 
            "ebn0_req": 2.0, 
            "efficiency": 4.2, 
            "robust": False,
            "throughput_factor": 4.2,
            "cinr_margin": effective_cinr - 15.0
        }
    elif effective_cinr >= 12.0:
        # Eficiencia media - condiciones aceptables
        return {
            "modcod": "8PSK_3_4", 
            "ebn0_req": 4.0, 
            "efficiency": 2.25, 
            "robust": True,
            "throughput_factor": 2.25,
            "cinr_margin": effective_cinr - 12.0
        }
    elif effective_cinr >= 8.0:
        # Eficiencia básica - condiciones críticas
        return {
            "modcod": "QPSK_2_3", 
            "ebn0_req": 6.5, 
            "efficiency": 1.33, 
            "robust": True,
            "throughput_factor": 1.33,
            "cinr_margin": effective_cinr - 8.0
        }
    elif effective_cinr >= 4.0:
        # Mínima eficiencia - supervivencia
        return {
            "modcod": "QPSK_1_2", 
            "ebn0_req": 9.0, 
            "efficiency": 1.0, 
            "robust": True,
            "throughput_factor": 1.0,
            "cinr_margin": effective_cinr - 4.0
        }
    else:
        # Outage - enlace no viable
        return {
            "modcod": "OUTAGE", 
            "ebn0_req": float('inf'), 
            "efficiency": 0.0, 
            "robust": False,
            "throughput_factor": 0.0,
            "cinr_margin": effective_cinr - 4.0  # Negativo
        }


def calculate_dynamic_angular_discrimination(sat_elevation_deg: float, 
                                           jammer_distance_km: float, 
                                           sat_distance_km: float) -> dict:
    """
    Discriminación angular basada en geometría 3D real del Spot Jammer.
    Rango dinámico 10-29dB según separación angular calculada.
    
    Args:
        sat_elevation_deg: Elevación del satélite (0-90°)
        jammer_distance_km: Distancia horizontal al jammer
        sat_distance_km: Distancia slant al satélite
        
    Returns:
        dict: {
            "discrimination_db": float,
            "angular_separation_deg": float,
            "geometry_type": str
        }
    """
    import math
    
    # Aproximación de ángulo de separación angular basada en geometría
    # Asumiendo jammer terrestre y satélite en elevación
    angular_separation = math.atan(jammer_distance_km / sat_distance_km) * 180 / math.pi
    
    # Ajuste por elevación - mayor elevación = mayor separación aparente
    elevation_factor = 1.0 + (sat_elevation_deg / 90.0) * 0.5
    angular_separation *= elevation_factor
    
    # Discriminación FCC-25 dinámica para Spot Jamming
    if angular_separation >= 10.0:
        # Discriminación estándar FCC-25
        discrimination = 29.0 - 25 * math.log10(angular_separation)
        geometry_type = "SEPARACION_ALTA"
    elif angular_separation >= 2.0:
        # Discriminación intermedia
        discrimination = 21.47 - 3 * (10 - angular_separation)
        geometry_type = "SEPARACION_MEDIA"
    else:
        # Spot Jammer muy próximo - discriminación degradada
        discrimination = max(10.0, 21.47 - 15 * (2 - angular_separation))
        geometry_type = "SEPARACION_BAJA"
    
    # Limitar rango 10-29dB
    discrimination = min(29.0, max(10.0, discrimination))
    
    return {
        "discrimination_db": discrimination,
        "angular_separation_deg": angular_separation,
        "geometry_type": geometry_type,
        "elevation_factor": elevation_factor
    }


def calculate_realistic_rtt_spot_jamming(one_way_latency_ms: float, elevation_deg: float, 
                                       jamming_active: bool = True) -> dict:
    """
    RTT realista considerando overhead de procesamiento bajo jamming.
    Corrige problema: RTT actual = 1.33-1.53 × Latencia_Ida (debería ser ~2.0x)
    
    Args:
        one_way_latency_ms: Latencia de ida en ms
        elevation_deg: Elevación del satélite (0-90°)
        jamming_active: Si hay jamming activo
        
    Returns:
        dict: {
            "rtt_total_ms": float,
            "processing_overhead_ms": float,
            "jamming_overhead_ms": float,
            "rtt_accuracy": str
        }
    """
    # Overhead de procesamiento base
    base_overhead = 0.5  # ms - overhead normal de procesamiento
    
    if jamming_active:
        # Overhead adicional por jamming (detección y mitigación)
        # Mayor overhead a baja elevación (condiciones más difíciles)
        # Interpolación lineal: elev 0° → 2.0ms, elev 90° → 0.5ms
        elevation_norm = elevation_deg / 90.0  # Normalizar 0-1
        jamming_overhead = 2.0 - (elevation_norm * 1.5)  # 2.0 → 0.5
        
        # Overhead adicional por detección de jamming
        detection_overhead = 0.3  # ms - tiempo de detección
        
        total_jamming_overhead = jamming_overhead + detection_overhead
    else:
        total_jamming_overhead = 0.0
    
    # RTT total = 2 × ida + overhead base + overhead jamming
    total_overhead = base_overhead + total_jamming_overhead
    rtt_total = 2.0 * one_way_latency_ms + total_overhead
    
    # Clasificación de precisión basada en el RTT corregido
    theoretical_rtt = 2.0 * one_way_latency_ms
    rtt_ratio = rtt_total / one_way_latency_ms  # Ratio respecto a latencia de ida
    
    if 1.95 <= rtt_ratio <= 2.10:
        accuracy = "EXCELENTE"
    elif 1.85 <= rtt_ratio <= 2.20:
        accuracy = "BUENA"
    elif 1.70 <= rtt_ratio <= 2.40:
        accuracy = "ACEPTABLE"
    else:
        accuracy = "PROBLEMATICA"
    
    return {
        "rtt_total_ms": rtt_total,
        "processing_overhead_ms": base_overhead,
        "jamming_overhead_ms": total_jamming_overhead,
        "rtt_accuracy": accuracy,
        "rtt_ratio": rtt_ratio,
        "theoretical_rtt_ms": theoretical_rtt
    }


class JammerConfigDialog:
    """Ventana de configuración de jammer"""
    
    def __init__(self, parent, config: Optional[JammerConfig] = None):
        self.parent = parent
        self.config = config
        self.result = None
        
        self.window = tk.Toplevel(parent)
        self.window.title("Configuración de Jammer")
        self.window.geometry("500x600")
        self.window.transient(parent)
        self.window.grab_set()
        
        # Centrar ventana
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.window.winfo_screenheight() // 2) - (600 // 2)
        self.window.geometry(f"500x600+{x}+{y}")
        
        self._create_widgets()
        self._load_config()
    
    def _create_widgets(self):
        """Crear interfaz de configuración"""
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # === IDENTIFICACIÓN ===
        id_frame = ttk.LabelFrame(main_frame, text="Identificación", padding="5")
        id_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=5)
        
        ttk.Label(id_frame, text="Nombre:").grid(row=0, column=0, sticky="w")
        self.name_var = tk.StringVar(value="Jammer_1")
        ttk.Entry(id_frame, textvariable=self.name_var, width=30).grid(row=0, column=1, sticky="ew")
        
        # === TIPO DE JAMMER ===
        type_frame = ttk.LabelFrame(main_frame, text="Tipo de Jammer", padding="5")
        type_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)
        
        ttk.Label(type_frame, text="Técnica:").grid(row=0, column=0, sticky="w")
        self.jammer_type_var = tk.StringVar(value=JammerType.SPOT.value)
        jammer_combo = ttk.Combobox(type_frame, textvariable=self.jammer_type_var, 
                                   values=[t.value for t in JammerType], state="readonly", width=25)
        jammer_combo.grid(row=0, column=1, sticky="ew")
        jammer_combo.bind('<<ComboboxSelected>>', self._update_description)
        
        self.description_label = ttk.Label(type_frame, text="", foreground="blue")
        self.description_label.grid(row=1, column=0, columnspan=2, sticky="w")
        
        # === ANTENA ===
        antenna_frame = ttk.LabelFrame(main_frame, text="Configuración de Antena", padding="5")
        antenna_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)
        
        ttk.Label(antenna_frame, text="Tipo:").grid(row=0, column=0, sticky="w")
        self.antenna_type_var = tk.StringVar(value=AntennaType.OMNIDIRECTIONAL.value)
        antenna_combo = ttk.Combobox(antenna_frame, textvariable=self.antenna_type_var,
                                   values=[t.value for t in AntennaType], state="readonly", width=25)
        antenna_combo.grid(row=0, column=1, sticky="ew")
        
        ttk.Label(antenna_frame, text="Ganancia [dBi]:").grid(row=1, column=0, sticky="w")
        self.antenna_gain_var = tk.DoubleVar(value=3.0)
        ttk.Spinbox(antenna_frame, from_=0, to=30, increment=0.5, 
                   textvariable=self.antenna_gain_var, width=10).grid(row=1, column=1, sticky="w")
        
        # === POTENCIA ===
        power_frame = ttk.LabelFrame(main_frame, text="Configuración de Potencia", padding="5")
        power_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=5)
        
        ttk.Label(power_frame, text="Potencia TX [dBW]:").grid(row=0, column=0, sticky="w")
        self.power_tx_var = tk.DoubleVar(value=27.0)  # Valor realista: 500W
        ttk.Spinbox(power_frame, from_=10, to=50, increment=1, 
                   textvariable=self.power_tx_var, width=10).grid(row=0, column=1, sticky="w")
        
        # EIRP calculado (solo lectura)
        ttk.Label(power_frame, text="EIRP [dBW]:").grid(row=1, column=0, sticky="w")
        self.eirp_label = ttk.Label(power_frame, text="30.0", foreground="green")  # 27+3=30
        self.eirp_label.grid(row=1, column=1, sticky="w")
        
        # Bind para actualizar EIRP
        self.power_tx_var.trace('w', self._update_eirp)
        self.antenna_gain_var.trace('w', self._update_eirp)
        
        # === FRECUENCIA ===
        freq_frame = ttk.LabelFrame(main_frame, text="Configuración de Frecuencia", padding="5")
        freq_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=5)
        
        ttk.Label(freq_frame, text="Frecuencia [GHz]:").grid(row=0, column=0, sticky="w")
        self.frequency_var = tk.DoubleVar(value=12.0)
        ttk.Spinbox(freq_frame, from_=1, to=50, increment=0.1,
                   textvariable=self.frequency_var, width=10).grid(row=0, column=1, sticky="w")
        
        ttk.Label(freq_frame, text="Ancho de Banda [MHz]:").grid(row=1, column=0, sticky="w")
        self.bandwidth_var = tk.DoubleVar(value=20.0)
        ttk.Spinbox(freq_frame, from_=1, to=1000, increment=1,
                   textvariable=self.bandwidth_var, width=10).grid(row=1, column=1, sticky="w")
        
        # === POSICIÓN GEOGRÁFICA ===
        pos_frame = ttk.LabelFrame(main_frame, text="Posición Geográfica", padding="5")
        pos_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=5)
        
        ttk.Label(pos_frame, text="Distancia Superficie [km]:").grid(row=0, column=0, sticky="w")
        self.distance_var = tk.DoubleVar(value=50.0)  # Distancia horizontal
        ttk.Spinbox(pos_frame, from_=0.1, to=1000, increment=1,
                   textvariable=self.distance_var, width=10).grid(row=0, column=1, sticky="w")
        
        ttk.Label(pos_frame, text="Tipo de Altura:").grid(row=1, column=0, sticky="w")
        self.altitude_type_var = tk.StringVar(value=AltitudeType.SURFACE.value)
        altitude_combo = ttk.Combobox(pos_frame, textvariable=self.altitude_type_var, 
                                     values=[alt.value for alt in AltitudeType],
                                     state='readonly', width=15)
        altitude_combo.grid(row=1, column=1, sticky="w")
        
        ttk.Label(pos_frame, text="Azimut Inicial [°]:").grid(row=2, column=0, sticky="w")
        self.azimuth_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(pos_frame, from_=0, to=360, increment=15,
                   textvariable=self.azimuth_var, width=10).grid(row=2, column=1, sticky="w")
        
        # NUEVO: Altura personalizada para Surface
        ttk.Label(pos_frame, text="Altura Personalizada [km]:").grid(row=3, column=0, sticky="w")
        self.custom_altitude_var = tk.DoubleVar(value=0.05)  # 50 metros por defecto
        self.custom_altitude_spin = ttk.Spinbox(pos_frame, from_=0.001, to=1.5, increment=0.01,
                   textvariable=self.custom_altitude_var, width=10, format="%.3f")
        self.custom_altitude_spin.grid(row=3, column=1, sticky="w")
        ttk.Label(pos_frame, text="(Solo para Superficie)", font=('TkDefaultFont', 8), 
                 foreground="gray").grid(row=3, column=2, sticky="w", columnspan=2)
        
        # Métricas calculadas automáticamente
        ttk.Label(pos_frame, text="Distancia 3D [km]:").grid(row=0, column=4, sticky="w", padx=(10,0))
        self.distance_3d_label = ttk.Label(pos_frame, text="50.0", foreground="blue")
        self.distance_3d_label.grid(row=0, column=5, sticky="w")
        
        ttk.Label(pos_frame, text="Altura Efectiva [km]:").grid(row=1, column=4, sticky="w", padx=(10,0))
        self.altitude_real_label = ttk.Label(pos_frame, text="0.001", foreground="blue")
        self.altitude_real_label.grid(row=1, column=5, sticky="w")
        
        ttk.Label(pos_frame, text="Elevación [°]:").grid(row=2, column=4, sticky="w", padx=(10,0))
        self.elevation_label = ttk.Label(pos_frame, text="0.0", foreground="blue")
        self.elevation_label.grid(row=2, column=5, sticky="w")
        
        ttk.Label(pos_frame, text="Período Orbital [min]:").grid(row=3, column=4, sticky="w", padx=(10,0))
        self.period_label = ttk.Label(pos_frame, text="0.0", foreground="green")
        self.period_label.grid(row=3, column=5, sticky="w")
        
        # Bind para actualizar métricas automáticamente
        self.distance_var.trace('w', self._update_position_metrics)
        self.altitude_type_var.trace('w', self._update_position_metrics)
        self.custom_altitude_var.trace('w', self._update_position_metrics)
        altitude_combo.bind('<<ComboboxSelected>>', lambda e: self._update_position_metrics())
        
        # === BOTONES ===
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Guardar Jammer", 
                  command=self._save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancelar", 
                  command=self._cancel).pack(side=tk.LEFT, padx=5)
        
        # Actualizar descripciones iniciales
        self._update_description()
        self._update_eirp()
        self._update_position_metrics()
    
    def _load_config(self):
        """Cargar configuración existente si la hay"""
        if self.config:
            self.name_var.set(self.config.name)
            self.jammer_type_var.set(self.config.jammer_type.value)
            self.antenna_type_var.set(self.config.antenna_type.value)
            self.antenna_gain_var.set(self.config.antenna_gain_dbi)
            self.power_tx_var.set(self.config.power_tx_dbw)
            self.frequency_var.set(self.config.frequency_ghz)
            self.bandwidth_var.set(self.config.bandwidth_mhz)
            self.distance_var.set(self.config.distance_from_gs_km)
            # Cargar tipo de altura (compatibilidad con configs antiguas)
            if hasattr(self.config, 'altitude_type'):
                self.altitude_type_var.set(self.config.altitude_type.value)
            else:
                # Migrar de altitude_km a altitude_type - solo superficie disponible
                self.altitude_type_var.set(AltitudeType.SURFACE.value)
            self.azimuth_var.set(self.config.azimuth_deg)
    
    def _update_description(self, event=None):
        """Actualizar descripción del tipo de jammer"""
        jammer_type = JammerType(self.jammer_type_var.get())
        descriptions = {
            JammerType.BARRAGE: "Banda Ancha: Cubre 100-1000 MHz, EIRP 40-60 dBW",
            JammerType.SPOT: "Banda Estrecha: 1-10 MHz, EIRP 50-70 dBW",
            JammerType.SMART: "Adaptativo: Respuesta dinámica con ML/SDR"
        }
        self.description_label.config(text=descriptions.get(jammer_type, ""))
    
    def _update_eirp(self, *args):
        """Actualizar cálculo de EIRP"""
        try:
            eirp = self.power_tx_var.get() + self.antenna_gain_var.get()
            self.eirp_label.config(text=f"{eirp:.1f}")
        except:
            self.eirp_label.config(text="---")
    
    def _update_position_metrics(self, *args):
        """Actualizar métricas de posición 3D calculadas"""
        try:
            distance_surface = self.distance_var.get()
            
            # Obtener tipo de altura seleccionado
            altitude_type_str = self.altitude_type_var.get()
            altitude_type = next((alt for alt in AltitudeType if alt.value == altitude_type_str), AltitudeType.SURFACE)
            
            # Usar altura personalizada o predeterminada
            if altitude_type == AltitudeType.SURFACE:
                custom_altitude = self.custom_altitude_var.get()
                altitude_km = custom_altitude
                period_min = 0.0  # Sin período orbital para superficie
            else:
                config = ORBITAL_CONFIGURATIONS[altitude_type]
                altitude_km = config['altitude_km']
                period_min = config['orbital_period_min']
            
            # Crear configuración temporal para cálculos
            temp_config = JammerConfig(
                distance_from_gs_km=distance_surface,
                altitude_type=altitude_type,
                custom_altitude_km=altitude_km  # NUEVO: usar altura personalizada
            )
            
            # Calcular métricas
            distance_3d = temp_config.effective_distance_3d_km
            elevation = temp_config.elevation_angle_deg
            
            # Actualizar labels
            self.distance_3d_label.config(text=f"{distance_3d:.2f}")
            self.altitude_real_label.config(text=f"{altitude_km:.3f}")
            self.elevation_label.config(text=f"{elevation:.1f}")
            self.period_label.config(text=f"{period_min:.1f}")
            
        except Exception as e:
            # En caso de error, mostrar valores por defecto
            self.distance_3d_label.config(text="---")
            self.altitude_real_label.config(text="---")
            self.elevation_label.config(text="---")
            self.period_label.config(text="---")
    
    def _save_config(self):
        """Guardar configuración"""
        try:
            # Validar nombre único
            name = self.name_var.get().strip()
            if not name:
                messagebox.showerror("Error", "El nombre no puede estar vacío")
                return
            
            # Obtener tipo de altura seleccionado
            altitude_type_str = self.altitude_type_var.get()
            altitude_type = next((alt for alt in AltitudeType if alt.value == altitude_type_str), AltitudeType.SURFACE)
            
            # Crear configuración
            config = JammerConfig(
                id=f"jammer_{hash(name) % 10000}",
                name=name,
                jammer_type=JammerType(self.jammer_type_var.get()),
                antenna_type=AntennaType(self.antenna_type_var.get()),
                power_tx_dbw=self.power_tx_var.get(),
                antenna_gain_dbi=self.antenna_gain_var.get(),
                frequency_ghz=self.frequency_var.get(),
                bandwidth_mhz=self.bandwidth_var.get(),
                distance_from_gs_km=self.distance_var.get(),
                altitude_type=altitude_type,  # Nuevo: tipo de altura preestablecida
                custom_altitude_km=self.custom_altitude_var.get(),  # NUEVO: Altura personalizada
                azimuth_deg=self.azimuth_var.get()
            )
            
            self.result = config
            self.window.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar configuración: {str(e)}")
    
    def _cancel(self):
        """Cancelar configuración"""
        self.window.destroy()

class JammerWidget:
    """Widget compacto para mostrar un jammer configurado"""
    
    def __init__(self, parent_frame, config: JammerConfig, edit_callback, delete_callback):
        self.config = config
        self.edit_callback = edit_callback
        self.delete_callback = delete_callback
        
        # Frame principal más compacto
        self.frame = ttk.Frame(parent_frame, relief="solid", borderwidth=1)
        self.frame.pack(fill="x", padx=1, pady=1)
        
        # Frame interno para layout horizontal
        inner_frame = ttk.Frame(self.frame)
        inner_frame.pack(fill="x", padx=2, pady=1)
        
        # Nombre del jammer (izquierda)
        name_label = ttk.Label(inner_frame, text=config.name, font=("Segoe UI", 8, "bold"))
        name_label.pack(side="left")
        
        # Botón eliminar (derecha)
        delete_btn = ttk.Button(inner_frame, text="×", width=2,
                               command=lambda: self.delete_callback(config.id))
        delete_btn.pack(side="right")
        
        # Info técnica compacta (centro) - incluir información orbital
        altitude_type = getattr(config, 'altitude_type', AltitudeType.SURFACE)
        altitude_km = config.altitude_km
        distance_3d = config.effective_distance_3d_km
        period_min = config.orbital_period_min
        
        if period_min > 0:
            orbital_info = f"T:{period_min:.0f}min"
        else:
            orbital_info = f"h:{altitude_km:.1f}km"
            
        info_text = f"{config.jammer_type.value[:4]} | {config.eirp_dbw:.0f}dBW | {distance_3d:.1f}km | {altitude_type.value[:3]} | {orbital_info}"
        info_label = ttk.Label(inner_frame, text=info_text, font=("Segoe UI", 7), foreground="blue")
        info_label.pack(side="left", padx=(5, 0))
        
        # Hacer todo el frame clickeable para editar
        widgets_to_bind = [self.frame, inner_frame, name_label, info_label]
        for widget in widgets_to_bind:
            widget.bind("<Button-1>", lambda e: self.edit_callback(config))

class JammerManager:
    """Gestor principal del sistema de jammers"""
    
    def __init__(self, parent_frame):
        self.parent_frame = parent_frame
        self.jammers: Dict[str, JammerConfig] = {}
        
        self._create_panel()
    
    def _create_panel(self):
        """Crear panel de jammers compacto y adaptativo"""
        # Frame principal con título compacto
        self.jammers_frame = ttk.LabelFrame(self.parent_frame, text="Jammers", padding="2")
        
        # Botón añadir jammer siempre visible (más compacto)
        self.add_button = ttk.Button(self.jammers_frame, text="+ Jammer", 
                                    command=self._add_jammer)
        self.add_button.pack(pady=1)
        
        # === PANEL DE ESTADO DE JAMMING MEJORADO ===
        status_frame = ttk.Frame(self.jammers_frame)
        status_frame.pack(fill='x', pady=1)
        
        # Label de estado principal con indicadores visuales
        self.jamming_status_label = ttk.Label(status_frame, 
                                            text="🔘 Jamming: DESACTIVADO", 
                                            foreground='#888888',
                                            font=('TkDefaultFont', 9, 'bold'))
        self.jamming_status_label.pack(anchor='w')
        
        # Label de diagnóstico con explicación inteligente
        self.jamming_diagnostic_label = ttk.Label(status_frame, 
                                                text="📊 Sin jammers activos en el escenario",
                                                foreground='#888888',
                                                font=('TkDefaultFont', 8))
        self.jamming_diagnostic_label.pack(anchor='w')
        
        # === MÉTRICAS EN TIEMPO REAL ===
        metrics_frame = ttk.LabelFrame(self.jammers_frame, text="📊 Métricas", padding=3)
        metrics_frame.pack(fill='x', pady=1)
        
        # Efectividad global
        self.effectiveness_label = ttk.Label(metrics_frame, 
                                           text="⚡ Global: —", 
                                           foreground='#666666',
                                           font=('TkDefaultFont', 7, 'bold'))
        self.effectiveness_label.pack(anchor='w', pady=0)
        
        # Container con pestañas para métricas individuales de jammers
        self.individual_metrics_frame = ttk.Frame(metrics_frame)
        self.individual_metrics_frame.pack(fill='both', expand=True, pady=1)
        
        # Notebook para pestañas de jammers (similar a UL/DL/End-to-End)
        self.jammer_notebook = ttk.Notebook(self.individual_metrics_frame)
        self.jammer_notebook.pack(fill='both', expand=True, padx=1, pady=1)
        
        # Frame para mostrar métricas del jammer seleccionado
        self.selected_jammer_metrics_frame = ttk.Frame(self.individual_metrics_frame)
        self.selected_jammer_metrics_frame.pack(fill='x', pady=2)
        
        # Variables para trackear jammers y pestañas
        self.jammer_tabs = {}  # {jammer_name: tab_frame}
        self.current_jammer_tab = None
        
        # Widgets persistentes para métricas del jammer seleccionado
        self.persistent_metrics_widgets = None
        self._create_persistent_metrics_widgets()
        
        # Bind para cambio de pestaña de jammer
        self.jammer_notebook.bind('<<NotebookTabChanged>>', self._on_jammer_tab_changed)
        
        # Target link detectado  
        self.target_link_label = ttk.Label(metrics_frame,
                                         text="🎯 Target Primario: —",
                                         foreground='#666666', 
                                         font=('TkDefaultFont', 8))
        self.target_link_label.pack(anchor='w')
        
        # Solapamiento espectral total
        self.spectral_overlap_label = ttk.Label(metrics_frame,
                                              text="📡 Solapamiento Total: —",
                                              foreground='#666666',
                                              font=('TkDefaultFont', 8))
        self.spectral_overlap_label.pack(anchor='w')
        
        # Compensación Doppler
        self.doppler_compensation_label = ttk.Label(metrics_frame,
                                                  text="🌊 Doppler: —",
                                                  foreground='#666666',
                                                  font=('TkDefaultFont', 8))
        self.doppler_compensation_label.pack(anchor='w')
        
        # Diccionario para trackear labels de jammers individuales
        self.individual_jammer_labels = {}
        
        # Container para jammers con altura dinámica
        self.jammers_container = ttk.Frame(self.jammers_frame)
        self.jammers_container.pack(fill='x')
    
    def get_panel(self) -> ttk.Widget:
        """Obtener el panel principal"""
        return self.jammers_frame
    
    def _create_persistent_metrics_widgets(self):
        """Crear widgets persistentes para métricas de jammer (sin destroy/recreate)"""
        # Crear grid de métricas persistente
        self.metrics_grid = ttk.Frame(self.selected_jammer_metrics_frame)
        self.metrics_grid.pack(fill='x', padx=5, pady=5)
        
        # Título persistente (más compacto)
        self.title_label = ttk.Label(self.metrics_grid, 
                                   text="📊 Sin jammer seleccionado", 
                                   font=('TkDefaultFont', 8, 'bold'))
        self.title_label.grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 3))
        
        # FILA 1: DEGRADACIÓN Y EIRP (layout más compacto)
        ttk.Label(self.metrics_grid, text="💥 Degradación:", font=('TkDefaultFont', 7, 'bold')).grid(row=1, column=0, sticky='w', padx=(0, 2))
        self.degradation_value = ttk.Label(self.metrics_grid, text="—", font=('TkDefaultFont', 7))
        self.degradation_value.grid(row=1, column=1, sticky='w', padx=(0, 8))
        
        ttk.Label(self.metrics_grid, text="⚡ EIRP:", font=('TkDefaultFont', 7, 'bold')).grid(row=1, column=2, sticky='w', padx=(0, 2))
        self.eirp_value = ttk.Label(self.metrics_grid, text="—", foreground='#0066CC', font=('TkDefaultFont', 7))
        self.eirp_value.grid(row=1, column=3, sticky='w')
        
        # FILA 2: C/I Y DISTANCIA
        ttk.Label(self.metrics_grid, text="📊 C/I:", font=('TkDefaultFont', 7, 'bold')).grid(row=2, column=0, sticky='w', padx=(0, 2))
        self.ci_value = ttk.Label(self.metrics_grid, text="—", font=('TkDefaultFont', 7))
        self.ci_value.grid(row=2, column=1, sticky='w', padx=(0, 8))
        
        ttk.Label(self.metrics_grid, text="📍 Dist:", font=('TkDefaultFont', 7, 'bold')).grid(row=2, column=2, sticky='w', padx=(0, 2))
        self.distance_value = ttk.Label(self.metrics_grid, text="—", foreground='#666666', font=('TkDefaultFont', 7))
        self.distance_value.grid(row=2, column=3, sticky='w')
        
        # FILA 3: TARGET Y SOLAPAMIENTO (títulos más cortos)
        ttk.Label(self.metrics_grid, text="🎯 Target:", font=('TkDefaultFont', 7, 'bold')).grid(row=3, column=0, sticky='w', padx=(0, 2))
        self.target_value = ttk.Label(self.metrics_grid, text="—", foreground='#9900CC', font=('TkDefaultFont', 7))
        self.target_value.grid(row=3, column=1, sticky='w', padx=(0, 8))
        
        ttk.Label(self.metrics_grid, text="📡 Overlap:", font=('TkDefaultFont', 7, 'bold')).grid(row=3, column=2, sticky='w', padx=(0, 2))
        self.overlap_value = ttk.Label(self.metrics_grid, text="—", font=('TkDefaultFont', 7))
        self.overlap_value.grid(row=3, column=3, sticky='w')
        
        # FILA 4: FRECUENCIA Y DOPPLER
        ttk.Label(self.metrics_grid, text="📻 Freq:", font=('TkDefaultFont', 7, 'bold')).grid(row=4, column=0, sticky='w', padx=(0, 2))
        self.frequency_value = ttk.Label(self.metrics_grid, text="—", foreground='#0066CC', font=('TkDefaultFont', 7))
        self.frequency_value.grid(row=4, column=1, sticky='w', padx=(0, 8))
        
        ttk.Label(self.metrics_grid, text="🌊 Doppler:", font=('TkDefaultFont', 7, 'bold')).grid(row=4, column=2, sticky='w', padx=(0, 2))
        self.doppler_value = ttk.Label(self.metrics_grid, text="—", foreground='#6600CC', font=('TkDefaultFont', 7))
        self.doppler_value.grid(row=4, column=3, sticky='w')
        
        # FILA 5: OFFSET Y SELECTIVIDAD
        ttk.Label(self.metrics_grid, text="🔄 Offset:", font=('TkDefaultFont', 7, 'bold')).grid(row=5, column=0, sticky='w', padx=(0, 2))
        self.offset_value = ttk.Label(self.metrics_grid, text="—", font=('TkDefaultFont', 7))
        self.offset_value.grid(row=5, column=1, sticky='w', padx=(0, 8))
        
        ttk.Label(self.metrics_grid, text="🔧 Select:", font=('TkDefaultFont', 7, 'bold')).grid(row=5, column=2, sticky='w', padx=(0, 2))
        self.selectivity_value = ttk.Label(self.metrics_grid, text="—", font=('TkDefaultFont', 7))
        self.selectivity_value.grid(row=5, column=3, sticky='w')
        
        # Configurar grid weights para distribución más equilibrada
        self.metrics_grid.columnconfigure(0, weight=1, minsize=80)
        self.metrics_grid.columnconfigure(1, weight=1, minsize=60)
        self.metrics_grid.columnconfigure(2, weight=1, minsize=80)
        self.metrics_grid.columnconfigure(3, weight=1, minsize=60)
        
        self.persistent_metrics_widgets = {
            'title': self.title_label,
            'degradation': self.degradation_value,
            'eirp': self.eirp_value,
            'ci': self.ci_value,
            'distance': self.distance_value,
            'target': self.target_value,
            'overlap': self.overlap_value,
            'frequency': self.frequency_value,
            'doppler': self.doppler_value,
            'offset': self.offset_value,
            'selectivity': self.selectivity_value
        }

    def _on_jammer_tab_changed(self, event):
        """Manejar cambio de pestaña de jammer"""
        try:
            selection = self.jammer_notebook.select()
            if selection:
                tab_text = self.jammer_notebook.tab(selection, "text")
                self.current_jammer_tab = tab_text
                # La actualización de métricas se maneja en update_real_time_metrics
        except Exception as e:
            print(f"Error al cambiar pestaña de jammer: {e}")
    
    def _create_jammer_tab(self, jammer_name: str):
        """Crear una nueva pestaña para un jammer"""
        if jammer_name not in self.jammer_tabs:
            # Crear frame para la pestaña
            tab_frame = ttk.Frame(self.jammer_notebook)
            self.jammer_notebook.add(tab_frame, text=jammer_name)
            self.jammer_tabs[jammer_name] = tab_frame
            
            # Si es la primera pestaña, seleccionarla
            if len(self.jammer_tabs) == 1:
                self.current_jammer_tab = jammer_name
        
        return self.jammer_tabs[jammer_name]
    
    def _remove_jammer_tab(self, jammer_name: str):
        """Remover pestaña de un jammer"""
        if jammer_name in self.jammer_tabs:
            tab_frame = self.jammer_tabs[jammer_name]
            self.jammer_notebook.forget(tab_frame)
            del self.jammer_tabs[jammer_name]
            
            # Si removimos la pestaña activa, seleccionar la primera disponible
            if self.current_jammer_tab == jammer_name:
                if self.jammer_tabs:
                    self.current_jammer_tab = next(iter(self.jammer_tabs.keys()))
                else:
                    self.current_jammer_tab = None
    
    def _update_selected_jammer_metrics(self, jammer_result):
        """Actualizar métricas del jammer seleccionado SIN destruir widgets (anti-parpadeo)"""
        if not self.persistent_metrics_widgets:
            return
        
        if not jammer_result:
            # Mostrar estado sin jammer seleccionado
            self.persistent_metrics_widgets['title'].config(text="📊 Sin jammer seleccionado - Selecciona una pestaña arriba")
            self.persistent_metrics_widgets['degradation'].config(text="—", foreground='#888888')
            self.persistent_metrics_widgets['eirp'].config(text="—", foreground='#888888')
            self.persistent_metrics_widgets['ci'].config(text="—", foreground='#888888')
            self.persistent_metrics_widgets['distance'].config(text="—", foreground='#888888')
            self.persistent_metrics_widgets['target'].config(text="—", foreground='#888888')
            self.persistent_metrics_widgets['overlap'].config(text="—", foreground='#888888')
            self.persistent_metrics_widgets['frequency'].config(text="—", foreground='#888888')
            self.persistent_metrics_widgets['doppler'].config(text="—", foreground='#888888')
            self.persistent_metrics_widgets['offset'].config(text="—", foreground='#888888')
            self.persistent_metrics_widgets['selectivity'].config(text="—", foreground='#888888')
            return
        
        # Actualizar título
        jammer_name = jammer_result.get('jammer_name', 'Unknown')
        self.persistent_metrics_widgets['title'].config(text=f"📊 Métricas Detalladas: {jammer_name}")
        
        # Extraer datos
        jammer_degradation = jammer_result.get("degradation_individual", 0.0)
        jammer_eirp = jammer_result.get("jammer_eirp_dbw", 0.0)
        jammer_ci = jammer_result.get("ci_db", float('inf'))
        jammer_distance = jammer_result.get("distance_km", 0.0)
        target_link = jammer_result.get("target_link_detected", "N/A")
        spectral_overlap = jammer_result.get("spectral_overlap_percent", 0.0)
        jammer_freq = jammer_result.get("jammer_center_freq_ghz", 0.0)
        doppler_comp = jammer_result.get("doppler_compensation_khz", 0.0)
        freq_offset = jammer_result.get("frequency_offset_mhz", 0.0)
        selectivity_factor = jammer_result.get("frequency_selectivity_factor", 1.0)
        
        # Actualizar degradación con color dinámico
        deg_color = '#FF6666' if jammer_degradation >= 3 else '#FFAA66' if jammer_degradation >= 1 else '#AAAAAA'
        self.persistent_metrics_widgets['degradation'].config(text=f"{jammer_degradation:.1f} dB", foreground=deg_color)
        
        # Actualizar EIRP
        self.persistent_metrics_widgets['eirp'].config(text=f"{jammer_eirp:.1f} dBW", foreground='#0066CC')
        
        # Actualizar C/I con color dinámico
        ci_text = f"{jammer_ci:.1f}" if not math.isinf(jammer_ci) else "∞"
        ci_color = '#00AA00' if jammer_ci < 10 else '#FFAA00' if jammer_ci < 20 else '#888888'
        self.persistent_metrics_widgets['ci'].config(text=f"{ci_text} dB", foreground=ci_color)
        
        # Actualizar distancia
        self.persistent_metrics_widgets['distance'].config(text=f"{jammer_distance:.1f} km", foreground='#666666')
        
        # Actualizar target
        self.persistent_metrics_widgets['target'].config(text=target_link, foreground='#9900CC')
        
        # Actualizar solapamiento con color dinámico
        overlap_color = '#00AA00' if spectral_overlap >= 80 else '#FFAA00' if spectral_overlap >= 40 else '#FF4444'
        self.persistent_metrics_widgets['overlap'].config(text=f"{spectral_overlap:.1f}%", foreground=overlap_color)
        
        # Actualizar frecuencia
        self.persistent_metrics_widgets['frequency'].config(text=f"{jammer_freq:.2f} GHz", foreground='#0066CC')
        
        # Actualizar Doppler
        self.persistent_metrics_widgets['doppler'].config(text=f"{doppler_comp:+.1f} kHz", foreground='#6600CC')
        
        # Actualizar offset con color dinámico
        offset_color = '#00AA00' if freq_offset < 10 else '#FFAA00' if freq_offset < 50 else '#FF4444'
        self.persistent_metrics_widgets['offset'].config(text=f"{freq_offset:.1f} MHz", foreground=offset_color)
        
        # Actualizar selectividad con color dinámico
        sel_color = '#00AA00' if selectivity_factor >= 0.8 else '#FFAA00' if selectivity_factor >= 0.5 else '#FF4444'
        self.persistent_metrics_widgets['selectivity'].config(text=f"{selectivity_factor:.2f}", foreground=sel_color)

    def update_real_time_metrics(self, jamming_metrics=None):
        """Actualizar métricas en tiempo real en la GUI para múltiples jammers"""
        try:
            if jamming_metrics and jamming_metrics.get("jamming_enabled", False):
                # Datos disponibles
                combined = jamming_metrics.get("combined_metrics", {})
                advanced = jamming_metrics.get("advanced_metrics", {})
                individual_results = jamming_metrics.get("individual_results", [])
                
                # === EFECTIVIDAD GLOBAL ===
                degradacion_total = combined.get("degradation_db", 0.0)
                if degradacion_total >= 10:
                    efectividad_global = "CRITICO"
                    color_efectividad = '#FF4444'  # Rojo
                elif degradacion_total >= 5:
                    efectividad_global = "EFECTIVO"
                    color_efectividad = '#FF8800'  # Naranja
                elif degradacion_total >= 2:
                    efectividad_global = "MODERADO"
                    color_efectividad = '#FFAA00'  # Amarillo
                elif degradacion_total >= 0.5:
                    efectividad_global = "LIMITADO"
                    color_efectividad = '#CCCC00'  # Amarillo oscuro
                else:
                    efectividad_global = "INEFECTIVO"
                    color_efectividad = '#888888'  # Gris
                
                self.effectiveness_label.config(
                    text=f"⚡ Efectividad Global: {efectividad_global} ({degradacion_total:.1f}dB total)",
                    foreground=color_efectividad
                )
                
                # === GESTIÓN DE PESTAÑAS DE JAMMERS ===
                current_jammers = {result.get("jammer_name", f"Jammer_{i+1}"): result 
                                 for i, result in enumerate(individual_results)}
                
                # Remover pestañas de jammers que ya no existen
                existing_jammer_names = set(self.jammer_tabs.keys())
                current_jammer_names = set(current_jammers.keys())
                
                for old_jammer in (existing_jammer_names - current_jammer_names):
                    self._remove_jammer_tab(old_jammer)
                
                # Crear pestañas para jammers nuevos
                for jammer_name in current_jammer_names:
                    if jammer_name not in self.jammer_tabs:
                        self._create_jammer_tab(jammer_name)
                
                # Actualizar métricas del jammer seleccionado actualmente
                if self.current_jammer_tab and self.current_jammer_tab in current_jammers:
                    selected_jammer_result = current_jammers[self.current_jammer_tab]
                    self._update_selected_jammer_metrics(selected_jammer_result)
                elif current_jammers:
                    # Si no hay jammer seleccionado, seleccionar el primero
                    first_jammer = next(iter(current_jammers.keys()))
                    self.current_jammer_tab = first_jammer
                    self._update_selected_jammer_metrics(current_jammers[first_jammer])
                else:
                    # No hay jammers activos
                    self._update_selected_jammer_metrics(None)
                
                # Target link global
                target_link = advanced.get("target_link_detected", "UL")
                target_reason = advanced.get("target_reasoning", "")
                self.target_link_label.config(
                    text=f"🎯 Target Primario: {target_link}",
                    foreground='#0066CC'
                )
                
                # Solapamiento espectral total
                overlap = advanced.get("spectral_overlap_percent", 0.0)
                num_jammers = len(individual_results)
                if overlap >= 90:
                    color_overlap = '#00AA00'  # Verde
                elif overlap >= 50:
                    color_overlap = '#FFAA00'  # Amarillo
                else:
                    color_overlap = '#FF4444'  # Rojo
                
                self.spectral_overlap_label.config(
                    text=f"📡 Solapamiento Total: {overlap:.1f}% ({num_jammers} jammers)",
                    foreground=color_overlap
                )
                
                # Compensación Doppler
                doppler_khz = getattr(jamming_metrics, 'current_doppler_khz', 0.0)
                freq_compensated = advanced.get("jammer_center_freq_ghz", 12.0)
                self.doppler_compensation_label.config(
                    text=f"🌊 Doppler: {doppler_khz:+.1f}kHz ({freq_compensated:.3f}GHz)",
                    foreground='#6600CC'
                )
                
                # Estado principal
                self.jamming_status_label.config(
                    text=f"🔴 Jamming: ACTIVO ({len(self.jammers)} jammers configurados)",
                    foreground='#FF4444'
                )
                self.jamming_diagnostic_label.config(
                    text=f"📊 {efectividad_global} | Target: {target_link} | {overlap:.1f}% espectral | {num_jammers} activos",
                    foreground='#333333'
                )
                
            else:
                # Sin jamming activo
                self.effectiveness_label.config(text="⚡ Efectividad Global: —", foreground='#888888')
                
                # Limpiar pestañas de jammers
                for jammer_name in list(self.jammer_tabs.keys()):
                    self._remove_jammer_tab(jammer_name)
                
                # Limpiar métricas del jammer seleccionado
                self._update_selected_jammer_metrics(None)
                
                self.target_link_label.config(text="🎯 Target Primario: —", foreground='#888888')
                self.spectral_overlap_label.config(text="📡 Solapamiento Total: —", foreground='#888888')
                self.doppler_compensation_label.config(text="🌊 Doppler: —", foreground='#888888')
                
                self.jamming_status_label.config(
                    text="🔘 Jamming: DESACTIVADO",
                    foreground='#888888'
                )
                self.jamming_diagnostic_label.config(
                    text="📊 Sin jammers activos en el escenario",
                    foreground='#888888'
                )
                
        except Exception as e:
            # Error en actualización - no bloquear GUI
            self.jamming_diagnostic_label.config(
                text=f"⚠️ Error métricas: {str(e)[:30]}",
                foreground='#FF8800'
            )
    
    def _add_jammer(self):
        """Añadir nuevo jammer"""
        dialog = JammerConfigDialog(self.parent_frame.winfo_toplevel())
        self.parent_frame.wait_window(dialog.window)
        
        if dialog.result:
            config = dialog.result
            self.jammers[config.id] = config
            self._refresh_display()
    
    def _edit_jammer(self, config: JammerConfig):
        """Editar jammer existente"""
        dialog = JammerConfigDialog(self.parent_frame.winfo_toplevel(), config)
        self.parent_frame.wait_window(dialog.window)
        
        if dialog.result:
            updated_config = dialog.result
            # Mantener el mismo ID
            updated_config.id = config.id
            self.jammers[config.id] = updated_config
            self._refresh_display()
    
    def _delete_jammer(self, jammer_id: str):
        """Eliminar jammer"""
        if jammer_id in self.jammers:
            config = self.jammers[jammer_id]
            if messagebox.askyesno("Confirmar", f"¿Eliminar jammer '{config.name}'?"):
                del self.jammers[jammer_id]
                self._refresh_display()
    
    def _refresh_display(self):
        """Actualizar visualización de jammers de forma compacta"""
        # Limpiar widgets existentes en el container
        for widget in self.jammers_container.winfo_children():
            widget.destroy()
        
        num_jammers = len(self.jammers)
        
        if num_jammers == 0:
            # No hay jammers - no mostrar nada extra
            return
        elif num_jammers <= 3:
            # Pocos jammers - mostrar directamente sin scroll
            for config in self.jammers.values():
                JammerWidget(self.jammers_container, config, self._edit_jammer, self._delete_jammer)
        else:
            # Muchos jammers - crear canvas con scroll
            self.canvas = tk.Canvas(self.jammers_container, height=90)
            self.scrollbar = ttk.Scrollbar(self.jammers_container, orient="vertical", 
                                         command=self.canvas.yview)
            self.scrollable_frame = ttk.Frame(self.canvas)
            
            self.scrollable_frame.bind(
                "<Configure>",
                lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            )
            
            self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
            self.canvas.configure(yscrollcommand=self.scrollbar.set)
            
            # Añadir jammers al frame scrollable
            for config in self.jammers.values():
                JammerWidget(self.scrollable_frame, config, self._edit_jammer, self._delete_jammer)
            
            # Layout del canvas
            self.canvas.pack(side="left", fill="both", expand=True)
            self.scrollbar.pack(side="right", fill="y")
    
    def get_active_jammers(self) -> List[JammerConfig]:
        """Obtener lista de jammers activos"""
        return [config for config in self.jammers.values() if config.active]
    
    def get_jammer_positions(self, gs_lat: float, gs_lon: float, earth_rotation_deg: float, simulation_time_min: float = 0.0) -> List[Dict]:
        """Calcular posiciones de jammers para visualización"""
        positions = []
        
        for config in self.get_active_jammers():
            # Calcular azimuth actual considerando movimiento orbital
            current_azimuth = config.get_current_azimuth_deg(simulation_time_min)
            
            # Conversión a coordenadas cartesianas (CORREGIDO)
            # Usar SOLO la distancia de superficie para posición horizontal
            surface_distance = config.get_surface_distance_km()
            dx = surface_distance * math.sin(math.radians(current_azimuth))
            dy = surface_distance * math.cos(math.radians(current_azimuth))
            
            # La altura se maneja por separado para la posición vertical
            altitude_km = config.altitude_km
            
            positions.append({
                'id': config.id,
                'name': config.name,
                'lat': gs_lat + dy / 111.0,  # Aproximación: 1° ≈ 111 km
                'lon': gs_lon + dx / (111.0 * math.cos(math.radians(gs_lat))),
                'dx': dx,  # Distancia horizontal desde GS
                'dy': dy,  # Distancia horizontal desde GS
                'altitude_km': altitude_km,  # Altura sobre superficie
                'current_azimuth': current_azimuth,  # Azimuth actual considerando movimiento
                'orbital_info': {
                    'altitude_type': config.altitude_type.value,
                    'period_min': config.orbital_period_min,
                    'angular_velocity': config.angular_velocity_deg_per_min
                },
                'config': config
            })
        
        return positions
    
    def export_config(self) -> Dict:
        """Exportar configuración de jammers"""
        return {
            'jammers': {
                jammer_id: {
                    'name': config.name,
                    'jammer_type': config.jammer_type.value,
                    'antenna_type': config.antenna_type.value,
                    'power_tx_dbw': config.power_tx_dbw,
                    'antenna_gain_dbi': config.antenna_gain_dbi,
                    'frequency_ghz': config.frequency_ghz,
                    'bandwidth_mhz': config.bandwidth_mhz,
                    'distance_from_gs_km': config.distance_from_gs_km,
                    'azimuth_deg': config.azimuth_deg,
                    'active': config.active
                }
                for jammer_id, config in self.jammers.items()
            }
        }
    
    def import_config(self, config_data: Dict):
        """Importar configuración de jammers"""
        if 'jammers' in config_data:
            self.jammers.clear()
            
            for jammer_id, jammer_data in config_data['jammers'].items():
                config = JammerConfig(
                    id=jammer_id,
                    name=jammer_data['name'],
                    jammer_type=JammerType(jammer_data['jammer_type']),
                    antenna_type=AntennaType(jammer_data['antenna_type']),
                    power_tx_dbw=jammer_data['power_tx_dbw'],
                    antenna_gain_dbi=jammer_data['antenna_gain_dbi'],
                    frequency_ghz=jammer_data['frequency_ghz'],
                    bandwidth_mhz=jammer_data['bandwidth_mhz'],
                    distance_from_gs_km=jammer_data['distance_from_gs_km'],
                    azimuth_deg=jammer_data['azimuth_deg'],
                    active=jammer_data['active']
                )
                self.jammers[jammer_id] = config
            
            self._refresh_display()

# Función de utilidad para integración
def create_jammer_manager(parent_frame) -> JammerManager:
    """Función factory para crear el gestor de jammers"""
    return JammerManager(parent_frame)
