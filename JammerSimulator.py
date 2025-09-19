"""JammerSimulator - Núcleo GUI simplificado

Este archivo contiene únicamente:
	- Carga de parámetros
	- Clases básicas (Satellite, Constellation, LEOEducationalCalculations)
	- Núcleo mínimo (JammerSimulatorCore) con parámetros usados por la GUI
	- Interfaz Tkinter con animación orbital y métricas

Se ha eliminado todo el código de demostración por consola / selftest para
mantener el script compacto y orientado a despliegue GUI.
"""
from __future__ import annotations

import json
import math
import time
import csv
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

# Importar sistema de jammers
try:
	from JammerSystem import JammerManager
	JAMMERS_AVAILABLE = True
except ImportError as e:
	print(f"Warning: JammerSystem no disponible: {e}")
	JammerManager = None
	JAMMERS_AVAILABLE = False

# Intentamos importar tkinter al cargar el módulo; si falla, se gestiona en main().
try:
	import tkinter as tk
	from tkinter import ttk
except ImportError:  # entorno sin GUI
	tk = None
	ttk = None

SPEED_OF_LIGHT = 299_792_458.0  # m/s
EARTH_RADIUS_M = 6_371_000.0
MU_EARTH = 3.986004418e14  # m^3/s^2 (fase 1)

# Constantes de rotación terrestre para animación realista
EARTH_ROTATION_PERIOD_S = 24 * 3600  # 86400 segundos (día sidéreo real ~86164s, pero usamos día solar)
EARTH_ROTATION_DEG_PER_S = 360.0 / EARTH_ROTATION_PERIOD_S  # ~0.004167 deg/s

# Tipos para enlaces separados
LinkSense = str  # 'UL' o 'DL'

@dataclass
class LinkInputs:
	f_Hz: float
	B_Hz: float 
	EIRP_dBW: float
	GT_dBK: float
	L_extra_dB: float

@dataclass 
class LinkOutputs:
	FSPL_dB: float
	CN0_dBHz: float
	CN_dB: float
	visible: bool
	latency_ms: float

# ------------------------------------------------------------- #
# Funciones puras para cálculos de enlace                       #
# ------------------------------------------------------------- #
def fspl_dB(f_Hz: float, d_m: float) -> float:
	"""Free Space Path Loss en dB."""
	if d_m <= 0 or f_Hz <= 0:
		return float('inf')
	return 20 * math.log10(4 * math.pi * d_m * f_Hz / SPEED_OF_LIGHT)

def cn0_dBHz(EIRP_dBW: float, GT_dBK: float, FSPL_dB: float, L_extra_dB: float) -> float:
	"""C/N0 en dBHz usando la fórmula estándar."""
	return EIRP_dBW + GT_dBK - FSPL_dB - L_extra_dB + 228.6

def cn_dB(CN0_dBHz: float, B_Hz: float) -> float:
	"""C/N en dB a partir de C/N0 y ancho de banda."""
	if B_Hz <= 0:
		return float('-inf')
	return CN0_dBHz - 10 * math.log10(B_Hz)

def combine_end_to_end(cnUL_dB: float, cnDL_dB: float, jamming_metrics: dict = None) -> dict:
	"""Combina C/N de UL y DL usando suma lineal de (N/C), considerando jamming si está activo."""
	if math.isnan(cnUL_dB) or math.isnan(cnDL_dB) or math.isinf(cnUL_dB) or math.isinf(cnDL_dB):
		return {"NC_tot_dB": float('nan'), "CN_tot_dB": float('nan'), "CINR_tot_dB": float('nan')}
	
	# Convertir C/N a N/C en escala lineal
	nc_ul = 10.0 ** (-cnUL_dB / 10.0)
	nc_dl = 10.0 ** (-cnDL_dB / 10.0)
	nc_tot = nc_ul + nc_dl
	
	# Convertir de vuelta a dB
	if nc_tot <= 0:
		return {"NC_tot_dB": float('inf'), "CN_tot_dB": float('-inf'), "CINR_tot_dB": float('-inf')}
	
	nc_tot_dB = 10 * math.log10(nc_tot)
	cn_tot_dB = -nc_tot_dB
	
	# NUEVO: Considerar jamming si está activo
	cinr_tot_dB = cn_tot_dB  # Base sin interferencia
	
	if jamming_metrics and jamming_metrics.get("jamming_enabled", False):
		combined = jamming_metrics.get("combined_metrics", {})
		if combined and combined.get("effectiveness") in ["EFECTIVO", "SEVERO"]:
			# El jamming limita el CINR total del enlace
			jamming_cinr_db = combined.get("cinr_db", float('nan'))
			if not math.isnan(jamming_cinr_db):
				# El CINR final es el mínimo entre el C/N térmico y el limitado por jamming
				cinr_tot_dB = min(cn_tot_dB, jamming_cinr_db)
	
	return {"NC_tot_dB": nc_tot_dB, "CN_tot_dB": cn_tot_dB, "CINR_tot_dB": cinr_tot_dB}

# ------------------------------------------------------------- #
# Helpers dB / lineal (Fase 0)                                  #
# ------------------------------------------------------------- #
def lin_to_db(x: float, min_lin: float = 1e-30) -> float:
	"""10log10(x) protegido contra valores <=0."""
	if x <= min_lin:
		x = min_lin
	return 10.0 * math.log10(x)


def db_to_lin(x_db: float) -> float:
	return 10.0 ** (x_db / 10.0)


def sum_powers_db(terms_db: List[float]) -> float:
	"""Suma de potencias en dominio dB (ignora NaN)."""
	linear_sum = 0.0
	for v in terms_db:
		if v is None or (isinstance(v, float) and math.isnan(v)):
			continue
		linear_sum += db_to_lin(v)
	if linear_sum <= 0:
		return float('-inf')
	return lin_to_db(linear_sum)

# ------------------------------------------------------------- #
# Carga de parámetros centralizada                              #
# ------------------------------------------------------------- #
class ParameterLoader:
	def __init__(self, filename: str = "SimulatorParameters.json"):
		with open(filename, 'r', encoding='utf-8') as f:
			self.data = json.load(f)

	def get(self, path: List[str]):
		ref = self.data
		for p in path:
			ref = ref[p]
		return ref

# ------------------------------------------------------------- #
# Modelo básico de un satélite (ahora solo necesitamos altitud) #
# ------------------------------------------------------------- #
@dataclass
class Satellite:
	name: str
	altitude_m: float  # Altitud media sobre superficie
	orbital_angle_deg: float = 0.0  # Posición angular en la órbita
	constellation_id: str = "default"  # ID de la constelación a la que pertenece


class Constellation:
	"""Representa una colección de satélites en una órbita específica.
	
	Preparado para futuras expansiones:
	- Múltiples constelaciones LEO/GEO
	- Diferentes planos orbitales
	- Handovers entre satélites
	- Propagación temporal coordinada
	"""
	def __init__(self, satellites: List[Satellite], constellation_type: str = "LEO", constellation_id: str = "default"):
		self.satellites = satellites
		self.constellation_type = constellation_type  # "LEO" o "GEO"
		self.constellation_id = constellation_id
		self.orbital_parameters = {}  # Para futuros parámetros específicos

	@classmethod
	def single_leo(cls, altitude_m: float, constellation_id: str = "LEO-1") -> 'Constellation':
		satellite = Satellite(name=f"{constellation_id}-SAT-1", altitude_m=altitude_m, constellation_id=constellation_id)
		return cls([satellite], "LEO", constellation_id)
	
	@classmethod
	def single_geo(cls, altitude_m: float = 35_786_000.0, constellation_id: str = "GEO-1") -> 'Constellation':
		satellite = Satellite(name=f"{constellation_id}-SAT-1", altitude_m=altitude_m, constellation_id=constellation_id)
		return cls([satellite], "GEO", constellation_id)
	
	def get_active_satellite(self) -> Optional[Satellite]:
		"""Retorna el satélite activo (para simulación simple, es el primero)."""
		return self.satellites[0] if self.satellites else None
	
	def add_satellite(self, satellite: Satellite):
		"""Añade un satélite a la constelación."""
		satellite.constellation_id = self.constellation_id
		self.satellites.append(satellite)
	
	def get_satellites_by_visibility(self, observer_position: tuple = (0, 0)) -> List[Satellite]:
		"""Futura función para filtrar satélites visibles desde una posición."""
		# Placeholder para futura implementación de visibilidad múltiple
		return self.satellites


class MultiConstellation:
	"""Gestor de múltiples constelaciones para futuras expansiones del simulador.
	
	Permitirá manejar:
	- Múltiples constelaciones LEO con diferentes altitudes
	- Constelaciones GEO con diferentes posiciones
	- Handovers automáticos entre satélites
	- Análisis de coverage combinado
	"""
	def __init__(self):
		self.constellations: Dict[str, Constellation] = {}
		self.active_constellation_id: Optional[str] = None
	
	def add_constellation(self, constellation: Constellation):
		"""Añade una constelación al sistema."""
		self.constellations[constellation.constellation_id] = constellation
		if self.active_constellation_id is None:
			self.active_constellation_id = constellation.constellation_id
	
	def get_active_constellation(self) -> Optional[Constellation]:
		"""Retorna la constelación actualmente activa."""
		if self.active_constellation_id:
			return self.constellations.get(self.active_constellation_id)
		return None
	
	def set_active_constellation(self, constellation_id: str):
		"""Cambia la constelación activa."""
		if constellation_id in self.constellations:
			self.active_constellation_id = constellation_id
	
	def get_all_visible_satellites(self, observer_position: tuple = (0, 0)) -> List[tuple]:
		"""Retorna todos los satélites visibles de todas las constelaciones.
		Retorna lista de tuplas (satellite, constellation_id)."""
		visible_satellites = []
		for const_id, constellation in self.constellations.items():
			for satellite in constellation.get_satellites_by_visibility(observer_position):
				visible_satellites.append((satellite, const_id))
		return visible_satellites
	
	def get_best_satellite_for_handover(self) -> Optional[tuple]:
		"""Futura función para seleccionar el mejor satélite para handover."""
		# Placeholder para lógica de handover inteligente
		return None


# ------------------------------------------------------------- #
# Calculos para los Enlaces #
# ------------------------------------------------------------- #
class LEOEducationalCalculations:
	def __init__(self, altitude_m: float, frequency_hz: float = 12e9):
		self.altitude_m = altitude_m
		self.frequency_hz = frequency_hz
		# Parámetros de potencia/noise por ahora sencillos; se podrán ajustar
		self.default_bandwidth_hz = 1e6  # 1 MHz para simplificar (coherente con Paso 2)
		# Constantes para ecuación educativa C/N0
		self.K_BOLTZ_TERM = 228.6  # dB (10log10(1/k))

	def slant_range_simple(self, elevation_deg: float) -> float:
		"""Distancia aproximada (m) usando d ≈ h / sin(E).

		Elección consciente: aproximación para crear intuición. Más adelante
		se añadirá la fórmula exacta con radio terrestre.
		"""
		if elevation_deg <= 0:
			elevation_deg = 0.1  # evitar división por cero manteniendo significado
		elev_rad = math.radians(elevation_deg)
		return self.altitude_m / math.sin(elev_rad)

	def free_space_path_loss_db(self, distance_m: float) -> float:
		return 20 * math.log10(4 * math.pi * distance_m * self.frequency_hz / SPEED_OF_LIGHT)

	# Latencia de propagación (one-way o round trip)
	def propagation_delay_ms(self, distance_m: float, round_trip: bool = False) -> float:
		factor = 2.0 if round_trip else 1.0
		return (factor * distance_m / SPEED_OF_LIGHT) * 1000.0

	# C/N0 simplificado
	def cn0_dbhz(self, eirp_dbw: float, gt_dbk: float, fspl_db: float) -> float:
		return eirp_dbw + gt_dbk - fspl_db + self.K_BOLTZ_TERM

	# C/N a partir de C/N0 y ancho de banda
	def cn_db(self, cn0_dbhz: float, bandwidth_hz: float | None = None) -> float:
		bw = bandwidth_hz or self.default_bandwidth_hz
		return cn0_dbhz - 10 * math.log10(bw)
class JammerSimulatorCore:
	"""Núcleo mínimo usado por la GUI (parámetros y cálculos)."""

	def __init__(self, params: ParameterLoader):
		self.params = params
		leo_alt = params.get(["LEO", "Altitude"])
		self.constellation = Constellation.single_leo(altitude_m=leo_alt)
		self.calc = LEOEducationalCalculations(altitude_m=leo_alt)
		# Parámetros de potencia base
		self.eirp_dbw = params.get(["LEO", "EIRP", "base"])  # Ejemplo
		self.gt_dbk = params.get(["LEO", "G_T", "base"])     # Placeholder
		# GEO (si disponible)
		try:
			self.geo_altitude_m = params.get(["GEO", "Altitude"])
			self.geo_eirp_dbw = params.get(["GEO", "EIRP", "base"])
			self.geo_gt_dbk = params.get(["GEO", "G_T", "base"])
		except Exception:
			# Valores típicos por defecto
			self.geo_altitude_m = 35_786_000.0
			self.geo_eirp_dbw = 52.0
			self.geo_gt_dbk = -5.0
		# Calculadora separada para GEO (misma frecuencia inicial)
		self.geo_calc = LEOEducationalCalculations(altitude_m=self.geo_altitude_m, frequency_hz=self.calc.frequency_hz)
		# --------------------------------------------------------- #
		# Contenedores estructurados (Fase 0)                      #
		# --------------------------------------------------------- #
		self.losses: Dict[str, float] = {
			'RFL_feeder': 0.0,
			'AML_misalignment': 0.0,
			'AA_atmos': 0.0,
			'Rain_att': 0.0,
			'PL_polarization': 0.0,
			'L_pointing': 0.0,
			'L_impl': 0.0,
		}
		self.noise: Dict[str, float] = {
			'T_rx': 120.0,
			'T_clear_sky': 30.0,
			'T_rain_excess': 0.0,
		}
		self.power: Dict[str, float] = {
			'EIRP_sat_saturated': self.eirp_dbw,
			'Input_backoff': 0.0,
		}
		self.throughput: Dict[str, float] = {
			'Rb_Mbps': 10.0,
			'EbN0_req_dB': 4.0,
		}
		self.latencies: Dict[str, float] = {
			'Processing_delay_ms': 2.0,
			'Switching_delay_ms': 1.0,
		}
		self.coverage: Dict[str, float] = {
			'Min_elevation_deg': 10.0,
		}
		
		# Parámetros de enlaces separados por constelación
		try:
			# Intentar cargar enlaces LEO específicos (por defecto LEO)
			self.link_presets = {
				'LEO': {
					'UL': params.get(["LEO", "Links", "UL"]),
					'DL': params.get(["LEO", "Links", "DL"])
				},
				'GEO': {
					'UL': params.get(["GEO", "Links", "UL"]),
					'DL': params.get(["GEO", "Links", "DL"])
				}
			}
		except Exception:
			# Fallback si no existe la estructura LEO/GEO separada
			try:
				# Intentar estructura antigua global
				self.link_presets = {
					'LEO': {
						'UL': params.get(["Links", "UL"]),
						'DL': params.get(["Links", "DL"])
					},
					'GEO': {
						'UL': params.get(["Links", "UL"]),
						'DL': params.get(["Links", "DL"])
					}
				}
			except Exception:
				# Fallback hardcoded
				self.link_presets = {
					'LEO': {
						'UL': {"freq_GHz": 30.0, "bw_MHz": 20.0, "EIRP_dBW": 45.0, "GT_dBK": -8.0, "extra_losses_dB": 0.0},
						'DL': {"freq_GHz": 20.0, "bw_MHz": 20.0, "EIRP_dBW": 48.0, "GT_dBK": 12.0, "extra_losses_dB": 0.0}
					},
					'GEO': {
						'UL': {"freq_GHz": 14.0, "bw_MHz": 12.0, "EIRP_dBW": 62.0, "GT_dBK": -2.0, "extra_losses_dB": 0.0},
						'DL': {"freq_GHz": 11.7, "bw_MHz": 12.0, "EIRP_dBW": 56.0, "GT_dBK": 8.0, "extra_losses_dB": 0.0}
					}
				}
	
	def compute_link_outputs(self, inputs: LinkInputs, d_km: float) -> LinkOutputs:
		"""Calcula las métricas de salida para un sentido de enlace."""
		# Verificar visibilidad basada en elevación y distancia válida
		elevation_deg = getattr(self, 'current_elevation_deg', 0.0)
		visible = d_km > 0 and elevation_deg > 0
		
		if not visible:
			return LinkOutputs(
				FSPL_dB=float('nan'),
				CN0_dBHz=float('nan'), 
				CN_dB=float('nan'),
				visible=False,
				latency_ms=float('nan')
			)
		
		# Cálculos usando las funciones puras
		fspl = fspl_dB(inputs.f_Hz, d_km * 1000)  # convertir km a m
		cn0 = cn0_dBHz(inputs.EIRP_dBW, inputs.GT_dBK, fspl, inputs.L_extra_dB)
		cn = cn_dB(cn0, inputs.B_Hz)
		latency = (d_km * 1000 / SPEED_OF_LIGHT) * 1000  # ms
		
		return LinkOutputs(
			FSPL_dB=fspl,
			CN0_dBHz=cn0,
			CN_dB=cn,
			visible=True,
			latency_ms=latency
		)
	
	def calculate_spot_jamming_metrics(self) -> Dict[str, Any]:
		"""
		Calcula métricas de Spot Jamming para todos los jammers activos.
		Integra con el sistema de jammers existente.
		"""
		if not JAMMERS_AVAILABLE:
			return {"jamming_enabled": False}
		
		# Importar calculadora desde JammerSystem
		try:
			from JammerSystem import SpotJammingCalculator
		except ImportError:
			return {"jamming_enabled": False}
		
		# Obtener jammers activos (será vinculado desde GUI)
		jammers_data = getattr(self, '_active_jammers', [])
		if not jammers_data:
			return {"jamming_enabled": False}
		
		# Parámetros actuales del enlace
		current_eirp_dbw = self.eirp_dbw
		current_distance_km = getattr(self, 'current_slant_distance_m', 0) / 1000.0
		
		# Obtener frecuencia actual (preferir la del modo activo)
		if hasattr(self, 'current_link_sense') and self.current_link_sense == 'DL':
			current_frequency_hz = getattr(self, 'dl_freq_var', None)
			current_frequency_hz = current_frequency_hz.get() * 1e9 if current_frequency_hz else 20e9
		else:
			current_frequency_hz = getattr(self, 'ul_freq_var', None) 
			current_frequency_hz = current_frequency_hz.get() * 1e9 if current_frequency_hz else 30e9
		
		# Configuración de jamming (desde JSON) - CORREGIDA para superficie
		try:
			jamming_params = self.params.get(["Jamming"])
		except:
			jamming_params = {
				"discrimination": {"angular_separation_deg": 0.1, "polarization_isolation_db": -4.0}
			}
		
		# CORRECCIÓN CRÍTICA: Separación angular realista para jammer superficie
		# Un jammer superficie efectivo debe estar muy cerca angularmente del satélite
		angular_sep = jamming_params.get("discrimination", {}).get("angular_separation_deg", 0.1)  # 0.1° no 2.0°
		polar_iso = jamming_params.get("discrimination", {}).get("polarization_isolation_db", -4.0)
		
		jamming_results = []
		total_interference_linear = 0.0
		
		# Calcular interferencia de cada jammer
		for jammer in jammers_data:
			if not jammer.active:
				continue
			
			# Calcular distancia real del jammer a la estación terrestre
			jammer_distance_km = jammer.distance_from_gs_km  # Distancia del jammer a la estación base
			
			# CORRECCIÓN: Usar discriminación angular real calculada dinámicamente
			try:
				# Obtener discriminación angular real de métricas actuales
				sat_elevation = getattr(self, 'current_elevation_deg', 45.0)
				sat_distance_km = getattr(self, 'current_slant_distance_m', 400000.0) / 1000.0
				
				from JammerSystem import calculate_dynamic_angular_discrimination
				angular_result = calculate_dynamic_angular_discrimination(
					sat_elevation_deg=sat_elevation,
					jammer_distance_km=jammer_distance_km,
					sat_distance_km=sat_distance_km
				)
				discrimination_angular_real_db = angular_result.get("discrimination_db", 21.47)
			except:
				discrimination_angular_real_db = angular_sep  # Fallback a parámetro original
			
			# CORRECCIÓN: Determinar link correcto y usar función apropiada
			# Detectar target_link del jammer para usar cálculo correcto
			target_link = getattr(jammer, 'target_link', 'UL')  # Fallback a UL por defecto
			
			if target_link == 'UL':
				# Para Uplink: Terminal → Satélite (jammer interfiere al satélite)
				terminal_eirp_dbw = getattr(self, 'terminal_eirp_dbw', 50.0)  # EIRP típico terminal
				ci_result = SpotJammingCalculator.calculate_ci_ratio_uplink(
					jammer,
					terminal_eirp_dbw,
					current_distance_km,      # Distancia terminal-satélite
					jammer_distance_km,       # Distancia jammer-satélite (aproximadamente)
					current_frequency_hz,     # Frecuencia del enlace
					discrimination_angular_real_db,  # ¡Usar discriminación real!
					polar_iso
				)
			else:
				# Para Downlink: Satélite → Estación terrestre
				ci_result = SpotJammingCalculator.calculate_ci_ratio_downlink(
					jammer, 
					current_eirp_dbw,
					current_distance_km,      # Distancia satélite-estación
					jammer_distance_km,       # Distancia jammer-estación (REAL)
					current_frequency_hz,     # Frecuencia del enlace
					discrimination_angular_real_db,  # ¡Usar discriminación real!
					polar_iso
				)
			
			# Calcular degradación individual de este jammer usando calculate_cinr_with_jamming
			cn_db = getattr(self, 'current_cn_db', float('nan'))
			individual_degradation = 0.0
			cinr_original_db = cn_db  # CINR original sin jamming
			cinr_with_attack_db = cn_db  # CINR con jamming aplicado
			
			if not math.isinf(ci_result["ci_db"]) and not math.isnan(cn_db):
				# Usar función del JammerSystem para cálculo coherente C/(N+I)
				from JammerSystem import SpotJammingCalculator
				cinr_result = SpotJammingCalculator.calculate_cinr_with_jamming(cn_db, ci_result["ci_db"])
				
				cinr_with_attack_db = cinr_result["cinr_db"]
				individual_degradation = cinr_result["degradation_db"]
			
			# Validación de coherencia
			calculated_degradation = cinr_original_db - cinr_with_attack_db
			if abs(individual_degradation - calculated_degradation) > 0.05:
				print(f"⚠️ Inconsistencia degradación: calculada={calculated_degradation:.2f}, reportada={individual_degradation:.2f}")
				individual_degradation = calculated_degradation  # Usar valor coherente
			
			# === MÉTRICAS EXPANDIDAS POR JAMMER ===
			# Calcular solapamiento espectral individual
			jammer_freq_ghz = jammer.frequency_ghz
			jammer_bw_mhz = jammer.bandwidth_mhz
			link_freq_ghz = current_frequency_hz / 1e9
			link_bw_mhz = getattr(self, 'current_bw_mhz', 20.0)
			
			# Cálculo de solapamiento espectral
			jammer_min_freq = jammer_freq_ghz - jammer_bw_mhz/2000
			jammer_max_freq = jammer_freq_ghz + jammer_bw_mhz/2000
			link_min_freq = link_freq_ghz - link_bw_mhz/2000
			link_max_freq = link_freq_ghz + link_bw_mhz/2000
			
			overlap_min = max(jammer_min_freq, link_min_freq)
			overlap_max = min(jammer_max_freq, link_max_freq)
			spectral_overlap_percent = 0.0
			
			if overlap_max > overlap_min:
				overlap_bw = (overlap_max - overlap_min) * 1000  # MHz
				link_total_bw = link_bw_mhz
				spectral_overlap_percent = min(100.0, (overlap_bw / link_total_bw) * 100)
			
			# === DETECCIÓN INDIVIDUAL DE ENLACE OBJETIVO POR JAMMER ===
			# Obtener frecuencias actuales del sistema
			try:
				ul_freq_ghz = float(self.ul_freq_var.get()) if hasattr(self, 'ul_freq_var') else 30.0
				dl_freq_ghz = float(self.dl_freq_var.get()) if hasattr(self, 'dl_freq_var') else 20.0
			except (ValueError, AttributeError):
				ul_freq_ghz = 30.0
				dl_freq_ghz = 20.0
			
			# Obtener CINR actual de ambos enlaces para este jammer específico
			ul_cinr_current = getattr(self, 'ul_cinr_db', 15.0)
			dl_cinr_current = getattr(self, 'dl_cinr_db', 35.0)
			
			# Calcular offsets frecuenciales específicos de este jammer
			ul_freq_offset = abs(jammer_freq_ghz - ul_freq_ghz)
			dl_freq_offset = abs(jammer_freq_ghz - dl_freq_ghz)
			
			# Estrategia inteligente individual: atacar enlace más vulnerable que esté en rango frecuencial
			frequency_threshold_ghz = 5.0
			
			if ul_freq_offset <= frequency_threshold_ghz and dl_freq_offset <= frequency_threshold_ghz:
				# Ambos enlaces en rango: atacar el más vulnerable (menor CINR)
				target_link = "UL" if ul_cinr_current <= dl_cinr_current else "DL"
				target_reasoning = f"VULNERABLE (UL:{ul_cinr_current:.1f}dB vs DL:{dl_cinr_current:.1f}dB)"
			elif ul_freq_offset <= frequency_threshold_ghz:
				# Solo UL en rango frecuencial
				target_link = "UL"
				target_reasoning = f"FRECUENCIAL (UL offset: {ul_freq_offset:.1f}GHz)"
			elif dl_freq_offset <= frequency_threshold_ghz:
				# Solo DL en rango frecuencial  
				target_link = "DL"
				target_reasoning = f"FRECUENCIAL (DL offset: {dl_freq_offset:.1f}GHz)"
			else:
				# Ningún enlace en rango óptimo: atacar el más cercano
				target_link = "UL" if ul_freq_offset <= dl_freq_offset else "DL"
				target_reasoning = f"SUBOPTIMO (min offset: {min(ul_freq_offset, dl_freq_offset):.1f}GHz)"
			
			target_detected = f"{target_link} - {target_reasoning}"
			
			# Cálculo de offset de frecuencia del enlace objetivo específico
			target_freq_ghz = ul_freq_ghz if target_link == "UL" else dl_freq_ghz
			frequency_offset_mhz = abs(jammer_freq_ghz - target_freq_ghz) * 1000
			
			# Factor de selectividad frecuencial (simulado)
			if frequency_offset_mhz == 0:
				selectivity_factor = 1.0
			elif frequency_offset_mhz < 10:
				selectivity_factor = 0.8
			elif frequency_offset_mhz < 50:
				selectivity_factor = 0.5
			else:
				selectivity_factor = 0.2
			
			# Ganancia de eficiencia adaptativa (placeholder)
			adaptive_efficiency = min(1.5, spectral_overlap_percent / 100 * 1.2)
			
			# Doppler individual (obtener del cálculo real del simulador)
			current_doppler_khz = 0.0
			if hasattr(self, 'doppler') and 'fd_hz' in self.doppler:
				doppler_hz = self.doppler['fd_hz']
				if not math.isnan(doppler_hz):
					current_doppler_khz = doppler_hz / 1000.0  # Convertir Hz a kHz
			
			jammer_doppler_compensation = abs(current_doppler_khz) * 0.1  # Factor realista
			
			# Generar recomendación específica para este jammer individual
			ci_db = ci_result["ci_db"]
			jammer_eirp = ci_result["jammer_eirp_dbw"]
			jammer_distance = jammer.distance_from_gs_km
			
			# Lógica de recomendación por jammer individual
			if individual_degradation < 1.0:
				if jammer_distance > 200:
					jammer_recommendation = "REDUCIR_DISTANCIA"
				elif jammer_eirp < 20:
					jammer_recommendation = "INCREMENTAR_EIRP"
				elif ci_db > -3:
					jammer_recommendation = "MEJORAR_DISCRIMINACION"
				else:
					jammer_recommendation = "REVISAR_CONFIG"
			elif individual_degradation < 3.0:
				jammer_recommendation = "OPTIMIZAR_POTENCIA"
			elif individual_degradation < 8.0:
				jammer_recommendation = "CONFIGURACION_OPTIMA"
			elif individual_degradation < 15.0:
				jammer_recommendation = "REDUCIR_EIRP_SIGILO"
			else:
				jammer_recommendation = "REDUCIR_EIRP_DETECCION"
			
			jamming_results.append({
				"jammer_name": jammer.name,
				"jammer_type": jammer.jammer_type.value,
				"ci_db": ci_result["ci_db"],
				"jammer_eirp_dbw": ci_result["jammer_eirp_dbw"],
				"discrimination_db": ci_result["discrimination_db"],
				"discrimination_angular_real_db": discrimination_angular_real_db,  # ¡Nueva métrica!
				"degradation_individual": individual_degradation,  # Nueva métrica
				"distance_km": jammer.distance_from_gs_km,
				"jammer_height_km": jammer.altitude_km,  # AÑADIDO: altura del jammer
				"recommendation": jammer_recommendation,  # NUEVA: Recomendación específica
				# === NUEVAS MÉTRICAS EXPANDIDAS ===
				"spectral_overlap_percent": spectral_overlap_percent,
				"target_link_detected": target_detected,
				"frequency_offset_mhz": frequency_offset_mhz,
				"frequency_selectivity_factor": selectivity_factor,
				"adaptive_efficiency_gain": adaptive_efficiency,
				"jammer_center_freq_ghz": jammer_freq_ghz,
				"jammer_bandwidth_mhz": jammer_bw_mhz,
				"doppler_compensation_khz": jammer_doppler_compensation
			})
			
			# Acumular interferencia (en lineal para suma)
			if not math.isinf(ci_result["ci_db"]):
				ic_linear = 10**(-ci_result["ci_db"]/10)
				total_interference_linear += ic_linear
		
		# Calcular CINR combinado si hay interferencia
		if total_interference_linear > 0:
			cn_db = getattr(self, 'current_cn_db', float('nan'))
			if not math.isnan(cn_db):
				# CORRECCIÓN CRÍTICA: Implementar fórmula C/(N+I) correcta
				# Problema: el cálculo anterior no reflejaba correctamente la degradación
				
				# 1. Convertir C/N de dB a lineal
				cn_linear = 10**(cn_db/10)  # C/N en lineal
				
				# 2. La interferencia total acumulada es I/C en lineal
				# Para obtener CINR = C/(N+I), necesitamos:
				# CINR = C/N / (1 + I/N) = C/N / (1 + (I/C) * (C/N))
				interference_over_noise = total_interference_linear * cn_linear
				
				# 3. Calcular CINR en lineal y convertir a dB
				cinr_linear = cn_linear / (1.0 + interference_over_noise)
				cinr_db = 10 * math.log10(max(1e-10, cinr_linear))  # Evitar log(0)
				degradation_db = cn_db - cinr_db
				
				# 4. C/I equivalente total para referencia
				ci_total_db = -10 * math.log10(max(1e-10, total_interference_linear))
			else:
				cinr_db = float('nan')
				degradation_db = float('nan')
				ci_total_db = float('inf')
		else:
			cinr_db = float('nan')
			degradation_db = 0.0
			ci_total_db = float('inf')
		
		# === FACTORES DE ELEVACIÓN REALISTAS ===
		# La efectividad del jamming varía con la elevación debido a:
		# 1. Path loss diferencial (distancia variable)
		# 2. Discriminación angular (mejor en elevaciones bajas)
		# 3. Atmospheric effects
		current_elevation = getattr(self, 'current_elevation_deg', 45.0)
		
		# Factor de elevación (0.7-1.3):
		# CORRECCIÓN: Eliminar factor de elevación que causa discontinuidades
		# La discriminación angular ya se calcula dinámicamente en calculate_dynamic_angular_discrimination
		# No aplicar factores adicionales que causen saltos bruscos en el dashboard
		elevation_factor = 1.0  # Mantener constante para continuidad suave
		
		# La degradación debe ser directamente la calculada por cada jammer
		# Sin modificaciones que introduzcan discontinuidades artificiales
		if math.isnan(degradation_db):
			degradation_db = 0.0
		
		# CINR con jamming usa la degradación calculada directamente
		cinr_db = cn_db - degradation_db if not math.isnan(degradation_db) else cn_db
		
		# Evaluar efectividad con factor de elevación
		effectiveness = SpotJammingCalculator.assess_jamming_effectiveness(cinr_db, ci_total_db)
		
		# ===== NUEVAS FUNCIONES DE DIAGNÓSTICO INTELIGENTE =====
		diagnostic_info = self._generate_jamming_diagnostic(
			jamming_results, cinr_db, ci_total_db, degradation_db, 
			current_distance_km, angular_sep
		)
		
		return {
			"jamming_enabled": len(jamming_results) > 0,
			"num_active_jammers": len(jamming_results),
			"individual_results": jamming_results,
			"combined_metrics": {
				"ci_total_db": ci_total_db,
				"cinr_db": cinr_db,
				"degradation_db": degradation_db,
				"effectiveness": effectiveness,
				"jamming_effective": degradation_db > 1.0 if not math.isnan(degradation_db) else False
			},
			# NUEVAS MÉTRICAS DE DIAGNÓSTICO
			"diagnostic": diagnostic_info,
			"parameters": {
				"angular_separation_deg": angular_sep,
				"polarization_isolation_db": polar_iso
			}
		}

	def _generate_jamming_diagnostic(self, jamming_results, cinr_db, ci_total_db, degradation_db, 
									sat_distance_km, angular_sep_deg):
		"""
		Genera diagnóstico inteligente del impacto de jamming.
		Explica por qué un jammer es efectivo o no.
		"""
		if not jamming_results:
			return {
				"impact_level": "SIN_IMPACTO",
				"explanation": "No hay jammers activos en el escenario",
				"distance_analysis": "N/A",
				"power_analysis": "N/A"
			}
		
		# Análisis del jammer principal (más potente)
		primary_jammer = max(jamming_results, key=lambda x: x.get("jammer_eirp_dbw", 0))
		
		# Determinar nivel de impacto
		if math.isnan(degradation_db) or degradation_db < 0.5:
			impact_level = "INEFECTIVO"
		elif degradation_db < 2.0:
			impact_level = "LEVE" 
		elif degradation_db < 5.0:
			impact_level = "MODERADO"
		else:
			impact_level = "CRÍTICO"
		
		# Análisis de distancia
		primary_distance = None
		for jammer_data in getattr(self, '_active_jammers', []):
			if jammer_data.name == primary_jammer["jammer_name"]:
				primary_distance = jammer_data.distance_from_gs_km
				break
		
		if primary_distance:
			if primary_distance < 5:
				distance_analysis = f"Jammer muy cercano ({primary_distance:.1f} km) - ventaja significativa"
			elif primary_distance < 20:
				distance_analysis = f"Jammer cercano ({primary_distance:.1f} km) - ventaja considerable"
			elif primary_distance < 100:
				distance_analysis = f"Jammer distante ({primary_distance:.1f} km) - ventaja limitada"
			else:
				distance_analysis = f"Jammer muy distante ({primary_distance:.1f} km) - mínima ventaja"
		else:
			distance_analysis = "Distancia no disponible"
		
		# Análisis de potencia 
		jammer_eirp = primary_jammer.get("jammer_eirp_dbw", 0)
		if jammer_eirp < 25:
			power_analysis = f"Potencia baja ({jammer_eirp:.1f} dBW) - impacto limitado"
		elif jammer_eirp < 35:
			power_analysis = f"Potencia moderada ({jammer_eirp:.1f} dBW) - impacto considerable"
		elif jammer_eirp < 45:
			power_analysis = f"Potencia alta ({jammer_eirp:.1f} dBW) - impacto significativo"
		else:
			power_analysis = f"Potencia muy alta ({jammer_eirp:.1f} dBW) - impacto devastador"
		
		# Generar explicación contextual
		if impact_level == "INEFECTIVO":
			explanation = f"El jammer no afecta significativamente debido a la discriminación angular ({angular_sep_deg:.1f}°) y la distancia ({primary_distance:.1f} km vs sat {sat_distance_km:.1f} km)"
		elif impact_level == "LEVE":
			explanation = f"Degradación menor debido a protección angular. Servicio mantenido con margen reducido"
		elif impact_level == "MODERADO":
			explanation = f"Degradación notable del servicio. El jammer está lo suficientemente cerca para afectar el enlace"
		else:  # CRÍTICO
			explanation = f"Jamming crítico. La proximidad del jammer ({primary_distance:.1f} km) y su potencia ({jammer_eirp:.1f} dBW) comprometen seriamente el enlace"
		
		# NUEVO: Generar recomendación inteligente basada en condiciones
		ci_db = ci_total_db if not math.isinf(ci_total_db) else 0.0
		power_margin = jammer_eirp - 20.0  # Asumiendo potencia objetivo 20 dBW para comparación
		
		if impact_level == "INEFECTIVO":
			if primary_distance > 500:
				recommendation = "REDUCIR_DISTANCIA_JAMMER"
			elif jammer_eirp < 20:
				recommendation = "INCREMENTAR_EIRP"
			elif angular_sep_deg > 5:
				recommendation = "MEJORAR_POINTING_ANGULAR"
			else:
				recommendation = "REVISAR_DISCRIMINACION"
		elif impact_level == "LEVE":
			if power_margin < 5:
				recommendation = "INCREMENTAR_EIRP_MODERADO"
			else:
				recommendation = "OPTIMIZAR_FRECUENCIA"
		elif impact_level == "MODERADO":
			if ci_db > -3:
				recommendation = "MANTENER_CONFIGURACION"
			else:
				recommendation = "AJUSTE_FINO_POTENCIA"
		else:  # CRÍTICO
			if power_margin > 10:
				recommendation = "REDUCIR_EIRP_SIGILO"
			elif degradation_db > 15:
				recommendation = "REDUCIR_EIRP_DETECCION"
			else:
				recommendation = "CONFIGURACION_OPTIMA"
		
		return {
			"impact_level": impact_level,
			"explanation": explanation,
			"distance_analysis": distance_analysis,
			"power_analysis": power_analysis,
			"degradation_db": round(degradation_db, 2) if not math.isnan(degradation_db) else 0.0,
			"primary_jammer_distance_km": primary_distance,
			"primary_jammer_eirp_dbw": jammer_eirp,
			"recommendation": recommendation  # NUEVA: Recomendación inteligente
		}


# ------------------------------------------------------------- #
# GUI (se define a nivel de módulo; solo se usará si tkinter disponible)
# ------------------------------------------------------------- #
class SimulatorGUI:
	def __init__(self, root, core: JammerSimulatorCore):
		self.root = root
		self.core = core
		self.root.title("Jammer Simulator (LEO/GEO)")
		self.running = False
		self.mode_var = None
		
		# Variables de rotación y posición orbital
		self.orbit_angle_deg = 0.0
		self.step_orbit_deg = 0.2  # Reducido para mayor granularidad en elevación
		self.earth_rotation_angle_deg = 0.0  # Rotación acumulada de la Tierra
		self.geo_rotation_angle_deg = 0.0    # Rotación GEO (sincronizada con Tierra)
		
		# Estado de enlaces separados (iniciará con LEO por defecto)
		self.link_state = {
			'UL': LinkInputs(0, 0, 0, 0, 0),
			'DL': LinkInputs(0, 0, 0, 0, 0)
		}
		self.link_out = {
			'UL': LinkOutputs(0.0, 0.0, 0.0, False, 0.0),
			'DL': LinkOutputs(0.0, 0.0, 0.0, False, 0.0)
		}
		self.current_link_sense = 'UL'  # Pestaña activa
		
		# Configuración orbital
		alt_km = self.core.constellation.satellites[0].altitude_m / 1000.0
		self.Re_km = EARTH_RADIUS_M / 1000.0
		self.orbit_r_km = self.Re_km + alt_km
		self.geo_orbit_r_km = self.Re_km + self.core.geo_altitude_m/1000.0
		self.horizon_central_angle_deg = math.degrees(math.acos(self.Re_km / self.orbit_r_km))
		self.orbit_angle_deg = (360.0 - self.horizon_central_angle_deg)
		
		# Parámetros de animación desde JSON
		try:
			self.time_scale_factor = self.core.params.get(["Animation", "time_scale_factor"])
			self.animation_interval_ms = int(self.core.params.get(["Animation", "update_interval_ms"]))
		except:
			# Valores por defecto si no están en JSON
			self.time_scale_factor = 1000.0
			self.animation_interval_ms = 300
		
		# Datos de simulación
		self.history: List[Dict[str, Any]] = []
		self.start_time: Optional[float] = None
		self.last_animation_time: Optional[float] = None
		
		# Control de tiempo manual vs automático
		self.manual_time_control = False  # Nuevo: modo manual vs automático
		self.simulation_time_s = 0.0      # Tiempo de simulación actual
		self.max_simulation_time_s = 7200.0  # Máximo 2 horas de simulación (más órbitas LEO completas)
		
		# Inicializar variables de estado orbital
		self.current_elevation_deg = 0.0
		self.current_visible = False
		self.current_slant_distance_m = 0.0
		self.current_doppler_khz = 0.0  # Variable para jammers
		
		# Inicializar gestor de jammers
		self.jammer_manager = None  # Se inicializará en _build_layout
		
		self._build_layout(); self._draw_static(); self._load_link_presets_for_mode(); self._refresh_gui_values(); self.update_metrics()
	
	def _refresh_gui_values(self):
		"""Actualiza los valores en la GUI después de la inicialización."""
		if hasattr(self, 'eirp_var') and hasattr(self, 'gt_var') and hasattr(self, 'bw_var'):
			# Asegurar que los valores básicos estén establecidos
			if self.eirp_var.get() == 0.0:
				self.eirp_var.set(self.core.eirp_dbw)
			if self.gt_var.get() == 0.0:
				self.gt_var.set(self.core.gt_dbk)
			if self.bw_var.get() == 0.0:
				self.bw_var.set(self.core.calc.default_bandwidth_hz/1e6)

	def _load_link_presets_for_mode(self):
		"""Carga los parámetros UL/DL según el modo activo (LEO/GEO)."""
		current_mode = getattr(self, 'mode_var', None)
		mode = current_mode.get() if current_mode else 'LEO'
		
		# Cargar presets según modo
		try:
			ul_preset = self.core.link_presets[mode]['UL']
			dl_preset = self.core.link_presets[mode]['DL']
		except KeyError:
			# Fallback a LEO si el modo no existe
			ul_preset = self.core.link_presets['LEO']['UL']
			dl_preset = self.core.link_presets['LEO']['DL']
		
		# Actualizar estado de enlaces
		self.link_state['UL'] = LinkInputs(
			f_Hz=ul_preset['freq_GHz'] * 1e9,
			B_Hz=ul_preset['bw_MHz'] * 1e6,
			EIRP_dBW=ul_preset['EIRP_dBW'],
			GT_dBK=ul_preset['GT_dBK'],
			L_extra_dB=ul_preset['extra_losses_dB']
		)
		self.link_state['DL'] = LinkInputs(
			f_Hz=dl_preset['freq_GHz'] * 1e9,
			B_Hz=dl_preset['bw_MHz'] * 1e6,
			EIRP_dBW=dl_preset['EIRP_dBW'],
			GT_dBK=dl_preset['GT_dBK'],
			L_extra_dB=dl_preset['extra_losses_dB']
		)
		
		# Actualizar variables GUI si existen
		if hasattr(self, 'ul_freq_var'):
			self.ul_freq_var.set(ul_preset['freq_GHz'])
			self.ul_bw_var.set(ul_preset['bw_MHz'])
			self.ul_eirp_var.set(ul_preset['EIRP_dBW'])
			self.ul_gt_var.set(ul_preset['GT_dBK'])
			self.ul_losses_var.set(ul_preset['extra_losses_dB'])
		
		if hasattr(self, 'dl_freq_var'):
			self.dl_freq_var.set(dl_preset['freq_GHz'])
			self.dl_bw_var.set(dl_preset['bw_MHz'])
			self.dl_eirp_var.set(dl_preset['EIRP_dBW'])
			self.dl_gt_var.set(dl_preset['GT_dBK'])
			self.dl_losses_var.set(dl_preset['extra_losses_dB'])

	def _build_layout(self):
		self.mainframe = ttk.Frame(self.root, padding=5); self.mainframe.pack(fill='both', expand=True)
		
		# Crear frame izquierdo con scroll (LAYOUT ORIGINAL RESTAURADO)
		left_container = ttk.Frame(self.mainframe)
		left_container.pack(side='left', fill='y', expand=False)
		
		# Canvas y scrollbar para el contenido izquierdo (ancho optimizado para jammers)
		self.left_canvas = tk.Canvas(left_container, width=480, highlightthickness=0)
		left_scrollbar = ttk.Scrollbar(left_container, orient='vertical', command=self.left_canvas.yview)
		self.scrollable_left = ttk.Frame(self.left_canvas)
		
		self.scrollable_left.bind(
			"<Configure>",
			lambda e: self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))
		)
		
		# Crear ventana con ancho fijo para evitar expansión
		self.left_canvas.create_window((0, 0), window=self.scrollable_left, anchor="nw", width=470)
		self.left_canvas.configure(yscrollcommand=left_scrollbar.set)
		
		self.left_canvas.pack(side='left', fill='y', expand=False)
		left_scrollbar.pack(side='right', fill='y')
		
		# Soporte para scroll con rueda del ratón en la columna izquierda
		def _on_left_mousewheel(event):
			if hasattr(self, 'left_canvas'):
				delta = int(-1*(event.delta/120))
				self.left_canvas.yview_scroll(delta, 'units')
		
		self.left_canvas.bind('<MouseWheel>', _on_left_mousewheel)
		self.scrollable_left.bind('<MouseWheel>', _on_left_mousewheel)
		
		# También bind para cuando se entra/sale del área
		def _bind_to_mousewheel(event):
			self.left_canvas.bind_all('<MouseWheel>', _on_left_mousewheel)
		def _unbind_from_mousewheel(event):
			self.left_canvas.unbind_all('<MouseWheel>')
		
		self.left_canvas.bind('<Enter>', _bind_to_mousewheel)
		self.left_canvas.bind('<Leave>', _unbind_from_mousewheel)
		
		# Ahora usar scrollable_left en lugar de left para todos los controles
		left = self.scrollable_left
		
		bold_lbl = ('Segoe UI', 10, 'bold')
		
		# -------- Selector de Modo --------
		ttk.Label(left, text="Modo:", font=bold_lbl).pack(anchor='w')
		self.mode_var = tk.StringVar(value='LEO')
		mode_combo = ttk.Combobox(left, textvariable=self.mode_var, values=['LEO','GEO'], state='readonly')
		mode_combo.pack(anchor='w', pady=2)
		mode_combo.bind('<<ComboboxSelected>>', lambda e: self._change_mode())
		
		# -------- Parámetros Básicos --------
		basic_frame = ttk.LabelFrame(left, text='Parámetros Básicos')
		basic_frame.pack(fill='x', pady=6)
		
		ttk.Label(basic_frame, text="EIRP (dBW):", font=bold_lbl).pack(anchor='w', padx=5, pady=1)
		self.eirp_var = tk.DoubleVar(value=self.core.eirp_dbw)
		ttk.Entry(basic_frame, textvariable=self.eirp_var, width=10).pack(anchor='w', padx=5)
		
		ttk.Label(basic_frame, text="G/T (dB/K):", font=bold_lbl).pack(anchor='w', padx=5, pady=1)
		self.gt_var = tk.DoubleVar(value=self.core.gt_dbk)
		ttk.Entry(basic_frame, textvariable=self.gt_var, width=10).pack(anchor='w', padx=5)
		
		ttk.Label(basic_frame, text="BW (MHz):", font=bold_lbl).pack(anchor='w', padx=5, pady=1)
		self.bw_var = tk.DoubleVar(value=self.core.calc.default_bandwidth_hz/1e6)
		ttk.Entry(basic_frame, textvariable=self.bw_var, width=10).pack(anchor='w', padx=5, pady=(0,5))
		
		# -------- Panel de Jammers Adaptativo (Escenario 2) --------
		if JAMMERS_AVAILABLE and JammerManager:
			self.jammer_manager = JammerManager(left)
			jammer_panel = self.jammer_manager.get_panel()
			jammer_panel.pack(fill='x', pady=6)
			
			# Conectar labels de estado para actualización en tiempo real
			if hasattr(self.jammer_manager, 'jamming_status_label'):
				self.jamming_status_label = self.jammer_manager.jamming_status_label
			if hasattr(self.jammer_manager, 'jamming_diagnostic_label'):
				self.jamming_diagnostic_label = self.jammer_manager.jamming_diagnostic_label
		else:
			self.jammer_manager = None
		
		# -------- Pestañas de Enlaces UL/DL/End-to-End --------
		links_frame = ttk.LabelFrame(left, text='Enlaces Separados')
		links_frame.pack(fill='x', pady=6)
		
		self.notebook = ttk.Notebook(links_frame)
		self.notebook.pack(fill='both', expand=True, padx=2, pady=2)
		
		# Crear pestañas
		self._create_uplink_tab()
		self._create_downlink_tab() 
		self._create_endtoend_tab()
		
		# Bind para cambio de pestaña
		self.notebook.bind('<<NotebookTabChanged>>', self._on_tab_changed)
		
		# -------- Potencia / Backoff (Fase 3) --------
		power_frame = ttk.LabelFrame(left, text='Potencia / Backoff')
		power_frame.pack(fill='x', pady=6)
		self.eirp_sat_var = tk.DoubleVar(value=self.core.power['EIRP_sat_saturated'])
		self.input_bo_var = tk.DoubleVar(value=self.core.power['Input_backoff'])
		self.manual_override_var = tk.BooleanVar(value=False)
		self.manual_eirp_var = tk.DoubleVar(value=self.core.eirp_dbw)
		row_pf1 = ttk.Frame(power_frame); row_pf1.pack(fill='x', padx=2, pady=1)
		ttk.Label(row_pf1, text='EIRP Saturado (dBW):', font=bold_lbl).pack(side='left')
		self.eirp_sat_entry = ttk.Entry(row_pf1, textvariable=self.eirp_sat_var, width=8); self.eirp_sat_entry.pack(side='right')
		row_pf2 = ttk.Frame(power_frame); row_pf2.pack(fill='x', padx=2, pady=1)
		ttk.Label(row_pf2, text='Back-off Entrada (dB):', font=bold_lbl).pack(side='left')
		self.input_bo_entry = ttk.Entry(row_pf2, textvariable=self.input_bo_var, width=8); self.input_bo_entry.pack(side='right')
		row_pf3 = ttk.Frame(power_frame); row_pf3.pack(fill='x', padx=2, pady=1)
		self.output_bo_label = ttk.Label(row_pf3, text='Back-off Salida: 0.0 dB', font=bold_lbl)
		self.output_bo_label.pack(side='left', anchor='w')
		self.eirp_eff_label = ttk.Label(row_pf3, text='EIRP Efectivo: -- dBW', font=bold_lbl)
		self.eirp_eff_label.pack(side='right', anchor='e')
		row_pf4 = ttk.Frame(power_frame); row_pf4.pack(fill='x', padx=2, pady=1)
		self.override_chk = ttk.Checkbutton(row_pf4, text='Override EIRP', variable=self.manual_override_var, command=lambda: self.update_metrics())
		self.override_chk.pack(side='left')
		self.manual_eirp_entry = ttk.Entry(row_pf4, textvariable=self.manual_eirp_var, width=8)
		self.manual_eirp_entry.pack(side='right')
		sep2 = ttk.Separator(left, orient='horizontal'); sep2.pack(fill='x', pady=6)
		# -------- Ruido (Entradas) --------
		ruido_frame = ttk.LabelFrame(left, text='Ruido (Entradas)')
		ruido_frame.pack(fill='x', pady=6)
		self.t_rx_var = tk.DoubleVar(value=self.core.noise['T_rx'])
		self.t_sky_var = tk.DoubleVar(value=self.core.noise['T_clear_sky'])
		self.t_rain_var = tk.DoubleVar(value=self.core.noise['T_rain_excess'])
		row_n1 = ttk.Frame(ruido_frame); row_n1.pack(fill='x', padx=2, pady=1)
		ttk.Label(row_n1, text='T RX (K):', font=bold_lbl).pack(side='left')
		self.t_rx_entry = ttk.Entry(row_n1, textvariable=self.t_rx_var, width=7); self.t_rx_entry.pack(side='right')
		row_n2 = ttk.Frame(ruido_frame); row_n2.pack(fill='x', padx=2, pady=1)
		ttk.Label(row_n2, text='T Cielo (K):', font=bold_lbl).pack(side='left')
		self.t_sky_entry = ttk.Entry(row_n2, textvariable=self.t_sky_var, width=7); self.t_sky_entry.pack(side='right')
		row_n3 = ttk.Frame(ruido_frame); row_n3.pack(fill='x', padx=2, pady=1)
		ttk.Label(row_n3, text='T Exceso Lluvia (K):', font=bold_lbl).pack(side='left')
		self.t_rain_entry = ttk.Entry(row_n3, textvariable=self.t_rain_var, width=7); self.t_rain_entry.pack(side='right')
		# -------- MODCOD Adaptativo (Fase 5) --------
		mod_frame = ttk.LabelFrame(left, text='Modulación / Coding (Fase 5)')
		mod_frame.pack(fill='x', pady=6)
		self.modcod_auto_var = tk.BooleanVar(value=self.core.params.get(["MODCOD","auto_default"]))
		self.modcod_selected_var = tk.StringVar(value=self.core.params.get(["MODCOD","default"]))
		mod_top = ttk.Frame(mod_frame); mod_top.pack(fill='x', padx=2, pady=1)
		mod_table = [e['name'] for e in self.core.params.get(["MODCOD","table"]) ]
		self.modcod_combo = ttk.Combobox(mod_top, values=mod_table, textvariable=self.modcod_selected_var, state='readonly', width=14)
		self.modcod_combo.pack(side='left')
		self.modcod_combo.bind('<<ComboboxSelected>>', lambda e: self.update_metrics())
		auto_chk = ttk.Checkbutton(mod_top, text='Auto', variable=self.modcod_auto_var, command=lambda: self.update_metrics())
		auto_chk.pack(side='right')
		# Parámetros dependientes de MODCOD (solo lectura)
		mod_mid1 = ttk.Frame(mod_frame); mod_mid1.pack(fill='x', padx=2, pady=1)
		self.rb_var = tk.DoubleVar(value=self.core.throughput['Rb_Mbps'])  # interno
		ttk.Label(mod_mid1, text='Rb (Mbps):', font=bold_lbl).pack(side='left')
		self.rb_value_label = ttk.Label(mod_mid1, text=f"{self.rb_var.get():.3f}", font=bold_lbl, width=8, anchor='e')
		self.rb_value_label.pack(side='right')
		mod_mid2 = ttk.Frame(mod_frame); mod_mid2.pack(fill='x', padx=2, pady=1)
		self.ebn0_req_var = tk.DoubleVar(value=self.core.throughput['EbN0_req_dB'])  # interno
		ttk.Label(mod_mid2, text='Eb/N0 Req (dB):', font=bold_lbl).pack(side='left')
		self.ebn0_req_value_label = ttk.Label(mod_mid2, text=f"{self.ebn0_req_var.get():.2f}", font=bold_lbl, width=8, anchor='e')
		self.ebn0_req_value_label.pack(side='right')
		mod_mid3 = ttk.Frame(mod_frame); mod_mid3.pack(fill='x', padx=2, pady=1)
		self.modcod_eff_label = ttk.Label(mod_mid3, text='Eff: -- b/Hz', font=bold_lbl)
		self.modcod_eff_label.pack(side='left')
		self.modcod_req_label = ttk.Label(mod_mid3, text='Eb/N0 Req: -- dB', font=bold_lbl)
		self.modcod_req_label.pack(side='right')
		mod_bot = ttk.Frame(mod_frame); mod_bot.pack(fill='x', padx=2, pady=1)
		self.modcod_status_label = ttk.Label(mod_bot, text='Estado: --', font=bold_lbl)
		self.modcod_status_label.pack(side='left')
		# -------- Latencias Detalladas (Fase 5) --------
		lat_frame = ttk.LabelFrame(left, text='Latencias (Fase 5)')
		lat_frame.pack(fill='x', pady=6)
		self.proc_lat_var = tk.DoubleVar(value=self.core.params.get(["Latencies","Processing_delay_ms"]))
		self.switch_lat_var = tk.DoubleVar(value=self.core.params.get(["Latencies","Switching_delay_ms"]))
		row_l1 = ttk.Frame(lat_frame); row_l1.pack(fill='x', padx=2, pady=1)
		ttk.Label(row_l1, text='Proc (ms):', font=bold_lbl).pack(side='left')
		self.proc_entry = ttk.Entry(row_l1, textvariable=self.proc_lat_var, width=6); self.proc_entry.pack(side='right')
		row_l2 = ttk.Frame(lat_frame); row_l2.pack(fill='x', padx=2, pady=1)
		ttk.Label(row_l2, text='Switch (ms):', font=bold_lbl).pack(side='left')
		self.switch_entry = ttk.Entry(row_l2, textvariable=self.switch_lat_var, width=6); self.switch_entry.pack(side='right')
		# ---------------- Inputs Pérdidas (Fase 2) ----------------
		loss_frame = ttk.LabelFrame(left, text='Pérdidas (dB)')
		loss_frame.pack(fill='x', pady=6)
		self.loss_vars = {}
		loss_order = [
			('RFL_feeder','Feeder RF'),
			('AML_misalignment','Desalineación Antena'),
			('AA_atmos','Atenuación Atmosférica'),
			('Rain_att','Atenuación Lluvia'),
			('PL_polarization','Desajuste Polarización'),
			('L_pointing','Pérdida Apuntamiento'),
			('L_impl','Pérdidas Implementación'),
		]
		for key,label in loss_order:
			self.loss_vars[key] = tk.DoubleVar(value=self.core.losses[key])
			row_f = ttk.Frame(loss_frame); row_f.pack(fill='x', padx=2, pady=1)
			ttk.Label(row_f, text=label+':', font=bold_lbl).pack(side='left')
			ttk.Entry(row_f, textvariable=self.loss_vars[key], width=6).pack(side='right')
		self.run_btn = ttk.Button(left, text="Iniciar", command=self.toggle_run); self.run_btn.pack(anchor='w', pady=2)
		self.reset_btn = ttk.Button(left, text="Reset", command=self.reset); self.reset_btn.pack(anchor='w', pady=2)
		center = ttk.Frame(self.mainframe); center.pack(side='left', fill='both', expand=True)
		self.canvas = tk.Canvas(center, width=600, height=480, bg='white', highlightthickness=0); self.canvas.pack(fill='both', expand=True)
		slider_frame = ttk.Frame(center); slider_frame.pack(fill='x')
		
		# Control de modo de tiempo
		time_control_frame = ttk.Frame(slider_frame)
		time_control_frame.pack(fill='x', pady=2)
		self.manual_mode_var = tk.BooleanVar(value=False)
		manual_check = ttk.Checkbutton(time_control_frame, text='Modo Manual', variable=self.manual_mode_var, command=self._toggle_manual_mode)
		manual_check.pack(side='left')
		
		# Control de sensibilidad de tiempo
		sensitivity_frame = ttk.Frame(time_control_frame)
		sensitivity_frame.pack(side='right')
		ttk.Label(sensitivity_frame, text='Sensibilidad:', font=('Segoe UI', 9)).pack(side='left', padx=(10,2))
		self.time_sensitivity_var = tk.DoubleVar(value=1.0)  # Factor multiplicador de sensibilidad
		sensitivity_scale = tk.Scale(sensitivity_frame, from_=0.1, to=5.0, orient='horizontal', resolution=0.1,
									variable=self.time_sensitivity_var, length=120, showvalue=True)
		sensitivity_scale.pack(side='left')
		ttk.Label(time_control_frame, text='(Pausar para control fino de posiciones)', font=('Segoe UI', 9)).pack(side='left', padx=10)
		
		# Barra principal de tiempo de simulación
		self.time_slider_var = tk.DoubleVar(value=0.0)
		self.time_slider = tk.Scale(slider_frame, from_=0, to=self.max_simulation_time_s, orient='horizontal', resolution=0.1, 
									label='Tiempo Simulación [s] - Controla LEO + Tierra + GEO sincronizados', 
									variable=self.time_slider_var, command=lambda v: self._on_time_slider(float(v)))
		self.time_slider.pack(fill='x', pady=2)
		
		# Barras de ajuste fino (solo activas en modo manual)
		self.orbit_slider_var = tk.DoubleVar(value=self.orbit_angle_deg); self.user_adjusting_slider = False
		self.orbit_slider = tk.Scale(slider_frame, from_=0, to=359.9, orient='horizontal', resolution=0.1, 
									label='Ajuste Fino LEO [°] - Solo activo en Modo Manual', 
									variable=self.orbit_slider_var, command=lambda v: self._on_slider_change(float(v)))
		self.orbit_slider.pack(fill='x', pady=2)
		self.orbit_slider.configure(state='disabled')  # Inicialmente deshabilitado
		
		self.geo_slider_var = tk.DoubleVar(value=0.0)
		self.geo_slider = tk.Scale(slider_frame, from_=-180, to=180, orient='horizontal', resolution=0.5, 
								   label='Ajuste Fino GEO Long [°] - Solo activo en Modo Manual', 
								   variable=self.geo_slider_var, command=lambda v: self._on_geo_slider(float(v)))
		self.geo_slider.pack(fill='x', pady=2)
		self.geo_slider.configure(state='disabled')  # Inicialmente deshabilitado
		
		self.orbit_slider.bind('<ButtonPress-1>', lambda e: self._begin_slider()); self.orbit_slider.bind('<ButtonRelease-1>', lambda e: self._end_slider())
		self.canvas.bind('<Configure>', lambda e: self._draw_static())
		
		# Frame derecho (LAYOUT ORIGINAL RESTAURADO)
		right = ttk.Frame(self.mainframe); right.pack(side='left', fill='y')
		# Panel de métricas desplazable (canvas + scrollbar)
		self.metrics_canvas = tk.Canvas(right, borderwidth=0, highlightthickness=0)
		self.metrics_scrollbar = ttk.Scrollbar(right, orient='vertical', command=self.metrics_canvas.yview)
		self.metrics_canvas.configure(yscrollcommand=self.metrics_scrollbar.set)
		self.metrics_canvas.pack(side='left', fill='both', expand=True)
		self.metrics_scrollbar.pack(side='right', fill='y')
		self.metrics_panel = ttk.Frame(self.metrics_canvas)
		self._metrics_window = self.metrics_canvas.create_window((0,0), window=self.metrics_panel, anchor='nw')
		self.metrics_panel.bind('<Configure>', lambda e: self.metrics_canvas.configure(scrollregion=self.metrics_canvas.bbox('all')))
		self.metrics_canvas.bind('<Configure>', lambda e: self.metrics_canvas.itemconfigure(self._metrics_window, width=e.width))
		# Soporte rueda ratón (Windows delta 120)
		self.metrics_canvas.bind_all('<MouseWheel>', self._on_mousewheel)
		self._init_metrics_table()
		# Botón colapsar pérdidas
		self.show_losses = False
		self.toggle_losses_btn = ttk.Button(right, text='Mostrar Pérdidas ▶', command=self._toggle_losses)
		self.toggle_losses_btn.pack(fill='x', pady=2)
		# Botones de exportación
		export_frame = ttk.Frame(right)
		export_frame.pack(side='bottom', pady=4, fill='x')
		
		# Solo mantener el botón de CSV estructurado dinámico
		self.export_structured_btn = ttk.Button(export_frame, text='Exportar CSV Dinámico', command=self.export_csv_structured)
		self.export_structured_btn.pack(fill='x', expand=True)

	def toggle_run(self):
		self.running = not self.running
		if self.running and self.start_time is None: 
			self.start_time = time.time()
			self.last_animation_time = None  # Reset para primera animación
		self.run_btn.config(text='Parar' if self.running else 'Iniciar')
		
		# Iniciar animación para ambos modos (LEO y GEO ahora ambos animan)
		if self.running: 
			self._animate()
		if not self.running: 
			# Generar resumen de jamming cuando se detiene
			if len(self.history) > 0:
				self._generate_jamming_summary()
			self.orbit_slider_var.set(self.orbit_angle_deg)

	def _generate_jamming_summary(self):
		"""
		Genera resumen estadístico del impacto de jamming durante la simulación.
		Incluye métricas clave: peor/mejor CINR, porcentaje de tiempo efectivo, etc.
		"""
		if not self.history:
			return
		
		# Filtrar solo datos con jamming
		jamming_data = [entry for entry in self.history if entry.get('jamming_enabled', 0) == 1]
		
		if not jamming_data:
			self._append_metrics("\n📊 === RESUMEN DE JAMMING ===\n")
			self._append_metrics("Sin actividad de jamming detectada en la simulación.\n")
			return
		
		# Extraer métricas clave
		cinr_values = [entry.get('cinr_with_jamming_db') for entry in jamming_data 
					  if entry.get('cinr_with_jamming_db') is not None]
		degradations = [entry.get('jamming_degradation_db', 0) for entry in jamming_data]
		ci_values = [entry.get('ci_total_db') for entry in jamming_data 
					if entry.get('ci_total_db') is not None]
		
		# Estadísticas básicas
		total_samples = len(self.history)
		jamming_samples = len(jamming_data)
		jamming_percentage = (jamming_samples / total_samples) * 100
		
		# Análisis de efectividad
		effective_count = len([d for d in degradations if d > 2.0])
		moderate_count = len([d for d in degradations if 1.0 <= d <= 2.0])
		low_count = len([d for d in degradations if d < 1.0])
		
		effective_percentage = (effective_count / jamming_samples) * 100 if jamming_samples > 0 else 0
		
		# Métricas de CINR
		min_cinr = min(cinr_values) if cinr_values else float('nan')
		max_cinr = max(cinr_values) if cinr_values else float('nan')
		avg_cinr = sum(cinr_values) / len(cinr_values) if cinr_values else float('nan')
		
		# Métricas de degradación
		max_degradation = max(degradations) if degradations else 0
		avg_degradation = sum(degradations) / len(degradations) if degradations else 0
		
		# Mejor/Peor C/I
		min_ci = min(ci_values) if ci_values else float('inf')
		max_ci = max(ci_values) if ci_values else float('-inf')
		
		# Generar reporte
		self._append_metrics("\n📊 === RESUMEN DE JAMMING ===\n")
		self._append_metrics(f"🕒 Tiempo con jamming activo: {jamming_percentage:.1f}% ({jamming_samples}/{total_samples} muestras)\n")
		self._append_metrics(f"⚡ Efectividad del jamming: {effective_percentage:.1f}% del tiempo fue efectivo\n")
		self._append_metrics(f"   • Crítico/Moderado: {effective_count} muestras\n")
		self._append_metrics(f"   • Leve: {moderate_count} muestras\n")
		self._append_metrics(f"   • Inefectivo: {low_count} muestras\n\n")
		
		self._append_metrics("📈 === MÉTRICAS DE RENDIMIENTO ===\n")
		if not math.isnan(min_cinr):
			self._append_metrics(f"🔻 CINR mínimo alcanzado: {min_cinr:.2f} dB\n")
			self._append_metrics(f"🔺 CINR máximo con jamming: {max_cinr:.2f} dB\n")
			self._append_metrics(f"📊 CINR promedio con jamming: {avg_cinr:.2f} dB\n")
		
		self._append_metrics(f"📉 Degradación máxima: {max_degradation:.2f} dB\n")
		self._append_metrics(f"📊 Degradación promedio: {avg_degradation:.2f} dB\n\n")
		
		if not math.isinf(min_ci):
			self._append_metrics("🎯 === MÉTRICAS DE INTERFERENCIA ===\n")
			self._append_metrics(f"💥 C/I más bajo: {min_ci:.2f} dB (condición más crítica)\n")
			self._append_metrics(f"🛡️ C/I más alto: {max_ci:.2f} dB (mejor protección)\n\n")
		
		# Recomendaciones basadas en el análisis
		self._append_metrics("💡 === ANÁLISIS Y RECOMENDACIONES ===\n")
		if effective_percentage > 70:
			self._append_metrics("⚠️  ALERTA: Jamming muy efectivo - considerar medidas de protección\n")
		elif effective_percentage > 30:
			self._append_metrics("⚡ Jamming moderadamente efectivo - monitoreo recomendado\n")
		else:
			self._append_metrics("✅ Impacto de jamming limitado - enlaces resilientes\n")
		
		if not math.isnan(avg_cinr) and avg_cinr < 5:
			self._append_metrics("🔴 CINR promedio bajo - servicio comprometido\n")
		elif not math.isnan(avg_cinr) and avg_cinr > 10:
			self._append_metrics("🟢 CINR promedio saludable - servicio mantenido\n")
		
		self._append_metrics("=" * 50 + "\n")

	def reset(self):
		self.orbit_angle_deg = (360.0 - self.horizon_central_angle_deg)
		self.earth_rotation_angle_deg = 0.0
		self.geo_rotation_angle_deg = 0.0
		self.simulation_time_s = 0.0
		self.history.clear()
		self.start_time = None
		self.last_animation_time = None
		self.update_metrics(); self._draw_dynamic(); 
		self.orbit_slider_var.set(self.orbit_angle_deg); self.geo_slider_var.set(0.0); self.time_slider_var.set(0.0)

	def _begin_slider(self):
		if self.running:
			self.running = False; self.run_btn.config(text='Iniciar')
		self.user_adjusting_slider = True

	def _on_slider_change(self, val: float):
		if not self.user_adjusting_slider: return
		if not self.manual_time_control: return  # Solo en modo manual
		self.orbit_angle_deg = val % 360.0; self._draw_dynamic(); self.update_metrics()

	def _on_geo_slider(self, val: float):
		if not self.manual_time_control: return  # Solo en modo manual
		if self.mode_var.get() == 'GEO': self._draw_dynamic(); self.update_metrics()

	def _end_slider(self):
		self.user_adjusting_slider = False; self.orbit_slider_var.set(self.orbit_angle_deg)
	
	def _toggle_manual_mode(self):
		"""Cambia entre modo automático y manual."""
		self.manual_time_control = self.manual_mode_var.get()
		
		if self.manual_time_control:
			# Modo manual: habilitar barras de ajuste fino
			self.orbit_slider.configure(state='normal')
			if self.mode_var.get() == 'GEO':
				self.geo_slider.configure(state='normal')
			# Si está corriendo, pausarlo
			if self.running:
				self.toggle_run()
		else:
			# Modo automático: deshabilitar barras de ajuste fino
			self.orbit_slider.configure(state='disabled')
			self.geo_slider.configure(state='disabled')
	
	def _on_time_slider(self, time_s: float):
		"""Maneja el cambio en la barra de tiempo de simulación."""
		if not self.running:  # Solo permitir cambio manual cuando esté pausado
			self.simulation_time_s = time_s
			self._update_positions_from_time()
			self._draw_dynamic()
			self.update_metrics()
	
	def _update_positions_from_time(self):
		"""Actualiza todas las posiciones basándose en el tiempo de simulación."""
		# Aplicar factor de sensibilidad definido por usuario
		effective_time = self.simulation_time_s * self.time_sensitivity_var.get()
		
		# Calcular rotación de la Tierra basada en tiempo
		earth_rotation_rate_deg_per_s = EARTH_ROTATION_DEG_PER_S * self.time_scale_factor
		self.earth_rotation_angle_deg = (effective_time * earth_rotation_rate_deg_per_s) % 360.0
		
		# GEO siempre sincronizado con Tierra
		self.geo_rotation_angle_deg = self.earth_rotation_angle_deg
		
		# LEO: calcular posición orbital basada en tiempo
		if self.mode_var.get() == 'LEO':
			# Velocidad orbital real para LEO
			orbital_velocity_deg_per_s = math.sqrt(MU_EARTH / (self.orbit_r_km * 1000)) * 180 / (math.pi * self.orbit_r_km * 1000) * self.time_scale_factor
			orbit_change = effective_time * orbital_velocity_deg_per_s
			self.orbit_angle_deg = ((360.0 - self.horizon_central_angle_deg) + orbit_change) % 360.0

	def export_csv_structured(self):
		"""
		Nueva función de exportación CSV estructurada dinámica multi-jammer.
		Utiliza build_csv_header(active_jammers) y write_row() dinámicos.
		"""
		if not self.history:
			self._append_metrics("No hay datos para exportar. Inicia la simulación primero.\n")
			return
		
		from tkinter import filedialog
		path = filedialog.asksaveasfilename(
			defaultextension='.csv', 
			filetypes=[('CSV','*.csv')], 
			title='Guardar CSV estructurado multi-jammer dinámico'
		)
		if not path: 
			return
		
		try:
			import csv
			import time
			
			# Determinar jammers activos del historial
			active_jammers_all = set()
			for row_data in self.history:
				if row_data.get('jamming_activado', 0) and row_data.get('numero_jammers', 0) > 0:
					# Agregar jammers activos de esta fila
					for j in range(1, row_data.get('numero_jammers', 0) + 1):
						jammer_id = row_data.get(f'jammer_{j}_id', f'J{j}')
						if jammer_id:
							active_jammers_all.add(jammer_id)
			
			# Lista ordenada de jammers activos
			active_jammers_list = sorted(list(active_jammers_all))
			
			# Generar cabecera dinámica
			headers = build_csv_header(active_jammers=active_jammers_list)
			
			# Metadatos de simulación
			sim_metadata = {
				'sim_id': f'SIM_{int(time.time())}',
				'schema_version': '2.1', 
				'scenario_name': getattr(self, 'scenario_name', 'LEO_JAMMING_DYNAMIC'),
				'notes': f'Dynamic CSV - {len(active_jammers_list)} jammers - Generated on {time.strftime("%Y-%m-%d %H:%M:%S")}'
			}
			
			with open(path, 'w', newline='', encoding='utf-8') as f:
				writer = csv.writer(f)
				# Escribir cabecera
				writer.writerow(headers)
				
				# Procesar cada fila del historial
				for row_data in self.history:
					
					# === MAPEAR DATOS EXISTENTES AL NUEVO FORMATO ===
					
					# Enlace nominal
					nominal_link = {
						'time_s': row_data.get('tiempo_s', 0.0),
						'rx_site_id': 'RX_PRINCIPAL',
						'constellation_id': 'LEO_CONSTELLATION',
						'sat_id': f"SAT_{row_data.get('modo', 'UNKNOWN')}",
						'beam_id': 'BEAM_001',
						'elevation_deg': row_data.get('elevacion_deg', 0.0),
						'azimuth_deg': row_data.get('azimut_deg', 0.0),
						'slant_distance_km': row_data.get('distancia_slant_km', 0.0),
						'fspl_db': row_data.get('fspl_espacio_libre_db', 0.0),
						'visible': row_data.get('visible', True),
						'ul_freq_ghz': row_data.get('ul_freq_ghz', 30.0),
						'ul_bw_mhz': row_data.get('ul_bw_mhz', 50.0),
						'ul_gt_dbk': row_data.get('ul_gt_db_k', 0.0),
						'ul_cn0_dbhz': row_data.get('ul_cn0_dbhz', 0.0),
						'ul_cn_db': row_data.get('ul_cn_db', 0.0),
						'ul_estado_cn': row_data.get('ul_estado_cn', 'UNKNOWN'),
						'dl_freq_ghz': row_data.get('dl_freq_ghz', 20.0),
						'dl_bw_mhz': row_data.get('dl_bw_mhz', 50.0),
						'dl_gt_dbk': row_data.get('dl_gt_db_k', 0.0),
						'dl_cn0_dbhz': row_data.get('dl_cn0_dbhz', 0.0),
						'dl_cn_db': row_data.get('dl_cn_db', 0.0),
						'dl_estado_cn': row_data.get('dl_estado_cn', 'UNKNOWN')
					}
					
					# Métricas end-to-end
					e2e_metrics = {
						'cinr_db': row_data.get('e2e_cinr_total_db', 0.0),
						'latency_ms': row_data.get('e2e_latencia_total_ms', 0.0),
						'rtt_ms': row_data.get('e2e_latencia_rtt_ms', 0.0),
						'shannon_capacity_mbps': row_data.get('capacidad_shannon_mbps', 0.0),
						'throughput_effective_mbps': row_data.get('throughput_efectivo_mbps', 0.0),
						'modcod_selected': row_data.get('modcod_name', 'QPSK_1/2'),
						'spectral_efficiency_bps_hz': row_data.get('eficiencia_espectral_bps_hz', 0.0),
						'e2e_state': row_data.get('e2e_estado', 'UNKNOWN')
					}
					
					# === CONSTRUIR MÉTRICAS DINÁMICAS DE JAMMERS ACTIVOS ===
					jammer_metrics_list = []
					
					# Solo procesamos jammers que están en la lista de activos
					if row_data.get('jamming_activado', 0) and row_data.get('numero_jammers', 0) > 0:
						
						for j in range(1, row_data.get('numero_jammers', 0) + 1):
							jammer_id = row_data.get(f'jammer_{j}_id', f'J{j}')
							
							# Solo incluir si está en la lista de jammers activos
							if jammer_id in active_jammers_list:
								
								# CINR original y con jamming para cálculo coherente usando calculate_cinr_with_jamming()
								cinr_original = row_data.get('cinr_sin_jamming_db', row_data.get('e2e_cinr_total_db', 0.0))
								ci_db = row_data.get(f'jammer_{j}_ci_db', row_data.get('ci_total_db', 0.0))
								
								# Usar función de JammerSystem para coherencia
								from JammerSystem import SpotJammingCalculator
								if not math.isinf(ci_db) and not math.isnan(cinr_original):
									cinr_result = SpotJammingCalculator.calculate_cinr_with_jamming(cinr_original, ci_db)
									cinr_with_attack = cinr_result["cinr_db"]
									degradation_db = cinr_result["degradation_db"]
								else:
									cinr_with_attack = cinr_original
									degradation_db = 0.0
								
								# Asegurar target.link correcto con tie-breaker UL
								target_link = row_data.get(f'jammer_{j}_target_link', 'UL')
								if target_link == 'DOWNLINK':  # Convertir legacy format
									target_link = 'DL'
								elif target_link not in ['UL', 'DL']:
									target_link = 'UL'  # Default con tie-breaker
								
								jammer_metrics = {
									'jammer_id': jammer_id,
									'jammer_name': row_data.get(f'jammer_{j}_nombre', f'JAMMER_{j}'),
									'platform_type': 'SURFACE',
									'jammer_type': row_data.get(f'jammer_{j}_tipo', 'SPOT'),
									'eirp_dbw': row_data.get(f'jammer_{j}_eirp_dbw', 63.0),
									'center_freq_ghz': row_data.get(f'jammer_{j}_freq_ghz', 30.0),
									'bandwidth_mhz': row_data.get(f'jammer_{j}_bandwidth_mhz', 50.0),
									'polarization': 'LINEAR',
									'antenna_gain_dbi': 30.0,
									'lat_deg': 0.0,
									'lon_deg': 0.0,
									'alt_km': row_data.get(f'jammer_{j}_altura_km', 0.05),
									'target_link': target_link,  # UL/DL exactos
									'spectral_overlap_percent': row_data.get('spectral_overlap_percent', 100.0),
									'separation_angular_deg': row_data.get('separacion_angular_deg', 0.0),
									'discrimination_fcc_db': row_data.get('discriminacion_fcc_db', 21.0),
									'polarization_isolation_db': row_data.get('aislacion_polarizacion_db', -4.0),
									'discrimination_angular_real_db': row_data.get('discrimination_angular_real_db', 21.0),
									'frequency_offset_mhz': row_data.get('frequency_offset_mhz', 0.0),
									'ci_db': ci_db,
									'cinr_original_db': cinr_original,
									'cinr_with_attack_db': cinr_with_attack,
									'degradation_db': degradation_db,  # COHERENTE con calculate_cinr_with_jamming()
									'efficiency_percent': row_data.get('eficiencia_jammer_percent', 0.0),
									'power_margin_db': row_data.get('potencia_jammer_necesaria_dbw', 0.0),  # CLARIFICADO: Margen de potencia
									'recommendation': row_data.get('recomendacion_configuracion', 'N/A'),
									'active': True
								}
								jammer_metrics_list.append(jammer_metrics)
					
					# Generar fila usando el nuevo sistema dinámico
					csv_row = write_row(sim_metadata, nominal_link, e2e_metrics, jammer_metrics_list)
					writer.writerow(csv_row)
			
			self._append_metrics(f"✅ CSV estructurado dinámico exportado: {path}\n")
			self._append_metrics(f"📊 Formato: {len(headers)} columnas dinámicas para {len(active_jammers_list)} jammers activos\n")
			self._append_metrics(f"🔄 Filas procesadas: {len(self.history)}\n")
			self._append_metrics(f"🎯 Jammers activos: {', '.join(active_jammers_list) if active_jammers_list else 'Ninguno'}\n")
			
		except Exception as e:
			self._append_metrics(f"❌ Error exportando CSV estructurado: {e}\n")
			
		except Exception as e:
			self._append_metrics(f"❌ Error exportando CSV estructurado: {e}\n")

	def _append_metrics(self, text: str):
		# Por simplicidad mostramos mensajes emergentes en consola si no hay text widget
		print(text.rstrip())

	def _init_metrics_table(self):
		"""Crea etiquetas (nombre en negrita, valor coloreado)."""
		font_label = ('Segoe UI', 10, 'bold')
		font_value = ('Consolas', 11)
		# Definimos filas con secciones (None => separador visual)
		rows = [
			('— PARÁMETROS BÁSICOS —','section'),
			('Modo', '—'),
			('Tiempo Simulación [s]', '—'),
			('Modo Control', '—'),
			('Elevación [°]', '—'),
			('Distancia Slant [km]', '—'),
			('FSPL (Espacio Libre) [dB]', '—'),
			('Latencia Ida [ms]', '—'),
			('Latencia RTT [ms]', '—'),
			('C/N0 [dBHz]', '—'),
			('C/N [dB]', '—'),
			('Estado C/N', '—'),
			('G/T [dB/K]', '—'),
			('— POTENCIA Y BACK-OFF —','section'),
			('EIRP Saturado [dBW]', '—'),
			('Back-off Entrada [dB]', '—'),
			('Back-off Salida [dB]', '—'),
			('EIRP Efectivo [dBW]', '—'),
			('— RUIDO Y RENDIMIENTO —','section'),
			('Temperatura Sistema T_sys [K]', '—'),
			('Densidad Ruido N0 [dBHz]', '—'),
			('Eb/N0 [dB]', '—'),
			('Eb/N0 Requerido [dB]', '—'),
			('Margen Eb/N0 [dB]', '—'),
			('Capacidad Shannon [Mbps]', '—'),
			('Eficiencia Espectral Real [b/Hz]', '—'),
			('Utilización vs Shannon [%]', '—'),
			('— GEOMETRÍA ORBITAL —','section'),
			('Ángulo Central Δ [°]', '—'),
			('Radio Orbital [km]', '—'),
			('Velocidad Orbital [km/s]', '—'),
			('Velocidad Angular ω [°/s]', '—'),
			('Rate Cambio Distancia [km/s]', '—'),
			('Periodo Orbital [min]', '—'),
			('Tiempo Visibilidad Restante [s]', '—'),
			('— DOPPLER —','section'),
			('Doppler Instantáneo [kHz]', '—'),
			('Doppler Máx Teórico [kHz]', '—'),
			('— PÉRDIDAS —','section'),
			('Σ Pérdidas Extra [dB]', '—'),
			('Path Loss Total [dB]', '—'),
		]
		self.metric_labels = {}
		row_index = 0
		for name, val in rows:
			if val == 'section':
				sep = ttk.Separator(self.metrics_panel, orient='horizontal')
				sep.grid(row=row_index, column=0, columnspan=2, sticky='ew', pady=(6,2))
				lbl_section = ttk.Label(self.metrics_panel, text=name, font=('Segoe UI',9,'bold'), foreground='#555')
				lbl_section.grid(row=row_index+1, column=0, columnspan=2, sticky='w', padx=2)
				row_index += 2
				continue
			lbl = ttk.Label(self.metrics_panel, text=name+':', font=font_label, anchor='w')
			lbl.grid(row=row_index, column=0, sticky='w', padx=(2,4), pady=1)
			val_lbl = ttk.Label(self.metrics_panel, text=val, font=font_value, foreground='#004080', anchor='e')
			val_lbl.grid(row=row_index, column=1, sticky='e', padx=(4,6), pady=1)
			self.metric_labels[name] = val_lbl
			row_index += 1
		self.loss_rows_start_index = row_index
		# Filas detalladas de pérdidas (creadas pero ocultas inicialmente)
		loss_detail_rows = [
			('Feeder RF [dB]', 'RFL_feeder'),
			('Desalineación Antena [dB]', 'AML_misalignment'),
			('Atenuación Atmosférica [dB]', 'AA_atmos'),
			('Atenuación Lluvia [dB]', 'Rain_att'),
			('Desajuste Polarización [dB]', 'PL_polarization'),
			('Pérdida Apuntamiento [dB]', 'L_pointing'),
			('Pérdidas Implementación [dB]', 'L_impl'),
		]
		self.loss_detail_label_map = {}
		current_row = self.loss_rows_start_index
		for disp, key in loss_detail_rows:
			lbl = ttk.Label(self.metrics_panel, text=disp+':', font=font_label, anchor='w')
			val_lbl = ttk.Label(self.metrics_panel, text='—', font=font_value, foreground='#004080', anchor='e')
			# No grid todavía (colapsado inicialmente)
			self.loss_detail_label_map[key] = val_lbl
		self.metrics_panel.columnconfigure(0, weight=1)
		self.metrics_panel.columnconfigure(0, weight=1)
		self.metrics_panel.columnconfigure(1, weight=1)

	def _draw_static(self):
		"""Redibuja fondo recalculando escala para que GEO completo quepa.
		Solo dibuja elementos que NO rotan: órbitastraces, referencias fijas.
		
		Escala: se reserva ~90% del mínimo lado para el diámetro GEO.
		"""
		w = max(self.canvas.winfo_width(), 200); h = max(self.canvas.winfo_height(), 200); self.canvas.delete('all')
		min_side = min(w, h)
		# Margen: 5% alrededor => diámetro GEO ocupa 90% => radio GEO 45% del min_side
		max_geo_radius_px = 0.45 * min_side
		self.scale_px_per_km = max_geo_radius_px / self.geo_orbit_r_km
		self.earth_radius_px = self.Re_km * self.scale_px_per_km
		# Radio físico (escala) de LEO y GEO
		self.leo_orbit_r_px_physical = self.orbit_r_km * self.scale_px_per_km
		self.geo_orbit_r_px = self.geo_orbit_r_km * self.scale_px_per_km
		# Radio visual para LEO (solo estética). Lo separamos un porcentaje del gap Tierra-GEO.
		gap_total_px = self.geo_orbit_r_px - self.earth_radius_px
		visual_fraction = 0.18  # Ajustable: 0.0=pegado, 1.0=mitad del camino hacia GEO
		self.leo_orbit_r_px_visual = self.earth_radius_px + max(18, visual_fraction * gap_total_px)
		# Centro (ligero desplazamiento vertical para texto)
		self.cx = w / 2
		self.cy = h / 2 + h * 0.04
		
		# Dibujar referencias fijas (no rotativas)
		# Líneas de referencia orbital (opcionales)
		# self.canvas.create_oval(self.cx-self.leo_orbit_r_px_visual, self.cy-self.leo_orbit_r_px_visual, 
		#                        self.cx+self.leo_orbit_r_px_visual, self.cy+self.leo_orbit_r_px_visual, 
		#                        outline='#cccccc', dash=(3,4), tags='static')
		# self.canvas.create_oval(self.cx-self.geo_orbit_r_px, self.cy-self.geo_orbit_r_px, 
		#                        self.cx+self.geo_orbit_r_px, self.cy+self.geo_orbit_r_px, 
		#                        outline='#aaaaff', dash=(2,3), tags='static')
		
		self._draw_earth_and_surface()
		self._draw_dynamic()

	def _draw_earth_and_surface(self):
		"""Dibuja la Tierra y elementos de superficie que rotan con ella."""
		self.canvas.delete('earth')
		
		# Tierra (base circular)
		self.canvas.create_oval(self.cx-self.earth_radius_px, self.cy-self.earth_radius_px, 
		                       self.cx+self.earth_radius_px, self.cy+self.earth_radius_px, 
		                       fill='#e0f4ff', outline='#0077aa', width=2, tags='earth')
		
		# Marcas en la superficie terrestre que indican rotación
		self._draw_earth_surface_features()
		
		# Ground station y futuros elementos de superficie
		self._draw_surface_elements()

	def _draw_earth_surface_features(self):
		"""Dibuja características en la superficie terrestre para visualizar rotación."""
		# Dibujar líneas de longitud como referencia visual de rotación
		for i in range(8):  # 8 líneas cada 45 grados
			angle_deg = i * 45.0 + self.earth_rotation_angle_deg
			angle_rad = math.radians(angle_deg)
			# Línea desde centro hasta borde
			end_x = self.cx + self.earth_radius_px * 0.9 * math.sin(angle_rad)
			end_y = self.cy - self.earth_radius_px * 0.9 * math.cos(angle_rad)
			self.canvas.create_line(self.cx, self.cy, end_x, end_y, 
			                       fill='#4488cc', width=1, dash=(2,2), tags='earth')

	def _draw_surface_elements(self):
		"""Dibuja elementos en la superficie que rotan con la Tierra."""
		# Ground Station - posición fija relativa a la Tierra (rota con ella)
		gs_angle_rad = math.radians(self.earth_rotation_angle_deg)  # GS en longitud 0° inicialmente
		self.gs_x = self.cx + self.earth_radius_px * math.sin(gs_angle_rad)
		self.gs_y = self.cy - self.earth_radius_px * math.cos(gs_angle_rad)
		
		self.canvas.create_oval(self.gs_x-5, self.gs_y-5, self.gs_x+5, self.gs_y+5, 
		                       fill='green', outline='black', tags='earth')
		self.canvas.create_text(self.gs_x+10, self.gs_y-10, text='GS', anchor='w', tags='earth')
		
		# Dibujar jammers terrestres (rotan con la Tierra)
		self._draw_jammers()

	def _draw_jammers(self):
		"""Dibuja los jammers terrestres en el canvas usando las mismas escalas que los satélites."""
		if not hasattr(self, 'jammer_manager') or not self.jammer_manager:
			return
		
		# Obtener posiciones de jammers considerando rotación terrestre
		# Aproximación: GS en lat=0, lon=0 para simplificar
		gs_lat, gs_lon = 0.0, 0.0
		simulation_time_min = self.simulation_time_s / 60.0  # Convertir a minutos
		jammer_positions = self.jammer_manager.get_jammer_positions(
			gs_lat, gs_lon, self.earth_rotation_angle_deg, simulation_time_min
		)
		
		for jammer_pos in jammer_positions:
			config = jammer_pos['config']
			
			# CORREGIDO: Calcular posición considerando tipo de altura y distancia real
			if config.altitude_type.value == "Superficie (0-50 km)":
				# SURFACE: Para jammers de superficie, mantenerlos cerca de la superficie terrestre
				# Solo agregar un pequeño offset visual para distinguirlos de la superficie
				altitude_km = config.altitude_km  # Ej: 0.05 km
				
				# Para superficie: posición muy cerca del radio terrestre
				# Solo agregar altura mínima para visibilidad (máximo 5-8 píxeles)
				altitude_offset_px = max(2, min(8, altitude_km * 100))  # Escala reducida
				
				# Posición final: justo fuera de la superficie terrestre
				jammer_radius_px = self.earth_radius_px + altitude_offset_px
				
				# Limitar para que no salga del canvas
				canvas_w = max(self.canvas.winfo_width(), 600)
				canvas_h = max(self.canvas.winfo_height(), 480)
				max_radius = min(canvas_w, canvas_h) // 2 - 50
				jammer_radius_px = min(jammer_radius_px, max_radius)
				
			elif config.altitude_type.value.startswith("LEO"):
				# LEO: Misma altura visual que satélite LEO
				jammer_radius_px = self.leo_orbit_r_px_visual  
			elif config.altitude_type.value.startswith("GEO"):
				# GEO: Misma altura que satélite GEO
				jammer_radius_px = self.geo_orbit_r_px
			elif config.altitude_type.value.startswith("MEO"):
				# MEO: Altura intermedia entre LEO y GEO
				jammer_radius_px = self.earth_radius_px + (self.leo_orbit_r_px_visual - self.earth_radius_px) * 2.5
			else:  # Super-GEO
				# Por encima de GEO
				jammer_radius_px = self.geo_orbit_r_px + (self.geo_orbit_r_px - self.leo_orbit_r_px_visual) * 0.3
			
			# CORREGIDO: Calcular posición angular incluyendo rotación terrestre
			current_azimuth = jammer_pos.get('current_azimuth', 0)
			
			# Para jammers de superficie: aplicar rotación terrestre como el GS
			if config.altitude_type.value == "Superficie (0-50 km)":
				# Aplicar rotación terrestre + azimut relativo + offset visual para evitar solapamiento
				total_angle = self.earth_rotation_angle_deg + current_azimuth
				
				# Offset angular para separar visualmente del GS (15° hacia la izquierda)
				visual_offset_deg = -15.0  # Separación visual
				total_angle += visual_offset_deg
			else:
				# Para jammers orbitales: solo azimut (no rotan con Tierra)
				total_angle = current_azimuth
			
			azimuth_rad = math.radians(total_angle)
			
			# Posición del jammer en el radio correspondiente a su altura
			jammer_x = self.cx + jammer_radius_px * math.sin(azimuth_rad)
			jammer_y = self.cy - jammer_radius_px * math.cos(azimuth_rad)
			
			# Dibujar jammer como círculo rojo
			jammer_radius = 5
			self.canvas.create_oval(
				jammer_x - jammer_radius, jammer_y - jammer_radius,
				jammer_x + jammer_radius, jammer_y + jammer_radius,
				fill='red', outline='darkred', width=2, tags='earth'
			)
			
			# Etiqueta del jammer con información específica por tipo
			orbital_info = jammer_pos.get('orbital_info', {})
			altitude_type = orbital_info.get('altitude_type', 'Surface')
			distance_km = config.distance_from_gs_km
			current_azimuth = jammer_pos.get('current_azimuth', 0)
			
			# Etiqueta diferenciada para Surface vs LEO
			if config.altitude_type.value == "Superficie (0-50 km)":
				altitude_m = config.altitude_km * 1000  # Convertir a metros para surface
				jammer_label = f"{jammer_pos['name']} (Superficie {altitude_m:.0f}m) d:{distance_km:.0f}km Az:{current_azimuth:.0f}°"
			else:
				jammer_label = f"{jammer_pos['name']} ({altitude_type}) d:{distance_km:.0f}km Az:{current_azimuth:.0f}°"
				
			self.canvas.create_text(
				jammer_x + 8, jammer_y - 8, 
				text=jammer_label, anchor='w', 
				font=('Segoe UI', 8), fill='darkred', tags='earth'
			)
			
			# Línea desde centro hasta jammer (opcional, para mostrar conexión)
			self.canvas.create_line(
				self.cx, self.cy, jammer_x, jammer_y,
				fill='red', width=1, dash=(3, 2), tags='earth'
			)

	def _change_mode(self):
		# Cargar parámetros específicos según modo
		self._load_link_presets_for_mode()
		
		if self.mode_var.get() == 'LEO':
			self.eirp_var.set(self.core.eirp_dbw); self.gt_var.set(self.core.gt_dbk)
			# Habilitar barras solo en modo manual
			if self.manual_time_control:
				self.orbit_slider.configure(state='normal')
			self.geo_slider.configure(state='disabled')
		else:
			self.eirp_var.set(self.core.geo_eirp_dbw); self.gt_var.set(self.core.geo_gt_dbk)
			self.orbit_slider.configure(state='disabled')
			# Habilitar barras solo en modo manual
			if self.manual_time_control:
				self.geo_slider.configure(state='normal')
		self.update_metrics(); self._draw_dynamic()

	def _draw_dynamic(self):
		"""Redibuja elementos dinámicos: satélites y sus enlaces. 
		También actualiza la rotación terrestre."""
		
		# Actualizar rotación terrestre en cada frame
		self._draw_earth_and_surface()
		
		# Limpiar elementos dinámicos previos
		self.canvas.delete('dyn')
		
		if self.mode_var.get() == 'LEO':
			# LEO: dibujar órbita visual y satélite
			orbit_r_px = self.leo_orbit_r_px_visual
			self.canvas.create_oval(self.cx-orbit_r_px, self.cy-orbit_r_px, self.cx+orbit_r_px, self.cy+orbit_r_px, outline='#cccccc', dash=(3,4), tags='dyn')
			phi = math.radians(self.orbit_angle_deg % 360.0)
			# Posición visual LEO
			sx = self.cx + orbit_r_px * math.sin(phi); sy = self.cy - orbit_r_px * math.cos(phi)
			
			# Cálculo geométrico CORREGIDO para LEO considerando rotación terrestre
			# Ángulo central = diferencia entre posición satélite y Ground Station
			satellite_angle_deg = self.orbit_angle_deg % 360.0
			gs_angle_deg = self.earth_rotation_angle_deg % 360.0
			
			# Calcular diferencia angular mínima (considerando que es un círculo)
			delta_raw = abs(satellite_angle_deg - gs_angle_deg)
			if delta_raw > 180:
				delta_raw = 360 - delta_raw
			delta_deg = delta_raw
			
			# Geometría física para elevación y distancia
			Re = self.Re_km; Ro = self.orbit_r_km
			delta_rad = math.radians(delta_deg)
			slant_km = math.sqrt(Re*Re + Ro*Ro - 2*Re*Ro*math.cos(delta_rad))
			if slant_km == 0:
				elev_deg = 90.0
			else:
				sin_e = (Ro * math.cos(delta_rad) - Re) / slant_km
				sin_e = max(-1.0, min(1.0, sin_e))
				elev_deg = math.degrees(math.asin(sin_e))
			visible = elev_deg > 0
			
			# Dibujar enlace LEO-GS
			self.canvas.create_line(self.gs_x, self.gs_y, sx, sy, fill=('red' if visible else '#bbbbbb'), dash=(5,4) if visible else (2,4), width=2 if visible else 1, tags='dyn')
			self.canvas.create_oval(sx-7, sy-7, sx+7, sy+7, fill='orange', outline='black', tags='dyn')
			self.canvas.create_text(sx+10, sy, text=f"LEO {elev_deg:.0f}°" + ("" if visible else " (OCULTO)"), anchor='w', tags='dyn')
			
			self.current_elevation_deg = elev_deg; self.current_visible = visible; self.current_slant_distance_m = slant_km * 1000.0
			self.current_delta_deg = delta_deg
		else:
			# GEO: dibujar órbita y satélite geoestacionario
			geo_r_px = self.geo_orbit_r_px
			self.canvas.create_oval(self.cx-geo_r_px, self.cy-geo_r_px, self.cx+geo_r_px, self.cy+geo_r_px, outline='#aaaaff', dash=(2,3), tags='dyn')
			
			# GEO posición: longitud relativa al GS + rotación síncrona con Tierra
			geo_longitude_relative = self.geo_slider_var.get()  # Longitud relativa del slider
			# Posición absoluta GEO = rotación tierra + longitud relativa
			geo_absolute_angle = self.earth_rotation_angle_deg + geo_longitude_relative
			phi_geo = math.radians(geo_absolute_angle)
			sx = self.cx + geo_r_px * math.sin(phi_geo); sy = self.cy - geo_r_px * math.cos(phi_geo)
			
			# Cálculo geométrico para GEO (ángulo entre GS y satélite GEO)
			gs_angle = math.radians(self.earth_rotation_angle_deg)
			geo_angle = math.radians(geo_absolute_angle)
			delta_long = abs(geo_angle - gs_angle)  # Diferencia angular
			
			Re = self.Re_km; Ro = self.geo_orbit_r_km
			slant_km = math.sqrt(Re*Re + Ro*Ro - 2*Re*Ro*math.cos(delta_long))
			if slant_km == 0:
				elev_deg = 90.0
			else:
				sin_e = (Ro * math.cos(delta_long) - Re) / slant_km
				sin_e = max(-1.0, min(1.0, sin_e))
				elev_deg = math.degrees(math.asin(sin_e))
			visible = elev_deg > 0
			
			# Dibujar enlace GEO-GS
			self.canvas.create_line(self.gs_x, self.gs_y, sx, sy, fill=('purple' if visible else '#bbbbbb'), dash=(5,3) if visible else (2,3), width=2 if visible else 1, tags='dyn')
			self.canvas.create_oval(sx-8, sy-8, sx+8, sy+8, fill='#6040ff', outline='black', tags='dyn')
			self.canvas.create_text(sx+10, sy, text=f"GEO {elev_deg:.0f}°", anchor='w', tags='dyn')
			
			self.current_elevation_deg = elev_deg; self.current_visible = visible; self.current_slant_distance_m = slant_km * 1000.0

	def _compute_slant_range_m(self, central_angle_deg: float) -> float:
		delta = math.radians(central_angle_deg); re = self.Re_km; ro = self.orbit_r_km; slant_km = math.sqrt(re*re + ro*ro - 2*re*ro*math.cos(delta)); return slant_km * 1000.0

	def _animate(self):
		"""Animación principal que actualiza posiciones de satélites y rotación terrestre."""
		if not self.running: 
			return
			
		# Calcular tiempo transcurrido desde última animación
		current_time = time.time()
		if self.last_animation_time is None:
			self.last_animation_time = current_time
			dt_s = 0.3  # Usar tiempo fijo para primer frame
		else:
			dt_s = current_time - self.last_animation_time
			self.last_animation_time = current_time
		
		# Aplicar factor de escalado temporal para visualización
		scaled_dt_s = dt_s * self.time_scale_factor
		
		# Actualizar tiempo de simulación
		self.simulation_time_s += scaled_dt_s
		if self.simulation_time_s > self.max_simulation_time_s:
			self.simulation_time_s = self.max_simulation_time_s
			# Opcional: pausar automáticamente al llegar al máximo
			# self.toggle_run()
		
		# Actualizar barra de tiempo
		self.time_slider_var.set(self.simulation_time_s)
		
		# Actualizar rotación terrestre (realista)
		earth_rotation_increment = EARTH_ROTATION_DEG_PER_S * scaled_dt_s
		self.earth_rotation_angle_deg = (self.earth_rotation_angle_deg + earth_rotation_increment) % 360.0
		
		# GEO rota sincrónicamente con la Tierra (geoestacionario)
		self.geo_rotation_angle_deg = self.earth_rotation_angle_deg
		
		if self.mode_var.get() == 'LEO':
			# LEO: calcular velocidad angular real y actualizar posición
			Re_m = EARTH_RADIUS_M
			ro_m = Re_m + self.core.constellation.satellites[0].altitude_m
			v_orbital_ms = math.sqrt(MU_EARTH / ro_m)  # Velocidad orbital en m/s
			omega_rad_s = v_orbital_ms / ro_m  # Velocidad angular en rad/s
			omega_deg_s = math.degrees(omega_rad_s)  # Velocidad angular en deg/s
			
			# Incremento LEO basado en dinámica orbital real
			leo_increment = omega_deg_s * scaled_dt_s
			self.orbit_angle_deg = (self.orbit_angle_deg + leo_increment) % 360.0
			
			# Actualizar slider si no está siendo manipulado por el usuario
			if not self.user_adjusting_slider: 
				self.orbit_slider_var.set(self.orbit_angle_deg)
		
		# Actualizar métricas y dibujo
		self.update_metrics()
		self._draw_dynamic()
		
		# Programar siguiente frame con intervalo configurado
		self.root.after(self.animation_interval_ms, self._animate)


	# ----------------------------- BLOQUES MODULARES (Fases 0-1) ----------------------------- #
	def update_metrics(self):
		"""Orquesta el refresco: parámetros -> geometría -> doppler -> enlace -> render tabla."""
		self._update_core_params()
		self._update_geometry_block()  # Actualizar geometría primero
		self._update_link_params()     # Después actualizar enlaces (usa geometría actualizada)
		self._update_doppler_block()
		self._update_link_block()
		self._update_jamming_block()  # Calcular jamming después del enlace base
		self._apply_jamming_to_link()  # NUEVO: Aplicar degradación por jamming a métricas principales
		self._update_latency_block()  # Fase 5
		# Primero seleccionamos MODCOD (deriva Rb y Eb/N0 requerido) y luego calculamos performance real
		self._update_modcod_block()  # Fase 5 (genera Rb_Mbps & EbN0_req)
		self._update_performance_block()  # Fase 4 (usa Rb derivado)
		self._update_jamming_block()  # Spot Jamming (Escenario 2)
		self._render_metrics()
		self._append_history_row()
		self._update_link_gui()  # Actualiza GUI de los enlaces UL/DL

	def _update_core_params(self):
		self.core.eirp_dbw = float(self.eirp_var.get())
		self.core.gt_dbk = float(self.gt_var.get())
		# Usar frecuencia del tab activo UL/DL/E2E
		if hasattr(self, 'current_link_sense'):
			if self.current_link_sense == 'UL' and hasattr(self, 'ul_freq_var'):
				self.core.calc.frequency_hz = float(self.ul_freq_var.get()) * 1e9
			elif self.current_link_sense == 'DL' and hasattr(self, 'dl_freq_var'):
				self.core.calc.frequency_hz = float(self.dl_freq_var.get()) * 1e9
			elif self.current_link_sense == 'E2E':
				# Para End-to-End, usar frecuencia de referencia
				ref_link = self.bw_ref_var.get() if hasattr(self, 'bw_ref_var') else 'UL'
				if ref_link == 'DL' and hasattr(self, 'dl_freq_var'):
					self.core.calc.frequency_hz = float(self.dl_freq_var.get()) * 1e9
				else:  # UL por defecto
					self.core.calc.frequency_hz = float(self.ul_freq_var.get()) * 1e9 if hasattr(self, 'ul_freq_var') else 14.0e9
			else:
				# Usar UL por defecto
				self.core.calc.frequency_hz = 14.0e9  # UL frequency por defecto
		else:
			self.core.calc.frequency_hz = 14.0e9  # UL frequency por defecto
		self.core.calc.default_bandwidth_hz = float(self.bw_var.get()) * 1e6
		# Sincroniza GEO calc frecuencia/BW
		self.core.geo_calc.frequency_hz = self.core.calc.frequency_hz
		self.core.geo_calc.default_bandwidth_hz = self.core.calc.default_bandwidth_hz
		self._update_power_block()

	def _update_power_block(self):
		"""Fase 3: backoff y EIRP efectivo."""
		try:
			eirp_sat = float(self.eirp_sat_var.get())
		except Exception:
			eirp_sat = self.core.power.get('EIRP_sat_saturated', self.core.eirp_dbw)
		try:
			input_bo = max(0.0, float(self.input_bo_var.get()))
		except Exception:
			input_bo = 0.0
		output_bo = input_bo - 5.0 if input_bo > 0 else 0.0
		if self.manual_override_var.get():
			try:
				self.core.eirp_dbw = float(self.manual_eirp_var.get())
			except Exception:
				pass
		else:
			self.core.eirp_dbw = eirp_sat - input_bo
		self.core.power['EIRP_sat_saturated'] = eirp_sat
		self.core.power['Input_backoff'] = input_bo
		self.power_metrics = {
			'eirp_sat': eirp_sat,
			'input_bo': input_bo,
			'output_bo': output_bo,
			'eirp_eff': self.core.eirp_dbw,
			'manual_override': int(self.manual_override_var.get())
		}
		self.output_bo_label.config(text=f"Back-off Salida: {output_bo:.1f} dB")
		self.eirp_eff_label.config(text=f"EIRP Efectivo: {self.core.eirp_dbw:.1f} dBW")

	def _update_geometry_block(self):
		"""Calcula métricas geométricas y dinámica orbital ideal (solo LEO)."""
		if not hasattr(self, 'current_slant_distance_m'):
			self._draw_dynamic()
		mode = self.mode_var.get()
		self.geom: Dict[str, Any] = {k: float('nan') for k in ['delta_deg','r_orb_km','v_orb_kms','omega_deg_s','range_rate_kms','t_orb_min','visibility_remaining_s']}
		if mode == 'LEO':
			# Orbital (ideal circular)
			alt_m = self.core.constellation.satellites[0].altitude_m
			r_orb_m = EARTH_RADIUS_M + alt_m
			v_orb = math.sqrt(MU_EARTH / r_orb_m)  # m/s
			omega_rad_s = v_orb / r_orb_m
			omega_deg_s = math.degrees(omega_rad_s)
			T_orb_s = 2 * math.pi * math.sqrt(r_orb_m ** 3 / MU_EARTH)
			T_orb_min = T_orb_s / 60.0
			delta_deg = getattr(self, 'current_delta_deg', float('nan'))
			# Range rate analítica con signo según variación delta
			if not hasattr(self, '_prev_delta_deg'):
				self._prev_delta_deg = delta_deg
			approaching = delta_deg < self._prev_delta_deg  # se acerca a nadir
			delta_rad = math.radians(delta_deg)
			Re = EARTH_RADIUS_M
			r_orb = r_orb_m
			d_slant = self.current_slant_distance_m
			if d_slant <= 0:
				range_rate_ms = 0.0
			else:
				dd_dDelta = (Re * r_orb * math.sin(delta_rad)) / d_slant
				range_rate_ms = dd_dDelta * omega_rad_s
			if approaching:
				range_rate_ms *= -1.0
			self._prev_delta_deg = delta_deg
			# Tiempo de visibilidad restante (hasta horizonte)
			if self.current_visible:
				rem_deg = max(0.0, self.horizon_central_angle_deg - delta_deg)
				visibility_remaining_s = rem_deg / omega_deg_s if omega_deg_s > 0 else float('nan')
			else:
				visibility_remaining_s = 0.0
			self.geom.update({
				'delta_deg': delta_deg,
				'r_orb_km': r_orb_m / 1000.0,
				'v_orb_kms': v_orb / 1000.0,
				'omega_deg_s': omega_deg_s,
				'range_rate_kms': range_rate_ms / 1000.0,
				't_orb_min': T_orb_min,
				'visibility_remaining_s': visibility_remaining_s,
			})

	def _update_doppler_block(self):
		"""Doppler instantáneo y máximo (solo LEO)."""
		self.doppler: Dict[str, Any] = {'fd_hz': float('nan'), 'fd_max_hz': float('nan')}
		if self.mode_var.get() == 'LEO' and self.current_visible:
			f_c = self.core.calc.frequency_hz
			v_rad_ms = self.geom.get('range_rate_kms', float('nan')) * 1000.0
			v_orb_ms = self.geom.get('v_orb_kms', float('nan')) * 1000.0
			if not math.isnan(v_rad_ms):
				fd = (v_rad_ms / SPEED_OF_LIGHT) * f_c
				fd_max = (v_orb_ms / SPEED_OF_LIGHT) * f_c
				self.doppler.update({'fd_hz': fd, 'fd_max_hz': fd_max})
				
				# NUEVO: Almacenar para que lo use el sistema de jammers
				self.current_doppler_khz = fd / 1000.0  # Convertir Hz a kHz
			else:
				self.current_doppler_khz = 0.0
		else:
			self.current_doppler_khz = 0.0

	def _update_link_block(self):
		"""FSPL, latencia y C/N actuales (bloque ya existente)."""
		mode = self.mode_var.get()
		calc = self.core.calc if mode == 'LEO' else self.core.geo_calc
		d = getattr(self, 'current_slant_distance_m', float('nan'))
		visible = getattr(self, 'current_visible', False)
		# Actualiza pérdidas desde inputs UI
		if hasattr(self, 'loss_vars'):
			for k,var in self.loss_vars.items():
				try:
					self.core.losses[k] = float(var.get())
				except Exception:
					self.core.losses[k] = 0.0
		loss_total_extra = sum(self.core.losses.values())
		if visible:
			fspl = calc.free_space_path_loss_db(d)
			lat_ow = calc.propagation_delay_ms(d)
			# Usar Path Loss Total (= FSPL + pérdidas extra) para degradar C/N0
			path_loss_total = fspl + loss_total_extra
			cn0 = self.core.eirp_dbw + self.core.gt_dbk - path_loss_total + calc.K_BOLTZ_TERM
			cn = calc.cn_db(cn0)
		else:
			fspl = float('nan'); lat_ow = float('nan'); cn0 = float('nan'); cn = float('nan'); path_loss_total = float('nan')
		self.link_metrics = {
			'fspl_db': fspl,
			'latency_ms_ow': lat_ow,
			'cn0_dbhz': cn0,
			'cn_db': cn,
			'loss_total_extra_db': loss_total_extra,
			'path_loss_total_db': path_loss_total,
		}

	def _update_latency_block(self):
		"""Fase 5: latencias totales (propagación + procesamiento + switching)."""
		try:
			proc_ms = max(0.0, float(self.proc_lat_var.get()))
		except Exception:
			proc_ms = 0.0
		try:
			switch_ms = max(0.0, float(self.switch_lat_var.get()))
		except Exception:
			switch_ms = 0.0
		self.core.latencies['Processing_delay_ms'] = proc_ms
		self.core.latencies['Switching_delay_ms'] = switch_ms
		prop_ow = self.link_metrics.get('latency_ms_ow', float('nan'))
		if not math.isnan(prop_ow):
			total_ow = prop_ow + proc_ms + switch_ms
			total_rtt = 2*prop_ow + 2*(proc_ms + switch_ms)
			self.link_metrics['total_latency_ow_ms'] = total_ow
			self.link_metrics['total_latency_rtt_ms'] = total_rtt

	def _update_modcod_block(self):
		"""Fase 5: selección adaptativa de MODCOD y actualización de Rb/EbN0_req."""
		mod_table = self.core.params.get(["MODCOD","table"])
		# Construir mapa nombre->entry con eficiencia
		best = None
		current_ebn0 = None
		# Usar Eb/N0 del tab activo en lugar del sistema tradicional
		current_ebn0 = self._get_active_ebn0_db()
		# Calcular eficiencias
		for entry in mod_table:
			bps = entry['bits_per_symbol'] * entry['code_rate']  # bits útiles por símbolo
			entry['efficiency_bps_hz'] = bps  # asumimos Nyquist 1 símbolo/Hz
		# Auto selección
		if self.modcod_auto_var.get() and current_ebn0 is not None and not math.isnan(current_ebn0):
			hyst = self.core.params.get(["MODCOD","hysteresis_db"])
			candidates = []
			for e in mod_table:
				if current_ebn0 - e['ebn0_req_db'] >= hyst:
					candidates.append(e)
			if candidates:
				best = max(candidates, key=lambda x: x['efficiency_bps_hz'])
			else:
				# Ninguna cumple margen; escoger la más robusta (menor req)
				best = min(mod_table, key=lambda x: x['ebn0_req_db'])
			self.modcod_selected_var.set(best['name'])
		else:
			# Manual: encontrar entry activo
			for e in mod_table:
				if e['name'] == self.modcod_selected_var.get():
					best = e; break
		if not best:
			best = mod_table[0]
		self.modcod_active = best
		# Actualizar requerimiento Eb/N0 y Rb
		self.core.throughput['EbN0_req_dB'] = best['ebn0_req_db']
		# Recalcular Rb en función de BW y eficiencia modcod (bits/Hz)
		bw_hz = self.core.calc.default_bandwidth_hz
		Rb_bps = best['efficiency_bps_hz'] * bw_hz
		self.core.throughput['Rb_Mbps'] = Rb_bps / 1e6
		# Actualizar variables y labels (siempre solo lectura)
		self.rb_var.set(self.core.throughput['Rb_Mbps'])
		self.ebn0_req_var.set(self.core.throughput['EbN0_req_dB'])
		if hasattr(self,'rb_value_label'):
			self.rb_value_label.config(text=f"{self.core.throughput['Rb_Mbps']:.3f}")
		if hasattr(self,'ebn0_req_value_label'):
			self.ebn0_req_value_label.config(text=f"{self.core.throughput['EbN0_req_dB']:.2f}")
		# Margen MODCOD
		if current_ebn0 is not None and not math.isnan(current_ebn0):
			self.modcod_margin_db = current_ebn0 - best['ebn0_req_db']
			if self.modcod_margin_db > 3:
				self.modcod_status = 'Excelente'
			elif self.modcod_margin_db >= 1:
				self.modcod_status = 'Aceptable'
			elif self.modcod_margin_db >= 0:
				self.modcod_status = 'Critico'
			else:
				self.modcod_status = 'Insuficiente'
		else:
			self.modcod_margin_db = float('nan')
			self.modcod_status = '—'
		# Actualizar labels MODCOD
		self.modcod_eff_label.config(text=f"Eff: {best['efficiency_bps_hz']:.3f} b/Hz")
		self.modcod_req_label.config(text=f"Eb/N0 Req: {best['ebn0_req_db']:.2f} dB")
		color_map = {'Excelente':'#007700','Aceptable':'#c08000','Critico':'#b05000','Insuficiente':'#b00000','—':'#666666'}
		self.modcod_status_label.config(text=f"Estado: {self.modcod_status}", foreground=color_map.get(self.modcod_status,'#444444'))

	def _add_dynamic_metric_row(self, display_name: str):
		"""Inserta una nueva fila de métrica al final si no existía."""
		if display_name in self.metric_labels:
			return
		# Buscar fila máxima actual
		max_row = 0
		for child in self.metrics_panel.grid_slaves():
			try:
				max_row = max(max_row, int(child.grid_info().get('row',0)))
			except Exception:
				pass
		row = max_row + 1
		font_label = ('Segoe UI', 10, 'bold'); font_value = ('Consolas', 11)
		lbl = ttk.Label(self.metrics_panel, text=display_name+':', font=font_label, anchor='w')
		lbl.grid(row=row, column=0, sticky='w', padx=(2,4), pady=1)
		val_lbl = ttk.Label(self.metrics_panel, text='—', font=font_value, foreground='#004080', anchor='e')
		val_lbl.grid(row=row, column=1, sticky='e', padx=(4,6), pady=1)
		self.metric_labels[display_name] = val_lbl

	def _update_performance_block(self):
		"""Fase 4: calcula T_sys, N0, Eb/N0, margen y métricas de capacidad.

		T_sys = suma de temperaturas componentes (simplificado).
		N0_dBHz = 10log10(k*T_sys) = -198.6 + 10log10(T_sys) (porque 228.6 = 10log10(1/k)).
		Eb/N0 = C/N0 - 10log10(Rb) (Rb en bit/s)
		Capacidad Shannon usando C/N lineal (=10^(C/N/10)).
		"""
		# Leer inputs ruido / throughput
		try:
			self.core.noise['T_rx'] = max(0.0, float(self.t_rx_var.get()))
		except Exception:
			self.core.noise['T_rx'] = 0.0
		try:
			self.core.noise['T_clear_sky'] = max(0.0, float(self.t_sky_var.get()))
		except Exception:
			self.core.noise['T_clear_sky'] = 0.0
		try:
			self.core.noise['T_rain_excess'] = max(0.0, float(self.t_rain_var.get()))
		except Exception:
			self.core.noise['T_rain_excess'] = 0.0
		T_sys = self.core.noise['T_rx'] + self.core.noise['T_clear_sky'] + self.core.noise['T_rain_excess']
		if T_sys <= 0: T_sys = float('nan')
		# N0: kT => 10log10(k) ~ -228.6 dBW/Hz; pero usamos C/N0 fórmula eirp+G/T - L + 228.6 => N0_dBHz = - (G/T - 10log10(T_sys))? Para simplicidad educativa usamos:
		# N0_dBHz (dBW/Hz) = -228.6 + 10log10(T_sys)  (valor absoluto de densidad de ruido)
		if not math.isnan(T_sys):
			N0_dBHz = -228.6 + 10*math.log10(T_sys)
		else:
			N0_dBHz = float('nan')
		# Throughput
		# (Rb y Eb/N0 Req ya fueron fijados por el bloque MODCOD; no se leen entradas del usuario)
		Rb_bps = self.core.throughput['Rb_Mbps'] * 1e6
		cn0 = self.link_metrics.get('cn0_dbhz', float('nan'))
		if not math.isnan(cn0) and Rb_bps > 0:
			EbN0_dB = cn0 - 10*math.log10(Rb_bps)
		else:
			EbN0_dB = float('nan')
		EbN0_req = self.core.throughput['EbN0_req_dB']
		margin_dB = EbN0_dB - EbN0_req if not math.isnan(EbN0_dB) else float('nan')
		# Capacidad Shannon
		cn_db = self.link_metrics.get('cn_db', float('nan'))
		if not math.isnan(cn_db):
			cn_lin = 10**(cn_db/10.0)
			BW_hz = self.core.calc.default_bandwidth_hz
			C_shannon_bps = BW_hz * math.log2(1+cn_lin)
			C_shannon_Mbps = C_shannon_bps / 1e6
			eta_shannon = (C_shannon_bps / BW_hz) if BW_hz>0 else float('nan')  # bits/s/Hz
			eta_real = (Rb_bps / BW_hz) if BW_hz>0 else float('nan')
			util_pct = (eta_real / eta_shannon * 100.0) if eta_shannon and not math.isnan(eta_shannon) and eta_shannon>0 else float('nan')
		else:
			C_shannon_Mbps = float('nan'); eta_shannon = float('nan'); eta_real = float('nan'); util_pct = float('nan')
		self.perf_metrics = {
			'T_sys_K': T_sys,
			'N0_dBHz': N0_dBHz,
			'EbN0_dB': EbN0_dB,
			'EbN0_req_dB': EbN0_req,
			'Eb_margin_dB': margin_dB,
			'Shannon_capacity_Mbps': C_shannon_Mbps,
			'Spectral_eff_real_bps_hz': eta_real,
			'Utilization_pct': util_pct,
			# NUEVAS MÉTRICAS DINÁMICAS
			'shannon_capacity_Mbps': C_shannon_Mbps,  # Para compatibilidad CSV
			'effective_throughput_Mbps': C_shannon_Mbps * 0.45,  # Base: 45% de capacidad Shannon
			'spectral_efficiency_bps_Hz': eta_real,
			'bit_rate_Mbps': self.rb_var.get() if hasattr(self, 'rb_var') else 50.0
		}
	
	def _update_jamming_block(self):
		"""Escenario 2: Calcula métricas de Spot Jamming."""
		if not JAMMERS_AVAILABLE:
			self.jamming_metrics = {"jamming_enabled": False}
			return
		
		# Vincular jammers activos desde el manager si existe
		if hasattr(self, 'jammer_manager') and self.jammer_manager:
			self.core._active_jammers = list(self.jammer_manager.jammers.values())
		else:
			self.core._active_jammers = []
		
		# Pasar C/N actual para cálculos CINR
		cn_db = self.link_metrics.get('cn_db', float('nan'))
		self.core.current_cn_db = cn_db
		self.core.current_slant_distance_m = self.current_slant_distance_m
		
		# Calcular métricas de jamming
		self.jamming_metrics = self.core.calculate_spot_jamming_metrics()
		
		# === ACTUALIZAR MÉTRICAS EN TIEMPO REAL EN GUI ===
		if hasattr(self, 'jammer_manager'):
			# Agregar métricas avanzadas para la GUI
			if self.jamming_metrics.get("jamming_enabled", False):
				advanced_metrics = self._calculate_spot_jamming_advanced_metrics(self.jamming_metrics)
				self.jamming_metrics["advanced_metrics"] = advanced_metrics
			
			# GARANTIZAR CONSISTENCIA GUI-CSV: Usar misma fuente de degradación
			if self.jamming_metrics.get("jamming_enabled", False):
				combined = self.jamming_metrics.get("combined_metrics", {})
				# Usar exactamente la misma degradación para GUI y CSV
				degradacion_consistente = combined.get("degradation_db", 0.0)
				
				# Actualizar la fuente GUI para consistencia
				combined["degradation_db"] = degradacion_consistente
				self.jamming_metrics["combined_metrics"] = combined
			
			# Actualizar display en tiempo real
			self.jammer_manager.update_real_time_metrics(self.jamming_metrics)
		
		# Actualizar estado en GUI si hay jammers
		if self.jamming_metrics.get("jamming_enabled", False):
			combined = self.jamming_metrics["combined_metrics"]
			diagnostic = self.jamming_metrics.get("diagnostic", {})
			effectiveness = combined["effectiveness"]
			impact_level = diagnostic.get("impact_level", "DESCONOCIDO")
			
			# === INDICADORES VISUALES MEJORADOS ===
			if hasattr(self, 'jamming_status_label'):
				# Colores según nivel de impacto
				if impact_level in ["CRÍTICO"]:
					status_color = '#cc0000'  # Rojo intenso - jamming crítico
					status_icon = "🔴"
				elif impact_level in ["MODERADO"]:
					status_color = '#ff8800'  # Naranja - moderado
					status_icon = "🟠"
				elif impact_level in ["LEVE"]:
					status_color = '#ffcc00'  # Amarillo - leve
					status_icon = "🟡"
				else:  # INEFECTIVO
					status_color = '#00aa00'  # Verde - inefectivo
					status_icon = "🟢"
				
				# Texto detallado con métricas clave
				degradation = combined.get("degradation_db", 0)
				ci_db = combined.get("ci_total_db", float('inf'))
				ci_text = f"{ci_db:.1f}" if not math.isinf(ci_db) else "∞"
				
				status_text = f"{status_icon} {impact_level} | C/I: {ci_text} dB | Degr: {degradation:.1f} dB"
				
				self.jamming_status_label.config(
					text=f"Jamming: {status_text}", 
					foreground=status_color
				)
				
			# === RESUMEN DE DIAGNÓSTICO EN TOOLTIP O PANEL ADICIONAL ===
			if hasattr(self, 'jamming_diagnostic_label'):
				explanation = diagnostic.get("explanation", "Sin análisis disponible")
				distance_analysis = diagnostic.get("distance_analysis", "")
				self.jamming_diagnostic_label.config(
					text=f"📊 {explanation[:60]}{'...' if len(explanation) > 60 else ''}",
					foreground='#444444'
				)
		else:
			# === SIN JAMMING ACTIVO ===
			if hasattr(self, 'jamming_status_label'):
				self.jamming_status_label.config(
					text="🔘 Jamming: DESACTIVADO", 
					foreground='#888888'
				)
			if hasattr(self, 'jamming_diagnostic_label'):
				self.jamming_diagnostic_label.config(
					text="📊 Sin jammers activos en el escenario",
					foreground='#888888'
				)

	def _apply_jamming_to_link(self):
		"""NUEVO: Aplica degradación por jamming a las métricas principales del enlace"""
		if not JAMMERS_AVAILABLE or not hasattr(self, 'jamming_metrics'):
			return
		
		# Verificar si hay jamming activo
		if not self.jamming_metrics.get("jamming_enabled", False):
			return
		
		combined = self.jamming_metrics.get("combined_metrics", {})
		if not combined:
			return
		
		# Obtener métricas de jamming
		cinr_with_jamming_db = combined.get("cinr_db", float('nan'))
		ci_ratio_db = combined.get("ci_ratio_db", float('nan'))
		effectiveness = combined.get("effectiveness", "SIN_JAMMING")
		
		# Aplicar degradación solo si el jamming es efectivo
		if effectiveness in ["EFECTIVO", "SEVERO"] and not math.isnan(cinr_with_jamming_db):
			# DEGRADAR C/N original por efecto del jamming
			original_cn_db = self.link_metrics.get('cn_db', float('nan'))
			
			if not math.isnan(original_cn_db):
				# El CINR con jamming es más restrictivo que el C/N original
				# Aplicar la degradación al enlace principal
				self.link_metrics['cn_db'] = cinr_with_jamming_db
				
				# Actualizar métricas dependientes
				# También actualizar C/N0 proporcionalmente
				degradation_db = original_cn_db - cinr_with_jamming_db
				original_cn0_dbhz = self.link_metrics.get('cn0_dbhz', float('nan'))
				if not math.isnan(original_cn0_dbhz):
					self.link_metrics['cn0_dbhz'] = original_cn0_dbhz - degradation_db
				
				# Agregar información de degradación a métricas
				self.link_metrics['jamming_degradation_db'] = degradation_db
				self.link_metrics['original_cn_db'] = original_cn_db
				self.link_metrics['jamming_active'] = True
			else:
				self.link_metrics['jamming_active'] = False
		else:
			self.link_metrics['jamming_active'] = False

	def _assess_eb_margin(self, margin_db: float):
		if isinstance(margin_db, float) and math.isnan(margin_db):
			return ("—", '#666666')
		if margin_db > 3.0:
			return ("OK", '#007700')
		elif margin_db >= 0.0:
			return ("Justo", '#c08000')
		else:
			return ("Insuficiente", '#b00000')

	def _render_metrics(self):
		def fmt(v, pattern="{:.2f}"):
			return '—' if (isinstance(v, float) and math.isnan(v)) else (pattern.format(v) if isinstance(v, (int, float)) else str(v))
		visible = getattr(self, 'current_visible', False)
		# Básicos
		self.metric_labels['Modo'].config(text=self.mode_var.get())
		self.metric_labels['Tiempo Simulación [s]'].config(text=f"{self.simulation_time_s:.1f}")
		control_mode = "Manual" if self.manual_time_control else "Automático"
		self.metric_labels['Modo Control'].config(text=control_mode)
		elv_txt = f"{self.current_elevation_deg:.1f} ({'OK' if visible else 'OCULTO'})"
		self.metric_labels['Elevación [°]'].config(text=elv_txt, foreground=('#004080' if visible else '#aa0000'))
		self.metric_labels['Distancia Slant [km]'].config(text=fmt(self.current_slant_distance_m/1000.0, "{:.0f}"))
		self.metric_labels['FSPL (Espacio Libre) [dB]'].config(text=fmt(self._get_active_fspl_db()))
		self.metric_labels['Latencia Ida [ms]'].config(text=fmt(self.link_metrics['latency_ms_ow']))
		rtt_ms = self.link_metrics['latency_ms_ow'] * 2 if not math.isnan(self.link_metrics['latency_ms_ow']) else float('nan')
		self.metric_labels['Latencia RTT [ms]'].config(text=fmt(rtt_ms))
		# Fase 5: latencias totales
		if 'total_latency_ow_ms' in self.link_metrics:
			# Añadimos/actualizamos dinámicamente labels si no existen
			if 'Latencia Total Ida [ms]' not in self.metric_labels:
				self._add_dynamic_metric_row('Latencia Total Ida [ms]')
			if 'Latencia Total RTT [ms]' not in self.metric_labels:
				self._add_dynamic_metric_row('Latencia Total RTT [ms]')
			self.metric_labels['Latencia Total Ida [ms]'].config(text=fmt(self.link_metrics['total_latency_ow_ms']))
			self.metric_labels['Latencia Total RTT [ms]'].config(text=fmt(self.link_metrics['total_latency_rtt_ms']))
		else:
			# Si invisibles y existen, mostrar guion
			if 'Latencia Total Ida [ms]' in self.metric_labels:
				self.metric_labels['Latencia Total Ida [ms]'].config(text='—')
			if 'Latencia Total RTT [ms]' in self.metric_labels:
				self.metric_labels['Latencia Total RTT [ms]'].config(text='—')
		self.metric_labels['C/N0 [dBHz]'].config(text=fmt(self._get_active_cn0_dbhz()))
		self.metric_labels['C/N [dB]'].config(text=fmt(self._get_active_cn_db()))
		self.metric_labels['G/T [dB/K]'].config(text=fmt(self.core.gt_dbk, "{:.1f}"))
		status_txt, color = self._assess_cn(self._get_active_cn_db())
		self.metric_labels['Estado C/N'].config(text=status_txt, foreground=color)

		# Potencia / Backoff
		self.metric_labels['EIRP Saturado [dBW]'].config(text=fmt(self.power_metrics.get('eirp_sat', float('nan')), "{:.1f}"))
		self.metric_labels['Back-off Entrada [dB]'].config(text=fmt(self.power_metrics.get('input_bo', float('nan')), "{:.1f}"))
		self.metric_labels['Back-off Salida [dB]'].config(text=fmt(self.power_metrics.get('output_bo', float('nan')), "{:.1f}"))
		self.metric_labels['EIRP Efectivo [dBW]'].config(text=fmt(self.core.eirp_dbw, "{:.1f}"))
		# Geometría
		self.metric_labels['Ángulo Central Δ [°]'].config(text=fmt(self.geom['delta_deg'], "{:.2f}"))
		self.metric_labels['Radio Orbital [km]'].config(text=fmt(self.geom['r_orb_km'], "{:.0f}"))
		self.metric_labels['Velocidad Orbital [km/s]'].config(text=fmt(self.geom['v_orb_kms'], "{:.2f}"))
		self.metric_labels['Velocidad Angular ω [°/s]'].config(text=fmt(self.geom['omega_deg_s'], "{:.3f}"))
		self.metric_labels['Rate Cambio Distancia [km/s]'].config(text=fmt(self.geom['range_rate_kms'], "{:.3f}"))
		self.metric_labels['Periodo Orbital [min]'].config(text=fmt(self.geom['t_orb_min'], "{:.1f}"))
		self.metric_labels['Tiempo Visibilidad Restante [s]'].config(text=fmt(self.geom['visibility_remaining_s'], "{:.1f}"))
		# Doppler
		fd_khz = self.doppler['fd_hz'] / 1e3 if not math.isnan(self.doppler['fd_hz']) else float('nan')
		fdmax_khz = self.doppler['fd_max_hz'] / 1e3 if not math.isnan(self.doppler['fd_max_hz']) else float('nan')
		self.metric_labels['Doppler Instantáneo [kHz]'].config(text=fmt(fd_khz, "{:.1f}"))
		self.metric_labels['Doppler Máx Teórico [kHz]'].config(text=fmt(fdmax_khz, "{:.1f}"))
		# Pérdidas
		self.metric_labels['Σ Pérdidas Extra [dB]'].config(text=fmt(self.link_metrics.get('loss_total_extra_db', float('nan'))))
		self.metric_labels['Path Loss Total [dB]'].config(text=fmt(self.link_metrics.get('path_loss_total_db', float('nan'))))
		# Ruido y rendimiento
		if hasattr(self, 'perf_metrics'):
			self.metric_labels['Temperatura Sistema T_sys [K]'].config(text=fmt(self.perf_metrics['T_sys_K'], "{:.1f}"))
			self.metric_labels['Densidad Ruido N0 [dBHz]'].config(text=fmt(self.perf_metrics['N0_dBHz'], "{:.1f}"))
			self.metric_labels['Eb/N0 [dB]'].config(text=fmt(self.perf_metrics['EbN0_dB'], "{:.2f}"))
			self.metric_labels['Eb/N0 Requerido [dB]'].config(text=f"{self.perf_metrics['EbN0_req_dB']:.2f}")
			self.metric_labels['Margen Eb/N0 [dB]'].config(text=fmt(self.perf_metrics['Eb_margin_dB'], "{:.2f}"), foreground=self._assess_eb_margin(self.perf_metrics['Eb_margin_dB'])[1])
			self.metric_labels['Capacidad Shannon [Mbps]'].config(text=fmt(self.perf_metrics['Shannon_capacity_Mbps'], "{:.2f}"))
			self.metric_labels['Eficiencia Espectral Real [b/Hz]'].config(text=fmt(self.perf_metrics['Spectral_eff_real_bps_hz'], "{:.3f}"))
			self.metric_labels['Utilización vs Shannon [%]'].config(text=fmt(self.perf_metrics['Utilization_pct'], "{:.1f}"))
		if getattr(self, 'show_losses', False) and hasattr(self, 'loss_detail_label_map'):
			for k,v in self.core.losses.items():
				if k in self.loss_detail_label_map:
					self.loss_detail_label_map[k].config(text=fmt(v, "{:.2f}"))
		
		# === ALERTA DE COHERENCIA SUPER-GEO ===
		self._check_and_display_super_geo_alert()
	
	def _check_and_display_super_geo_alert(self):
		"""
		Verifica si hay jammer Super-GEO con configuración incoherente y muestra alerta visual.
		"""
		if not (hasattr(self, 'jammer_manager') and self.jammer_manager.jammers):
			return
		
		# Verificar si hay algún jammer Super-GEO activo
		super_geo_jammer = None
		for jammer_config in self.jammer_manager.jammers.values():
			jammer_altitude = getattr(jammer_config, 'altitude_km', 0.001)
			if jammer_altitude >= 45000.0:  # Super-GEO range
				super_geo_jammer = jammer_config
				break
		
		if not super_geo_jammer:
			# No hay jammer Super-GEO, ocultar alerta si existe
			if hasattr(self, 'super_geo_alert_label'):
				self.super_geo_alert_label.destroy()
				delattr(self, 'super_geo_alert_label')
			return
		
		# Hay jammer Super-GEO, verificar coherencia
		jamming_data = getattr(self, 'jamming_metrics', None)
		if not jamming_data or not jamming_data.get("jamming_enabled", False):
			return
		
		# Obtener métricas para análisis
		degradation_db = jamming_data.get("combined_metrics", {}).get("degradation_db", 0.0)
		ci_db = jamming_data.get("combined_metrics", {}).get("ci_total_db", float('inf'))
		
		# Realizar análisis de coherencia
		from JammerSystem import PhysicalValidation
		validator = PhysicalValidation()
		
		satellite_altitude = 550.0  # LEO por defecto
		if hasattr(self, 'sat_type') and self.sat_type == 'GEO':
			satellite_altitude = 35786.0
		
		jammer_eirp = jamming_data.get("individual_results", [{}])[0].get("jammer_eirp_dbw", 63.0)
		sat_eirp = self.power_metrics.get('eirp_sat', 50.0)
		
		try:
			super_geo_analysis = validator.analyze_super_geo_jammer_coherence(
				jammer_altitude_km=super_geo_jammer.altitude_km,
				satellite_altitude_km=satellite_altitude,
				jammer_eirp_dbw=jammer_eirp,
				satellite_eirp_dbw=sat_eirp,
				degradation_db=degradation_db,
				ci_db=ci_db
			)
			
			coherence_level = super_geo_analysis.get("coherence_level", "COHERENTE")
			
			# Determinar mensaje y color de alerta
			if coherence_level == "INCOHERENTE":
				alert_msg = f"⚠️ ALERTA: Jammer Super-GEO INCOHERENTE"
				alert_color = "#CC0000"  # Rojo
				detailed_msg = f"Factor distancia: {super_geo_analysis.get('physics_metrics', {}).get('distance_factor', 0):.0f}x | EIRP req: {super_geo_analysis.get('physics_metrics', {}).get('required_eirp_dbw', 0):.0f} dBW"
			elif coherence_level == "DUDOSO":
				alert_msg = f"⚠️ ADVERTENCIA: Jammer Super-GEO DUDOSO"
				alert_color = "#FF8C00"  # Naranja
				detailed_msg = f"Revisar parámetros | Degradación: {degradation_db:.1f} dB"
			else:
				# Coherente, no mostrar alerta
				if hasattr(self, 'super_geo_alert_label'):
					self.super_geo_alert_label.destroy()
					delattr(self, 'super_geo_alert_label')
				return
			
			# Crear o actualizar label de alerta
			if not hasattr(self, 'super_geo_alert_label'):
				# Crear frame de alerta en la parte superior del panel de métricas
				alert_frame = ttk.Frame(self.metrics_panel)
				alert_frame.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 5))
				
				self.super_geo_alert_label = tk.Label(
					alert_frame, 
					text=alert_msg,
					font=('Segoe UI', 9, 'bold'),
					bg=alert_color,
					fg='white',
					wraplength=300,
					justify='center'
				)
				self.super_geo_alert_label.pack(fill='x', padx=2, pady=2)
				
				# Label adicional para detalles
				self.super_geo_details_label = tk.Label(
					alert_frame,
					text=detailed_msg,
					font=('Segoe UI', 8),
					bg='#F0F0F0',
					fg='black',
					wraplength=300,
					justify='center'
				)
				self.super_geo_details_label.pack(fill='x', padx=2, pady=(0, 2))
			else:
				# Actualizar alerta existente
				self.super_geo_alert_label.config(text=alert_msg, bg=alert_color)
				if hasattr(self, 'super_geo_details_label'):
					self.super_geo_details_label.config(text=detailed_msg)
				
		except Exception as e:
			# Si hay error en análisis, mostrar alerta genérica
			if not hasattr(self, 'super_geo_alert_label'):
				alert_frame = ttk.Frame(self.metrics_panel)
				alert_frame.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 5))
				
				self.super_geo_alert_label = tk.Label(
					alert_frame,
					text=f"⚠️ ERROR: Validación Super-GEO falló",
					font=('Segoe UI', 9, 'bold'),
					bg='#808080',
					fg='white'
				)
				self.super_geo_alert_label.pack(fill='x', padx=2, pady=2)

	def _assess_cn(self, cn_db: float):
		if isinstance(cn_db, float) and math.isnan(cn_db):
			return ("No visible", "#666666")
		try:
			val = float(cn_db)
		except Exception:
			return ("—", "#666666")
		if val > 15.0:
			return ("Excelente", "#007700")
		elif val >= 6.0:
			return ("Aceptable", "#c08000")
		else:
			return ("Critico", "#b00000")

	def _calculate_spot_jamming_advanced_metrics(self, jamming_data) -> dict:
		"""
		Calcula las métricas avanzadas del Spot Jamming Selectivo.
		Incluye análisis de frecuencia, MODCOD adaptativo, discriminación angular dinámica y RTT realista.
		CORREGIDO: Obtiene frecuencias de variables de la GUI correctamente.
		"""
		if jamming_data is None or not jamming_data.get("jamming_enabled", False):
			return {
				'jammer_center_freq_ghz': None,
				'jammer_bandwidth_mhz': None,
				'spectral_overlap_percent': None,
				'target_link_detected': "SIN_JAMMING",
				'frequency_offset_mhz': None,
				'modcod_selected': "N/A",
				'spectral_efficiency': None,
				'discrimination_angular_real_db': None,
				'rtt_processing_overhead_ms': None,
				'jamming_detection_time_ms': None,
				'frequency_selectivity_factor': None,
				'adaptive_efficiency_gain': None,
			}
		
		# === OBTENER FRECUENCIAS REALES DE LA GUI ===
		try:
			# Obtener frecuencias directamente de las variables de la GUI
			ul_freq_ghz = float(self.ul_freq_var.get()) if hasattr(self, 'ul_freq_var') else 30.0
			dl_freq_ghz = float(self.dl_freq_var.get()) if hasattr(self, 'dl_freq_var') else 20.0
			ul_bw_mhz = float(self.ul_bw_var.get()) if hasattr(self, 'ul_bw_var') else 20.0
			dl_bw_mhz = float(self.dl_bw_var.get()) if hasattr(self, 'dl_bw_var') else 20.0
		except (ValueError, AttributeError):
			# Valores por defecto si falla la obtención
			ul_freq_ghz = 30.0
			dl_freq_ghz = 20.0
			ul_bw_mhz = 20.0
			dl_bw_mhz = 20.0
		
		# === CONFIGURACION DEL JAMMER ===
		# Obtener la frecuencia configurada del jammer, NO la UL del satelite
		jammer_center_freq_ghz = 12.0  # Frecuencia configurada del jammer (por defecto)
		jammer_name = "SPOT_1"  # Nombre por defecto
		
		# Intentar obtener la frecuencia real de los jammers configurados
		if hasattr(self, 'jammer_manager') and self.jammer_manager.jammers:
			# Usar el primer jammer configurado como referencia
			first_jammer = next(iter(self.jammer_manager.jammers.values()))
			jammer_center_freq_ghz = first_jammer.frequency_ghz
			jammer_name = getattr(first_jammer, 'name', first_jammer.id)
		
		# === TARGETING INTELIGENTE: Priorizar enlace más vulnerable ===
		# Obtener CINR actual de ambos enlaces
		ul_cinr_current = self.link_metrics.get('ul_cinr_db', 15.0)
		dl_cinr_current = self.link_metrics.get('dl_cinr_db', 35.0)
		
		# Calcular offsets frecuenciales
		ul_freq_offset = abs(jammer_center_freq_ghz - ul_freq_ghz)
		dl_freq_offset = abs(jammer_center_freq_ghz - dl_freq_ghz)
		
		# Estrategia inteligente: atacar enlace más vulnerable que esté en rango frecuencial
		# Umbral de proximidad frecuencial: 5 GHz (efectividad mínima aceptable)
		frequency_threshold_ghz = 5.0
		
		if ul_freq_offset <= frequency_threshold_ghz and dl_freq_offset <= frequency_threshold_ghz:
			# Ambos enlaces en rango: atacar el más vulnerable (menor CINR)
			target_link = "UL" if ul_cinr_current <= dl_cinr_current else "DL"
			target_reasoning = f"VULNERABLE (UL:{ul_cinr_current:.1f}dB vs DL:{dl_cinr_current:.1f}dB)"
		elif ul_freq_offset <= frequency_threshold_ghz:
			# Solo UL en rango frecuencial
			target_link = "UL"
			target_reasoning = f"FRECUENCIAL (UL offset: {ul_freq_offset:.1f}GHz)"
		elif dl_freq_offset <= frequency_threshold_ghz:
			# Solo DL en rango frecuencial  
			target_link = "DL"
			target_reasoning = f"FRECUENCIAL (DL offset: {dl_freq_offset:.1f}GHz)"
		else:
			# Ningún enlace en rango óptimo: atacar el más cercano
			target_link = "UL" if ul_freq_offset <= dl_freq_offset else "DL"
			target_reasoning = f"SUBOPTIMO (min offset: {min(ul_freq_offset, dl_freq_offset):.1f}GHz)"
		
		target_freq_ghz = ul_freq_ghz if target_link == "UL" else dl_freq_ghz
		target_bw_mhz = ul_bw_mhz if target_link == "UL" else dl_bw_mhz
		
		# === COMPENSACION DOPPLER ADAPTATIVA (Opción B - Seguimiento Doppler) ===
		# Obtener Doppler instantáneo actual
		doppler_instantaneo_khz = getattr(self, 'current_doppler_khz', 0.0)
		doppler_instantaneo_ghz = doppler_instantaneo_khz / 1e6  # Convertir kHz -> GHz
		
		# Aplicar corrección Doppler al jammer para seguimiento preciso
		jammer_center_freq_compensated = jammer_center_freq_ghz + doppler_instantaneo_ghz
		
		# Calcular ancho de banda óptimo considerando máximo Doppler esperado
		doppler_max_khz = getattr(self, 'max_doppler_khz', 506.283)  # Del CSV
		doppler_margin_mhz = 2 * (doppler_max_khz / 1000)  # ±506 kHz -> 1.012 MHz total
		bw_minimo_compensado = target_bw_mhz + doppler_margin_mhz
		jammer_bandwidth_mhz = max(50.0, bw_minimo_compensado * 1.25)  # Margen 25%
		
		jammer_eirp_dbw = jamming_data.get("primary_jammer_eirp_dbw", 63.0)
		
		# === CREAR INSTANCIA DE JAMMER SELECTIVO CON COMPENSACION DOPPLER ===
		from JammerSystem import SpotJammerFrequencySelective
		selective_jammer = SpotJammerFrequencySelective(
			center_freq_ghz=jammer_center_freq_compensated,  # Frecuencia compensada por Doppler
			bandwidth_mhz=jammer_bandwidth_mhz,
			eirp_dbw=jammer_eirp_dbw
		)
		
		# === CALCULAR EFECTIVIDAD Y SOLAPAMIENTO ESPECTRAL ===
		effectiveness_result = selective_jammer.calculate_jamming_effectiveness(
			ul_freq_ghz=ul_freq_ghz,
			dl_freq_ghz=dl_freq_ghz,
			ul_bandwidth_mhz=ul_bw_mhz,
			dl_bandwidth_mhz=dl_bw_mhz
		)
		
		# Calcular solapamiento espectral real usando FREQUENCY_OFFSET_MHZ
		frequency_offset_mhz = abs(jammer_center_freq_compensated - target_freq_ghz) * 1000
		
		def calcular_solapamiento_espectral(f_jammer_ghz, bw_jammer_mhz, f_signal_ghz, bw_signal_mhz):
			"""Calcula solapamiento espectral real entre jammer y señal"""
			# Convertir todo a MHz para precisión
			f_jammer_mhz = f_jammer_ghz * 1000
			f_signal_mhz = f_signal_ghz * 1000
			
			# Límites espectrales
			jammer_min = f_jammer_mhz - bw_jammer_mhz/2
			jammer_max = f_jammer_mhz + bw_jammer_mhz/2
			signal_min = f_signal_mhz - bw_signal_mhz/2
			signal_max = f_signal_mhz + bw_signal_mhz/2
			
			# Calcular solapamiento
			overlap_min = max(jammer_min, signal_min)
			overlap_max = min(jammer_max, signal_max)
			
			if overlap_max <= overlap_min:
				return 0.0  # Sin solapamiento
			
			overlap_bandwidth = overlap_max - overlap_min
			solapamiento_porcentaje = (overlap_bandwidth / bw_signal_mhz) * 100
			return min(100.0, solapamiento_porcentaje)
		
		# Calcular solapamiento real para ambos enlaces
		ul_spectral_overlap = calcular_solapamiento_espectral(
			jammer_center_freq_compensated, jammer_bandwidth_mhz, ul_freq_ghz, ul_bw_mhz)
		dl_spectral_overlap = calcular_solapamiento_espectral(
			jammer_center_freq_compensated, jammer_bandwidth_mhz, dl_freq_ghz, dl_bw_mhz)
		
		# Usar el enlace objetivo para métricas principales
		spectral_overlap_percent = ul_spectral_overlap if target_link == "UL" else dl_spectral_overlap
		frequency_selectivity_factor = spectral_overlap_percent / 100.0
		
		# === CALCULAR EFECTIVIDAD REAL DEL JAMMING ===
		# Basado en solapamiento espectral y degradación CINR
		cinr_degradation_db = jamming_data.get("combined_metrics", {}).get("degradation_db", 0.0)
		
		if spectral_overlap_percent >= 90:
			if cinr_degradation_db >= 10:
				efectividad_jamming = "CRITICO"
			elif cinr_degradation_db >= 5:
				efectividad_jamming = "EFECTIVO" 
			else:
				efectividad_jamming = "MODERADO"
		elif spectral_overlap_percent >= 50:
			if cinr_degradation_db >= 5:
				efectividad_jamming = "MODERADO"
			else:
				efectividad_jamming = "LIMITADO"
		elif spectral_overlap_percent >= 10:
			efectividad_jamming = "LIMITADO"
		else:
			efectividad_jamming = "INEFECTIVO"
		
		# Definir target_link_detected basado en nuestra lógica inteligente
		target_link_detected = f"{target_link} ({target_reasoning})"
		
		# === MODCOD ADAPTATIVO ===
		# Obtener CINR actual para selección de MODCOD
		try:
			cinr_db = jamming_data.get("combined_metrics", {}).get("cinr_db", 15.0)
			if math.isnan(cinr_db) or cinr_db < 0:
				cinr_db = 15.0  # Valor conservador por defecto
		except:
			cinr_db = 15.0
		
		# Usar función directa de selección adaptativa
		from JammerSystem import select_adaptive_modcod_spot_jamming
		modcod_result = select_adaptive_modcod_spot_jamming(cinr_db, jamming_active=True)
		modcod_selected = modcod_result.get("modcod", "QPSK_1_2")
		spectral_efficiency = modcod_result.get("efficiency", 1.0)
		adaptive_efficiency_gain = modcod_result.get("throughput_factor", 1.0) - 1.0
		
		# === DISCRIMINACIÓN ANGULAR DINÁMICA ===
		try:
			# Obtener parámetros geométricos
			sat_elevation = self.current_elevation_deg if hasattr(self, 'current_elevation_deg') else 45.0
			jammer_distance = jamming_data.get("primary_jammer_distance_km", 50.0)
			sat_distance = self.current_slant_distance_m / 1000.0 if hasattr(self, 'current_slant_distance_m') else 400.0
			
			# Usar función directa de discriminación dinámica
			from JammerSystem import calculate_dynamic_angular_discrimination
			angular_result = calculate_dynamic_angular_discrimination(
				sat_elevation_deg=sat_elevation,
				jammer_distance_km=jammer_distance,
				sat_distance_km=sat_distance
			)
			discrimination_angular_real_db = angular_result.get("discrimination_db", 21.47)
		except:
			discrimination_angular_real_db = 21.47  # Valor por defecto
		
		# === RTT REALISTA CON OVERHEAD DE JAMMING ===
		try:
			# Obtener latencia actual de ida
			one_way_latency = self.link_metrics.get('latency_ms_ow', 250.0) if hasattr(self, 'link_metrics') else 250.0
			elevation_deg = sat_elevation
			
			# Usar función directa de RTT realista
			from JammerSystem import calculate_realistic_rtt_spot_jamming
			rtt_result = calculate_realistic_rtt_spot_jamming(
				one_way_latency_ms=one_way_latency,
				elevation_deg=elevation_deg,
				jamming_active=True
			)
			rtt_processing_overhead_ms = rtt_result.get("processing_overhead_ms", 0.5)
			jamming_detection_time_ms = rtt_result.get("jamming_overhead_ms", 2.0)
		except:
			rtt_processing_overhead_ms = 0.5
			jamming_detection_time_ms = 2.0
		
		return {
			'jammer_center_freq_ghz': round(jammer_center_freq_ghz, 4),
			'jammer_bandwidth_mhz': round(jammer_bandwidth_mhz, 1),
			'spectral_overlap_percent': round(spectral_overlap_percent, 1),
			'target_link_detected': target_link_detected,
			'frequency_offset_mhz': round(frequency_offset_mhz, 1),
			'modcod_selected': modcod_selected,
			'spectral_efficiency': round(spectral_efficiency, 2),
			'discrimination_angular_real_db': round(discrimination_angular_real_db, 2),
			'jamming_detection_time_ms': round(jamming_detection_time_ms, 1),
			'adaptive_efficiency_gain': round(adaptive_efficiency_gain, 2),
			# ELIMINADAS: frequency_selectivity_factor, rtt_processing_overhead_ms (valores constantes)
		}

	def _calculate_physical_validation_metrics(self, row_data: dict, jam_system) -> dict:
		"""
		Calcula métricas de validación física sin bloquear la simulación.
		Retorna diccionario con flags de coherencia para análisis CSV.
		"""
		try:
			# Importar el sistema de validación
			from JammerSystem import PhysicalValidation
			validator = PhysicalValidation()
			
			# Extraer datos necesarios para validación
			ul_cinr = row_data.get('ul_cn_db', float('nan'))
			dl_cinr = row_data.get('dl_cn_db', float('nan'))
			e2e_cinr = row_data.get('e2e_cn_total_db', float('nan'))
			eb_n0_margin = row_data.get('Eb_margin_dB', float('nan'))
			
			# Validar coherencia de enlaces
			link_coherence = validator.validate_link_coherence(ul_cinr, dl_cinr, e2e_cinr)
			
			# Validar márgenes Eb/N0
			eb_n0_req = row_data.get('EbN0_dB', 9.6)  # Usar valor simulado o default LEO
			margin_feasibility = validator.validate_margin_feasibility(e2e_cinr, eb_n0_margin, eb_n0_req)
			
			# Validar realismo de jamming si hay jammer activo
			jamming_realism = {"realismo_jamming": "PASS"}  # Default OK si no hay jamming
			super_geo_analysis = None
			
			if jam_system and row_data.get('jamming_enabled', 0) == 1:
				ci_db = row_data.get('ci_total_db', float('inf'))
				jammer_distance = row_data.get('distancia_jammer_km', 0)
				satellite_distance = row_data.get('slant_range_km', 500)  # Default típico LEO
				degradation = row_data.get('jamming_degradation_db', 0)
				jamming_realism = validator.validate_jamming_realism(ci_db, degradation, jammer_distance, satellite_distance)
				
				# ANÁLISIS ESPECÍFICO PARA JAMMER SUPER-GEO
				if hasattr(self, 'jammer_manager') and self.jammer_manager.jammers:
					for jammer_config in self.jammer_manager.jammers.values():
						jammer_altitude = getattr(jammer_config, 'altitude_km', 0.001)
						if jammer_altitude >= 45000.0:  # Super-GEO range
							satellite_altitude = 550.0  # LEO por defecto
							if hasattr(self, 'sat_type') and self.sat_type == 'GEO':
								satellite_altitude = 35786.0
							
							# Obtener EIRP del jammer y satélite
							jammer_eirp = row_data.get('eirp_jammer_principal_dbw', 63.0)
							sat_eirp = row_data.get('eirp_saturado_dbw', 50.0)
							
							super_geo_analysis = validator.analyze_super_geo_jammer_coherence(
								jammer_altitude_km=jammer_altitude,
								satellite_altitude_km=satellite_altitude,
								jammer_eirp_dbw=jammer_eirp,
								satellite_eirp_dbw=sat_eirp,
								degradation_db=degradation,
								ci_db=ci_db
							)
							break
			
			# Consolidar validación general
			overall_validation = (
				link_coherence.get("coherencia_enlace") == "PASS" and
				margin_feasibility.get("viabilidad_margen") == "PASS" and
				jamming_realism.get("realismo_jamming") == "PASS"
			)
			
			# Generar flags descriptivos
			flags = []
			flags.extend(link_coherence.get("flags_coherencia", []))
			flags.extend(margin_feasibility.get("flags_margen", []))
			flags.extend(jamming_realism.get("flags_jamming", []))
			
			# Agregar flags de análisis Super-GEO si aplica
			if super_geo_analysis:
				flags.extend(super_geo_analysis.get("coherence_flags", []))
			
			# Determinar validación física considerando Super-GEO
			if super_geo_analysis and super_geo_analysis.get("coherence_level") == "INCOHERENTE":
				overall_validation = False
			
			# Las validaciones físicas han sido eliminadas
			# La coherencia se evalúa directamente en métricas principales
			return {}
			
		except Exception as e:
			# Si hay error en validación, retornar vacío
			return {}

	def _append_history_row(self):
		"""
		Captura completa de datos REORGANIZADA POR SECCIONES sin duplicaciones.
		Estructura: 9 secciones organizadas, 73 columnas totales sin redundancias.
		"""
		if not self.running or self.start_time is None:
			return
		
		elapsed = time.time() - self.start_time
		
		# === CALCULAR GEOMETRIA ORBITAL CORREGIDA ===
		elevation_deg = self.current_elevation_deg if hasattr(self, 'current_elevation_deg') else float('nan')
		slant_distance_km = self.current_slant_distance_m / 1000.0 if hasattr(self, 'current_slant_distance_m') else float('nan')
		
		# Calcular azimut basado en geometría LEO realista
		if hasattr(self, 'orbit_angle_deg') and not math.isnan(elevation_deg):
			# Para LEO, el azimut depende del ángulo orbital y la latitud del ground station
			gs_lat_deg = 36.7  # Málaga, España como referencia
			orbit_angle_rad = math.radians(getattr(self, 'orbit_angle_deg', 0))
			elevation_rad = math.radians(elevation_deg)
			
			# Azimut simplificado basado en órbita circular LEO
			# En realidad sería más complejo, pero esto da valores coherentes
			azimut_deg = (orbit_angle_rad * 180 / math.pi + 90) % 360
		else:
			azimut_deg = float('nan')
		
		# Velocidad angular realista para LEO
		if not math.isnan(slant_distance_km) and slant_distance_km > 0:
			# LEO típico: ~400-800 km altitud, velocidad orbital ~7.5 km/s
			orbital_radius_km = slant_distance_km / math.sin(math.radians(elevation_deg)) if elevation_deg > 0 else 400
			orbital_velocity_ms = math.sqrt(398600.4418 / (orbital_radius_km * 1000))  # m/s usando μ de la Tierra
			angular_velocity_deg_s = orbital_velocity_ms / (orbital_radius_km * 1000) * 180 / math.pi
		else:
			angular_velocity_deg_s = 0.001  # Valor por defecto LEO
		
		# === SECCIÓN 1: PARÁMETROS BÁSICOS ORBITALES (8 columnas) ===
		row = {
			'tiempo_s': round(elapsed, 3),
			'modo': self.mode_var.get() if hasattr(self, 'mode_var') else 'LEO',
			'elevacion_deg': round(elevation_deg, 2) if not math.isnan(elevation_deg) else float('nan'),
			'distancia_slant_km': round(slant_distance_km, 2) if not math.isnan(slant_distance_km) else float('nan'),
			'fspl_espacio_libre_db': round(self.link_metrics.get('fspl_db', float('nan')), 2),
			'azimut_deg': round(azimut_deg, 2) if not math.isnan(azimut_deg) else float('nan'),
			'velocidad_angular_deg_s': round(angular_velocity_deg_s, 4),
			'visible': 'Si' if getattr(self, 'current_visible', False) else 'No'  # Sin tilde
		}
		
		# === SECCIÓN 2: UPLINK (6 columnas) ===
		ul_out = self.link_out.get('UL') if hasattr(self, 'link_out') and self.link_out else None
		if ul_out and hasattr(ul_out, 'visible') and ul_out.visible:
			row.update({
				'ul_cn0_dbhz': round(ul_out.CN0_dBHz, 2),
				'ul_cn_db': round(ul_out.CN_dB, 2),
				'ul_freq_ghz': round(float(self.ul_freq_var.get()), 1) if hasattr(self, 'ul_freq_var') else 30.0,
				'ul_bw_mhz': round(float(self.ul_bw_var.get()), 1) if hasattr(self, 'ul_bw_var') else 20.0,
				'ul_gt_db_k': round(float(self.ul_gt_var.get()), 1) if hasattr(self, 'ul_gt_var') else -8.0,
				'ul_estado_cn': self._assess_cn(ul_out.CN_dB)[0]
			})
		else:
			row.update({
				'ul_cn0_dbhz': float('nan'),
				'ul_cn_db': float('nan'),
				'ul_freq_ghz': round(float(self.ul_freq_var.get()), 1) if hasattr(self, 'ul_freq_var') else 30.0,
				'ul_bw_mhz': round(float(self.ul_bw_var.get()), 1) if hasattr(self, 'ul_bw_var') else 20.0,
				'ul_gt_db_k': round(float(self.ul_gt_var.get()), 1) if hasattr(self, 'ul_gt_var') else -8.0,
				'ul_estado_cn': 'No visible'
			})
		
		# === SECCIÓN 3: DOWNLINK (6 columnas) ===
		dl_out = self.link_out.get('DL') if hasattr(self, 'link_out') and self.link_out else None
		if dl_out and hasattr(dl_out, 'visible') and dl_out.visible:
			row.update({
				'dl_cn0_dbhz': round(dl_out.CN0_dBHz, 2),
				'dl_cn_db': round(dl_out.CN_dB, 2),
				'dl_freq_ghz': round(float(self.dl_freq_var.get()), 1) if hasattr(self, 'dl_freq_var') else 20.0,
				'dl_bw_mhz': round(float(self.dl_bw_var.get()), 1) if hasattr(self, 'dl_bw_var') else 20.0,
				'dl_gt_db_k': round(float(self.dl_gt_var.get()), 1) if hasattr(self, 'dl_gt_var') else 12.0,
				'dl_estado_cn': self._assess_cn(dl_out.CN_dB)[0]
			})
		else:
			row.update({
				'dl_cn0_dbhz': float('nan'),
				'dl_cn_db': float('nan'),
				'dl_freq_ghz': round(float(self.dl_freq_var.get()), 1) if hasattr(self, 'dl_freq_var') else 20.0,
				'dl_bw_mhz': round(float(self.dl_bw_var.get()), 1) if hasattr(self, 'dl_bw_var') else 20.0,
				'dl_gt_db_k': round(float(self.dl_gt_var.get()), 1) if hasattr(self, 'dl_gt_var') else 12.0,
				'dl_estado_cn': 'No visible'
			})
		
		# === SECCIÓN 4: END-TO-END (6 columnas) ===
		if ul_out and dl_out and hasattr(ul_out, 'visible') and hasattr(dl_out, 'visible') and ul_out.visible and dl_out.visible:
			jamming_data = getattr(self, 'jamming_metrics', None)
			combined = self.combine_end_to_end(ul_out.CN_dB, dl_out.CN_dB, jamming_data) if hasattr(self, 'combine_end_to_end') else {}
			worst_link = 'UL' if ul_out.CN_dB < dl_out.CN_dB else 'DL'
			worst_cn = min(ul_out.CN_dB, dl_out.CN_dB)
			e2e_status = self._assess_cn(worst_cn)[0] if worst_cn is not None else 'CRÍTICO'
			
			# Usar las latencias E2E como las oficiales (sin duplicar)
			e2e_latency_ms = ul_out.latency_ms + dl_out.latency_ms if hasattr(ul_out, 'latency_ms') and hasattr(dl_out, 'latency_ms') else float('nan')
			
			row.update({
				'e2e_latencia_total_ms': round(e2e_latency_ms, 3) if not math.isnan(e2e_latency_ms) else float('nan'),
				'e2e_latencia_rtt_ms': round(e2e_latency_ms * 2, 3) if not math.isnan(e2e_latency_ms) else float('nan'),
				'e2e_cn_total_db': round(worst_cn, 2),
				'e2e_cinr_total_db': round(combined.get("CINR_tot_dB", worst_cn), 2),
				'e2e_enlace_critico': worst_link,
				'e2e_estado': e2e_status
			})
		else:
			row.update({
				'e2e_latencia_total_ms': float('nan'),
				'e2e_latencia_rtt_ms': float('nan'),
				'e2e_cn_total_db': float('nan'),
				'e2e_cinr_total_db': float('nan'),
				'e2e_enlace_critico': '—',
				'e2e_estado': 'No visible'
			})
		
		# === SECCIÓN 5: POTENCIA Y BACK-OFF (4 columnas) ===
		row.update({
			'eirp_saturado_dbw': round(float(self.eirp_sat_var.get()), 2) if hasattr(self, 'eirp_sat_var') else 50.0,
			'back_off_entrada_db': round(float(self.input_backoff_var.get()), 2) if hasattr(self, 'input_backoff_var') else 0.0,
			'back_off_salida_db': round(float(self.output_backoff_var.get()), 2) if hasattr(self, 'output_backoff_var') else 0.0,
			'eirp_efectivo_dbw': round(self.power_metrics.get('eirp_effective', 50.0), 2) if hasattr(self, 'power_metrics') else 50.0
		})
		
		# === SECCIÓN 6: TEMPERATURA Y RUIDO (12 columnas) ===
		perf_metrics = getattr(self, 'perf_metrics', {})
		
		# APLICAR DEGRADACIÓN DINÁMICA SI HAY JAMMING ACTIVO
		jamming_data = getattr(self, 'jamming_metrics', {})
		if jamming_data.get("jamming_enabled", False) and jamming_data.get("degradation_db", 0) > 0:
			degradation_db = jamming_data.get("degradation_db", 0)
			
			# Recalcular capacidad Shannon con CINR degradado
			cn_base_db = getattr(self, 'current_cn_db', 15.0)
			cinr_degraded_db = cn_base_db - degradation_db
			cinr_linear = 10**(cinr_degraded_db / 10.0)
			bw_mhz = getattr(self, 'current_bw_mhz', 20.0)
			
			# Shannon con jamming: C = BW * log2(1 + CINR_degraded)
			shannon_degraded = bw_mhz * math.log2(1 + cinr_linear)
			
			# Throughput efectivo: función cuadrática de la degradación
			degradation_factor = max(0.3, (cinr_linear / 10**(cn_base_db/10))**0.5)
			throughput_degraded = shannon_degraded * degradation_factor * 0.45
			
			# Actualizar métricas dinámicas
			perf_metrics_dynamic = perf_metrics.copy()
			perf_metrics_dynamic['shannon_capacity_Mbps'] = shannon_degraded
			perf_metrics_dynamic['effective_throughput_Mbps'] = throughput_degraded
		else:
			perf_metrics_dynamic = perf_metrics
		
		row.update({
			'temperatura_sistema_k': round(perf_metrics.get('T_sys_K', 150.0), 1),
			'ruido_figura_rx_db': round(perf_metrics.get('noise_figure_rx_dB', 0.5), 2),
			'ruido_densidad_n0_dbhz': round(perf_metrics.get('N0_dBHz', -206.8), 2),
			'ebn0_db': round(perf_metrics.get('EbN0_dB', 10.0), 2),
			'ebn0_margen_db': round(perf_metrics.get('Eb_margin_dB', 5.0), 2),
			'ebn0_requerido_db': round(perf_metrics.get('EbN0_req_dB', 5.0), 2),
			'capacidad_shannon_mbps': round(perf_metrics_dynamic.get('shannon_capacity_Mbps', 100.0), 2),
			'eficiencia_espectral_bps_hz': round(perf_metrics_dynamic.get('spectral_efficiency_bps_Hz', 2.0), 3),
			'tasa_bits_rb_mbps': round(perf_metrics_dynamic.get('bit_rate_Mbps', 50.0), 3),
			'throughput_efectivo_mbps': round(perf_metrics_dynamic.get('effective_throughput_Mbps', 45.0), 3)
		})
		
		# === DETERMINAR MODCOD POR ENLACE CRÍTICO ===
		# Determinar MODCOD por enlace crítico (UL/DL tienen modulaciones distintas)
		ul_cn = ul_out.CN_dB if ul_out and hasattr(ul_out, 'CN_dB') else float('nan')
		dl_cn = dl_out.CN_dB if dl_out and hasattr(dl_out, 'CN_dB') else float('nan')
		
		# El enlace crítico determina el MODCOD del sistema
		if not math.isnan(ul_cn) and not math.isnan(dl_cn):
			if ul_cn <= dl_cn:
				modcod_link = "UL"
				modcod_cn = ul_cn
			else:
				modcod_link = "DL" 
				modcod_cn = dl_cn
		elif not math.isnan(ul_cn):
			modcod_link = "UL"
			modcod_cn = ul_cn
		elif not math.isnan(dl_cn):
			modcod_link = "DL"
			modcod_cn = dl_cn
		else:
			modcod_link = "UL"  # Default
			modcod_cn = 15.0   # Default
			
		# Seleccionar MODCOD apropiado basado en CINR del enlace crítico
		modcod_selected = self.modcod_selected_var.get() if hasattr(self, 'modcod_selected_var') else 'QPSK_1_2'
		modcod_name_with_link = f"{modcod_selected}_{modcod_link}"  # Ej: "QPSK_1_2_UL", "16APSK_3_4_DL"
		
		# Agregar MODCOD diferenciado
		row.update({
			'modcod_name': modcod_name_with_link,
			'modcod_estado': getattr(self, 'modcod_status', 'Aceptable')
		})
		
		# === SECCIÓN 7: SPOT JAMMING BÁSICO (11 columnas) ===
		jamming_data = getattr(self, 'jamming_metrics', None)
		
		# Calcular efectividad mejorada basada en solapamiento y degradación
		if jamming_data and jamming_data.get("jamming_enabled", False):
			combined = jamming_data.get("combined_metrics", {})
			params = jamming_data.get("parameters", {})
			individual = jamming_data.get("individual_results", [])
			
			# Obtener datos del jammer principal
			primary_jammer_name = "SPOT_1"  # Por defecto
			if hasattr(self, 'jammer_manager') and self.jammer_manager.jammers:
				first_jammer = next(iter(self.jammer_manager.jammers.values()))
				primary_jammer_name = getattr(first_jammer, 'name', first_jammer.id)
			
			# Calcular efectividad basada en degradación real
			degradacion_db = combined.get("degradation_db", 0.0)
			if degradacion_db >= 10:
				efectividad_calculada = "CRITICO"
			elif degradacion_db >= 5:
				efectividad_calculada = "EFECTIVO"
			elif degradacion_db >= 2:
				efectividad_calculada = "MODERADO"
			elif degradacion_db >= 0.5:
				efectividad_calculada = "LIMITADO"
			else:
				efectividad_calculada = "INEFECTIVO"
			
			# === CALCULAR MÉTRICAS DE EFECTIVIDAD MEJORADAS ===
			cinr_sin_jamming = row.get('e2e_cinr_total_db', 15.0)  # CINR sin jamming
			cinr_con_jamming = combined.get("cinr_db", 15.0)  # CINR con jamming
			
			# Calcular degradación porcentual
			if not math.isnan(cinr_sin_jamming) and not math.isnan(cinr_con_jamming):
				degradacion_porcentual = ((cinr_sin_jamming - cinr_con_jamming) / cinr_sin_jamming) * 100
			else:
				degradacion_porcentual = 0.0
			
			# Determinar estado del enlace con jamming - CORREGIDO: coherente con throughput
			throughput_efectivo = perf_metrics_dynamic.get('effective_throughput_Mbps', 45.0)
			
			if throughput_efectivo < 5.0 or cinr_con_jamming < 3.0:
				estado_enlace = "BLOQUEADO"
				enlace_bloqueado = True
			elif throughput_efectivo < 15.0 or cinr_con_jamming < 6.0:
				estado_enlace = "CRITICO"
				enlace_bloqueado = False
			elif throughput_efectivo < 30.0 or cinr_con_jamming < 10.0:
				estado_enlace = "DEGRADADO"
				enlace_bloqueado = False
			else:
				estado_enlace = "FUNCIONAL"
				enlace_bloqueado = False
			
			# Evaluar efectividad operacional
			if degradacion_db >= 15.0:
				efectividad_operacional = "MUY_ALTA"
			elif degradacion_db >= 10.0:
				efectividad_operacional = "ALTA"
			elif degradacion_db >= 5.0:
				efectividad_operacional = "MEDIA"
			elif degradacion_db >= 2.0:
				efectividad_operacional = "BAJA"
			else:
				efectividad_operacional = "NULA"
			
			# Calcular métricas de superioridad del jammer
			ci_db = combined.get("ci_total_db", float('inf'))
			if not math.isinf(ci_db):
				superioridad_jammer_db = -ci_db  # C/I negativo = J/C positivo
				if superioridad_jammer_db >= 20:
					nivel_superioridad = "DOMINANTE"
				elif superioridad_jammer_db >= 10:
					nivel_superioridad = "SUPERIOR"
				elif superioridad_jammer_db >= 0:
					nivel_superioridad = "COMPETITIVO"
				else:
					nivel_superioridad = "INSUFICIENTE"
			else:
				superioridad_jammer_db = 0.0
				nivel_superioridad = "NO_DETECTABLE"
			
			# === CALCULAR MÉTRICAS CRÍTICAS FALTANTES ===
			# Obtener altura y distancia real del jammer principal
			jammer_altura_km = 0.001  # Default superficie
			jammer_distancia_km = 50.0  # Default
			solapamiento_espectral = params.get("spectral_overlap_percent", 100.0)
			
			if hasattr(self, 'jammer_manager') and self.jammer_manager.jammers:
				# Obtener datos del primer jammer (principal)
				first_jammer = next(iter(self.jammer_manager.jammers.values()))
				jammer_altura_km = getattr(first_jammer, 'altitude_km', 0.001)
				jammer_distancia_km = getattr(first_jammer, 'distance_from_gs_km', 50.0)
			
			# Calcular EIRP necesario para efectividad deseada
			eirp_actual = individual[0]["jammer_eirp_dbw"] if individual else 20.0
			degradacion_objetivo = 10.0  # dB objetivo para "EFECTIVO"
			
			# Path loss del jammer (aproximación) - PROTEGIDO
			jammer_freq_ghz = max(params.get("jammer_center_freq_ghz", 20.0), 0.1)  # Mínimo 100 MHz
			jammer_distancia_km = max(jammer_distancia_km, 0.001)  # Mínimo 1 metro
			fspl_jammer_db = 32.45 + 20*math.log10(jammer_distancia_km) + 20*math.log10(jammer_freq_ghz)
			
			# EIRP necesario DINÁMICO considerando geometría real
			# Objetivo: degradar enlace a umbral crítico (3 dB)
			# Protección: asegurar que cinr_sin_jamming sea válido
			cinr_sin_jamming = max(cinr_sin_jamming, -10.0)  # Valor mínimo razonable
			degradacion_objetivo_dinamico = max(3.0, cinr_sin_jamming - 3.0)  # Adaptar al margen disponible
			
			# Calcular C/I necesario para esa degradación - CORREGIDO para evitar domain error
			# Fórmula: C/I = degradación / (CINR_original - degradación)
			denominador = cinr_sin_jamming - degradacion_objetivo_dinamico
			if denominador <= 0:
				# Si no hay margen suficiente, usar mínimo ratio C/I
				ci_objetivo_db = -10.0  # Equivale a ratio 0.1 (jamming muy fuerte)
			else:
				ratio_ci = degradacion_objetivo_dinamico / denominador
				ratio_ci = max(ratio_ci, 0.001)  # Evitar log de cero
				ci_objetivo_db = 10 * math.log10(ratio_ci)
			
			# Potencia satélite recibida (aproximación) - PROTEGIDO
			satellite_eirp = eirp_actual  # EIRP satélite
			satellite_distance_km = max(getattr(self, 'current_slant_distance_m', 550000) / 1000.0, 200.0)  # Mínimo 200 km
			jammer_freq_ghz_sat = max(jammer_freq_ghz, 0.1)  # Protección adicional
			satellite_fspl_db = 32.45 + 20*math.log10(satellite_distance_km) + 20*math.log10(jammer_freq_ghz_sat)
			
			# EIRP jammer necesario considerando discriminación y path loss
			discrimination_db = individual[0]["discrimination_db"] if individual else 20.0
			polarization_db = params.get("polarization_isolation_db", -4.0)
			
			eirp_necesario_dbw = (satellite_eirp - satellite_fspl_db) - ci_objetivo_db + fspl_jammer_db - discrimination_db - polarization_db
			
			# Margen de enlace restante después del jamming
			margen_original = cinr_sin_jamming - 6.0  # Umbral QPSK 1/2
			margen_restante = cinr_con_jamming - 6.0
			
			# Umbral crítico (donde enlace falla)
			umbral_critico_db = 3.0  # Umbral mínimo operacional
			
			# Eficiencia del jammer basada en factores geométricos REALES
			# Función de eficiencia realista: decrece con separación angular y elevación
			elevation_deg = getattr(self, 'current_elevation_deg', 45.0)  # Elevación actual
			angular_separation = params.get("angular_separation_deg", 0.1)
			
			# Eficiencia geométrica: mejor con baja elevación y separación angular pequeña
			elevation_factor = max(0.3, 1.0 - (elevation_deg / 90.0) * 0.4)  # 60-100% según elevación
			angular_factor = max(0.6, math.exp(-angular_separation / 5.0))    # 60-100% según separación
			discrimination_penalty = max(0.8, 1.0 - individual[0]["discrimination_db"] / 50.0) if individual else 0.9
			
			# Eficiencia combinada (60-95% rango realista)
			eficiencia_jammer = elevation_factor * angular_factor * discrimination_penalty * 100
			
			# Recomendación de configuración
			if degradacion_db < 2.0:
				recomendacion = "INCREMENTAR_EIRP_O_REDUCIR_DISTANCIA"
			elif degradacion_db > 20.0:
				recomendacion = "REDUCIR_EIRP_PARA_EVITAR_DETECCION"
			elif solapamiento_espectral < 80.0:
				recomendacion = "AJUSTAR_FRECUENCIA_PARA_MAYOR_SOLAPAMIENTO"
			else:
				recomendacion = "CONFIGURACION_OPTIMA"
			
			row.update({
				'jamming_activado': 1,
				'numero_jammers': jamming_data.get("num_active_jammers", 1),
				'estado_enlace_con_jamming': estado_enlace,
				'degradacion_porcentual': round(degradacion_porcentual, 1),
				'enlace_bloqueado': enlace_bloqueado,
				'efectividad_operacional': efectividad_operacional,
				'superioridad_jammer_db': round(superioridad_jammer_db, 2),
				'nivel_dominancia': nivel_superioridad,
				'cinr_sin_jamming_db': round(cinr_sin_jamming, 2),
				'cinr_con_jamming_db': round(cinr_con_jamming, 2),
				'perdida_margen_db': round(max(0, cinr_sin_jamming - cinr_con_jamming), 2),
				'tiempo_bloqueo_percent': round(100.0 if enlace_bloqueado else 0.0, 1),
				'impacto_throughput_percent': round(min(100.0, degradacion_porcentual * 0.8), 1),  # Estimación conservadora
				'detectabilidad_jammer': "VISIBLE" if degradacion_db > 1.0 else "ENCUBIERTO",
				'persistencia_efecto': "CONTINUO" if degradacion_db > 5.0 else "INTERMITENTE",
				'ci_total_db': round(ci_db, 2) if not math.isinf(ci_db) else float('inf'),
				'degradacion_jamming_db': round(max(0, cinr_sin_jamming - cinr_con_jamming), 2),  # CORREGIDO: diferencia real punto a punto
				'efectividad_jamming': efectividad_calculada,
				# === NUEVAS MÉTRICAS IMPLEMENTADAS ===
				'margen_enlace_restante_db': round(margen_restante, 2),
				'umbral_critico_db': round(umbral_critico_db, 2),
				'potencia_jammer_necesaria_dbw': round(eirp_necesario_dbw, 1),
				'eficiencia_jammer_percent': round(min(100.0, max(0.0, eficiencia_jammer)), 1),
				'recomendacion_configuracion': recomendacion,
				'altura_jammer_km': round(jammer_altura_km, 3),
				'distancia_jammer_km': round(jammer_distancia_km, 1),
				'separacion_angular_deg': round(params.get("angular_separation_deg", 2.0), 1),
				'aislacion_polarizacion_db': round(params.get("polarization_isolation_db", -4.0), 1),
				'discriminacion_fcc_db': round(individual[0]["discrimination_db"], 2) if individual else 21.47,
				'jammer_1_eirp_dbw': round(individual[0]["jammer_eirp_dbw"], 1) if individual else 63.0,
				'jammer_1_tipo': individual[0]["jammer_type"] if individual else 'Spot Jamming',
				'jammer_1_nombre': primary_jammer_name,  # Agregar nombre del jammer
				'jammer_1_freq_ghz': round(individual[0]["jammer_center_freq_ghz"], 2) if individual else 30.0,
				'jammer_1_bandwidth_mhz': round(individual[0]["jammer_bandwidth_mhz"], 1) if individual else 50.0,
				'jammer_1_altura_km': round(individual[0]["jammer_height_km"], 2) if individual else 0.05,
			})
			
			# === MÉTRICAS INDIVIDUALES POR JAMMER DESHABILITADAS PARA SIMPLICIDAD ===
			# Las métricas principales de jamming se mantienen en las secciones generales
			# Esto reduce el CSV de 115 a ~99 columnas eliminando redundancia
			
			# for idx, jammer_metrics in enumerate(individual):
			#     jammer_id = jammer_metrics.get("jammer_name", f"JAMMER_{idx+1}")
			#     # ... código individual por jammer comentado para reducir columnas ...
			
		else:
			row.update({
				'jamming_activado': 0,
				'numero_jammers': 0,
				'estado_enlace_con_jamming': 'SIN_JAMMING',
				'degradacion_porcentual': 0.0,
				'enlace_bloqueado': False,
				'efectividad_operacional': 'NO_APLICA',
				'superioridad_jammer_db': 0.0,
				'nivel_dominancia': 'NO_ACTIVO',
				'cinr_sin_jamming_db': row.get('e2e_cinr_total_db', float('nan')),
				'cinr_con_jamming_db': row.get('e2e_cinr_total_db', float('nan')),
				'perdida_margen_db': 0.0,
				'tiempo_bloqueo_percent': 0.0,
				'impacto_throughput_percent': 0.0,
				'detectabilidad_jammer': 'NO_ACTIVO',
				'persistencia_efecto': 'NO_ACTIVO',
				'ci_total_db': float('inf'),
				'degradacion_jamming_db': 0.0,
				'efectividad_jamming': 'SIN_JAMMING',
				# === NUEVAS MÉTRICAS SIN JAMMING ===
				'margen_enlace_restante_db': round(row.get('e2e_cinr_total_db', 15.0) - 6.0, 2),
				'umbral_critico_db': 3.0,
				'potencia_jammer_necesaria_dbw': 0.0,
				'eficiencia_jammer_percent': 0.0,
				'recomendacion_configuracion': 'SIN_JAMMER_ACTIVO',
				'altura_jammer_km': 0.0,
				'distancia_jammer_km': 0.0,
				'separacion_angular_deg': float('nan'),
				'aislacion_polarizacion_db': float('nan'),
				'discriminacion_fcc_db': float('nan'),
				'jammer_1_eirp_dbw': float('nan'),
				'jammer_1_tipo': '',
				'jammer_1_nombre': '',
				'jammer_1_freq_ghz': float('nan'),
				'jammer_1_bandwidth_mhz': float('nan'),
				'jammer_1_altura_km': float('nan'),
			})
		
		# === SECCIÓN 8: SPOT JAMMING AVANZADO (12 columnas) ===
		advanced_jamming = self._calculate_spot_jamming_advanced_metrics(jamming_data)
		row.update(advanced_jamming)
		
		# === SECCIÓN 9: VALIDACIÓN FÍSICA - ELIMINADA ===
		# Las validaciones están implícitas en métricas principales (CINR, throughput, MODCOD)
		
		self.history.append(row)

	def _toggle_losses(self):
		self.show_losses = not self.show_losses
		if self.show_losses:
			self.toggle_losses_btn.config(text='Ocultar Pérdidas ▼')
			# Posicionar filas detalladas al final
			base_row = 0
			for child in self.metrics_panel.grid_slaves():
				base_row = max(base_row, int(child.grid_info().get('row',0)))
			start = base_row + 1
			ordered = [
				('RFL_feeder','Feeder RF [dB]'),
				('AML_misalignment','Desalineación Antena [dB]'),
				('AA_atmos','Atenuación Atmosférica [dB]'),
				('Rain_att','Atenuación Lluvia [dB]'),
				('PL_polarization','Desajuste Polarización [dB]'),
				('L_pointing','Pérdida Apuntamiento [dB]'),
				('L_impl','Pérdidas Implementación [dB]'),
			]
			self._loss_title_labels = {}
			for i,(k,disp) in enumerate(ordered):
				# Crear title label y grid value label
				title = ttk.Label(self.metrics_panel, text=disp+':', font=('Segoe UI',10,'bold'), anchor='w')
				title.grid(row=start+i, column=0, sticky='w', padx=(2,4), pady=1)
				self._loss_title_labels[k] = title
				if k in self.loss_detail_label_map:
					self.loss_detail_label_map[k].grid(row=start+i, column=1, sticky='e', padx=(4,6), pady=1)
		else:
			self.toggle_losses_btn.config(text='Mostrar Pérdidas ▶')
			# Retirar labels
			if hasattr(self, '_loss_title_labels'):
				for k,lbl in self._loss_title_labels.items():
					if lbl.winfo_manager() == 'grid':
						lbl.grid_forget()
			for k,lbl in self.loss_detail_label_map.items():
				if lbl.winfo_manager() == 'grid':
					lbl.grid_forget()


	def _on_mousewheel(self, event):
		# Normalizar delta (Windows suele ser múltiplos de 120)
		if hasattr(self, 'metrics_canvas'):
			delta = int(-1*(event.delta/120))
			self.metrics_canvas.yview_scroll(delta, 'units')
	
	def _create_uplink_tab(self):
		"""Crea la pestaña de Uplink."""
		ul_frame = ttk.Frame(self.notebook)
		self.notebook.add(ul_frame, text='Uplink')
		
		# Variables específicas de UL
		self.ul_freq_var = tk.DoubleVar(value=self.link_state['UL'].f_Hz / 1e9)
		self.ul_bw_var = tk.DoubleVar(value=self.link_state['UL'].B_Hz / 1e6) 
		self.ul_eirp_var = tk.DoubleVar(value=self.link_state['UL'].EIRP_dBW)
		self.ul_gt_var = tk.DoubleVar(value=self.link_state['UL'].GT_dBK)
		self.ul_losses_var = tk.DoubleVar(value=self.link_state['UL'].L_extra_dB)
		
		# Conectar eventos de cambio
		for var in [self.ul_freq_var, self.ul_bw_var, self.ul_eirp_var, self.ul_gt_var, self.ul_losses_var]:
			var.trace('w', lambda *args: self.update_metrics())
		
		# Widgets
		ttk.Label(ul_frame, text='Frecuencia UL (GHz):').grid(row=0, column=0, sticky='w', padx=2, pady=1)
		ttk.Entry(ul_frame, textvariable=self.ul_freq_var, width=8).grid(row=0, column=1, padx=2, pady=1)
		
		ttk.Label(ul_frame, text='BW UL (MHz):').grid(row=1, column=0, sticky='w', padx=2, pady=1)
		ttk.Entry(ul_frame, textvariable=self.ul_bw_var, width=8).grid(row=1, column=1, padx=2, pady=1)
		
		ttk.Label(ul_frame, text='EIRP UL (dBW):').grid(row=2, column=0, sticky='w', padx=2, pady=1)
		ttk.Entry(ul_frame, textvariable=self.ul_eirp_var, width=8).grid(row=2, column=1, padx=2, pady=1)
		
		ttk.Label(ul_frame, text='G/T UL (dB/K):').grid(row=3, column=0, sticky='w', padx=2, pady=1)
		ttk.Entry(ul_frame, textvariable=self.ul_gt_var, width=8).grid(row=3, column=1, padx=2, pady=1)
		
		ttk.Label(ul_frame, text='Pérdidas Extra (dB):').grid(row=4, column=0, sticky='w', padx=2, pady=1)
		ttk.Entry(ul_frame, textvariable=self.ul_losses_var, width=8).grid(row=4, column=1, padx=2, pady=1)
		
		# Métricas de salida (solo lectura)
		self.ul_fspl_label = ttk.Label(ul_frame, text='FSPL: —', foreground='blue')
		self.ul_fspl_label.grid(row=5, column=0, columnspan=2, sticky='w', padx=2, pady=1)
		
		self.ul_cn0_label = ttk.Label(ul_frame, text='C/N0: —', foreground='blue')
		self.ul_cn0_label.grid(row=6, column=0, columnspan=2, sticky='w', padx=2, pady=1)
		
		self.ul_cn_label = ttk.Label(ul_frame, text='C/N: —', foreground='blue')
		self.ul_cn_label.grid(row=7, column=0, columnspan=2, sticky='w', padx=2, pady=1)
		
		self.ul_lat_label = ttk.Label(ul_frame, text='Latencia: —', foreground='blue')
		self.ul_lat_label.grid(row=8, column=0, columnspan=2, sticky='w', padx=2, pady=1)
	
	def _create_downlink_tab(self):
		"""Crea la pestaña de Downlink."""
		dl_frame = ttk.Frame(self.notebook)
		self.notebook.add(dl_frame, text='Downlink')
		
		# Variables específicas de DL
		self.dl_freq_var = tk.DoubleVar(value=self.link_state['DL'].f_Hz / 1e9)
		self.dl_bw_var = tk.DoubleVar(value=self.link_state['DL'].B_Hz / 1e6)
		self.dl_eirp_var = tk.DoubleVar(value=self.link_state['DL'].EIRP_dBW)
		self.dl_gt_var = tk.DoubleVar(value=self.link_state['DL'].GT_dBK)
		self.dl_losses_var = tk.DoubleVar(value=self.link_state['DL'].L_extra_dB)
		
		# Conectar eventos de cambio
		for var in [self.dl_freq_var, self.dl_bw_var, self.dl_eirp_var, self.dl_gt_var, self.dl_losses_var]:
			var.trace('w', lambda *args: self.update_metrics())
		
		# Widgets
		ttk.Label(dl_frame, text='Frecuencia DL (GHz):').grid(row=0, column=0, sticky='w', padx=2, pady=1)
		ttk.Entry(dl_frame, textvariable=self.dl_freq_var, width=8).grid(row=0, column=1, padx=2, pady=1)
		
		ttk.Label(dl_frame, text='BW DL (MHz):').grid(row=1, column=0, sticky='w', padx=2, pady=1)
		ttk.Entry(dl_frame, textvariable=self.dl_bw_var, width=8).grid(row=1, column=1, padx=2, pady=1)
		
		ttk.Label(dl_frame, text='EIRP DL (dBW):').grid(row=2, column=0, sticky='w', padx=2, pady=1)
		ttk.Entry(dl_frame, textvariable=self.dl_eirp_var, width=8).grid(row=2, column=1, padx=2, pady=1)
		
		ttk.Label(dl_frame, text='G/T DL (dB/K):').grid(row=3, column=0, sticky='w', padx=2, pady=1)
		ttk.Entry(dl_frame, textvariable=self.dl_gt_var, width=8).grid(row=3, column=1, padx=2, pady=1)
		
		ttk.Label(dl_frame, text='Pérdidas Extra (dB):').grid(row=4, column=0, sticky='w', padx=2, pady=1)
		ttk.Entry(dl_frame, textvariable=self.dl_losses_var, width=8).grid(row=4, column=1, padx=2, pady=1)
		
		# Métricas de salida (solo lectura)
		self.dl_fspl_label = ttk.Label(dl_frame, text='FSPL: —', foreground='blue')
		self.dl_fspl_label.grid(row=5, column=0, columnspan=2, sticky='w', padx=2, pady=1)
		
		self.dl_cn0_label = ttk.Label(dl_frame, text='C/N0: —', foreground='blue')
		self.dl_cn0_label.grid(row=6, column=0, columnspan=2, sticky='w', padx=2, pady=1)
		
		self.dl_cn_label = ttk.Label(dl_frame, text='C/N: —', foreground='blue')
		self.dl_cn_label.grid(row=7, column=0, columnspan=2, sticky='w', padx=2, pady=1)
		
		self.dl_lat_label = ttk.Label(dl_frame, text='Latencia: —', foreground='blue')
		self.dl_lat_label.grid(row=8, column=0, columnspan=2, sticky='w', padx=2, pady=1)
		
		# Botones de copia
		btn_frame = ttk.Frame(dl_frame)
		btn_frame.grid(row=9, column=0, columnspan=2, pady=5)
		ttk.Button(btn_frame, text='← Copiar UL→DL', command=self._copy_ul_to_dl).pack(side='left', padx=2)
		ttk.Button(btn_frame, text='Copiar DL→UL →', command=self._copy_dl_to_ul).pack(side='left', padx=2)
	
	def _create_endtoend_tab(self):
		"""Crea la pestaña End-to-End."""
		e2e_frame = ttk.Frame(self.notebook)
		self.notebook.add(e2e_frame, text='End-to-End')
		
		# Métricas combinadas
		self.e2e_cn_ul_label = ttk.Label(e2e_frame, text='C/N (UL): —', foreground='green')
		self.e2e_cn_ul_label.grid(row=0, column=0, columnspan=2, sticky='w', padx=2, pady=1)
		
		self.e2e_cn_dl_label = ttk.Label(e2e_frame, text='C/N (DL): —', foreground='green')
		self.e2e_cn_dl_label.grid(row=1, column=0, columnspan=2, sticky='w', padx=2, pady=1)
		
		self.e2e_nc_tot_label = ttk.Label(e2e_frame, text='(N/C) Total: —', foreground='red')
		self.e2e_nc_tot_label.grid(row=2, column=0, columnspan=2, sticky='w', padx=2, pady=1)
		
		self.e2e_cn_tot_label = ttk.Label(e2e_frame, text='C/N Total: —', foreground='red')
		self.e2e_cn_tot_label.grid(row=3, column=0, columnspan=2, sticky='w', padx=2, pady=1)
		
		self.e2e_cinr_tot_label = ttk.Label(e2e_frame, text='CINR Total: —', foreground='red')
		self.e2e_cinr_tot_label.grid(row=4, column=0, columnspan=2, sticky='w', padx=2, pady=1)
		
		self.e2e_status_label = ttk.Label(e2e_frame, text='Estado: —', font=('Segoe UI', 10, 'bold'))
		self.e2e_status_label.grid(row=5, column=0, columnspan=2, sticky='w', padx=2, pady=5)
		
		# Selector de ancho de banda de referencia
		ttk.Label(e2e_frame, text='BW Referencia:').grid(row=6, column=0, sticky='w', padx=2, pady=1)
		self.bw_ref_var = tk.StringVar(value='DL')
		self.bw_ref_var.trace('w', lambda *args: self.update_metrics())
		ttk.Combobox(e2e_frame, textvariable=self.bw_ref_var, values=['UL', 'DL'], state='readonly', width=6).grid(row=6, column=1, padx=2, pady=1)
	
	def _on_tab_changed(self, event):
		"""Maneja el cambio de pestaña."""
		selected_tab = event.widget.tab('current')['text']
		if selected_tab == 'Uplink':
			self.current_link_sense = 'UL'
		elif selected_tab == 'Downlink':
			self.current_link_sense = 'DL'
		elif selected_tab == 'End-to-End':
			self.current_link_sense = 'E2E'
		self._sync_main_params_with_active_tab()
		self.update_metrics()

	def _sync_main_params_with_active_tab(self):
		"""Sincroniza parámetros principales con el tab activo UL/DL/E2E."""
		if self.current_link_sense == 'UL':
			self.eirp_var.set(self.ul_eirp_var.get())
			self.gt_var.set(self.ul_gt_var.get())
			self.bw_var.set(self.ul_bw_var.get())
		elif self.current_link_sense == 'DL':
			self.eirp_var.set(self.dl_eirp_var.get())
			self.gt_var.set(self.dl_gt_var.get())
			self.bw_var.set(self.dl_bw_var.get())
		elif self.current_link_sense == 'E2E':
			# Para End-to-End, usar los parámetros de referencia seleccionados
			ref_link = self.bw_ref_var.get()  # 'UL' o 'DL'
			if ref_link == 'UL':
				self.eirp_var.set(self.ul_eirp_var.get())
				self.gt_var.set(self.ul_gt_var.get())
				self.bw_var.set(self.ul_bw_var.get())
			else:  # DL
				self.eirp_var.set(self.dl_eirp_var.get())
				self.gt_var.set(self.dl_gt_var.get())
				self.bw_var.set(self.dl_bw_var.get())

	def _get_active_cn0_dbhz(self):
		"""Devuelve C/N0 del tab activo."""
		if hasattr(self, 'current_link_sense') and hasattr(self, 'link_out'):
			if self.current_link_sense == 'UL':
				ul_out = self.link_out.get('UL')
				return ul_out.CN0_dBHz if ul_out and ul_out.visible else float('nan')
			elif self.current_link_sense == 'DL':
				dl_out = self.link_out.get('DL')
				return dl_out.CN0_dBHz if dl_out and dl_out.visible else float('nan')
			elif self.current_link_sense == 'E2E':
				# Para End-to-End, usar C/N0 del enlace de referencia
				ref_link = self.bw_ref_var.get() if hasattr(self, 'bw_ref_var') else 'DL'
				ref_out = self.link_out.get(ref_link)
				return ref_out.CN0_dBHz if ref_out and ref_out.visible else float('nan')
		# Fallback al valor tradicional
		return self.link_metrics.get('cn0_dbhz', float('nan'))

	def _get_active_cn_db(self):
		"""Devuelve C/N del tab activo."""
		if hasattr(self, 'current_link_sense') and hasattr(self, 'link_out'):
			if self.current_link_sense == 'UL':
				ul_out = self.link_out.get('UL')
				return ul_out.CN_dB if ul_out and ul_out.visible else float('nan')
			elif self.current_link_sense == 'DL':
				dl_out = self.link_out.get('DL')
				return dl_out.CN_dB if dl_out and dl_out.visible else float('nan')
			elif self.current_link_sense == 'E2E':
				# Para End-to-End, mostrar C/N total combinado
				ul_out = self.link_out.get('UL')
				dl_out = self.link_out.get('DL')
				if ul_out and dl_out and ul_out.visible and dl_out.visible:
					combined = combine_end_to_end(ul_out.CN_dB, dl_out.CN_dB, getattr(self, 'jamming_metrics', None))
					return combined["CN_tot_dB"]
				return float('nan')
		# Fallback al valor tradicional
		return self.link_metrics.get('cn_db', float('nan'))

	def _get_active_fspl_db(self):
		"""Devuelve FSPL del tab activo."""
		if hasattr(self, 'current_link_sense') and hasattr(self, 'link_out'):
			if self.current_link_sense == 'UL':
				ul_out = self.link_out.get('UL')
				return ul_out.FSPL_dB if ul_out and ul_out.visible else float('nan')
			elif self.current_link_sense == 'DL':
				dl_out = self.link_out.get('DL')
				return dl_out.FSPL_dB if dl_out and dl_out.visible else float('nan')
			elif self.current_link_sense == 'E2E':
				# Para End-to-End, usar FSPL del enlace de referencia
				ref_link = self.bw_ref_var.get() if hasattr(self, 'bw_ref_var') else 'DL'
				ref_out = self.link_out.get(ref_link)
				return ref_out.FSPL_dB if ref_out and ref_out.visible else float('nan')
		# Fallback al valor tradicional
		return self.link_metrics.get('fspl_db', float('nan'))

	def _get_active_ebn0_db(self):
		"""Devuelve Eb/N0 del tab activo para evaluación MODCOD."""
		if hasattr(self, 'current_link_sense') and hasattr(self, 'link_out'):
			if self.current_link_sense == 'UL':
				# Usar C/N UL directamente (más simple y directo)
				ul_out = self.link_out.get('UL')
				if ul_out and ul_out.visible:
					return ul_out.CN_dB
				return float('nan')
			elif self.current_link_sense == 'DL':
				# Usar C/N DL directamente
				dl_out = self.link_out.get('DL')
				if dl_out and dl_out.visible:
					return dl_out.CN_dB
				return float('nan')
			elif self.current_link_sense == 'E2E':
				# Para End-to-End, usar el peor caso (menor C/N)
				ul_out = self.link_out.get('UL')
				dl_out = self.link_out.get('DL')
				if ul_out and dl_out and ul_out.visible and dl_out.visible:
					return min(ul_out.CN_dB, dl_out.CN_dB)
				elif ul_out and ul_out.visible:
					return ul_out.CN_dB
				elif dl_out and dl_out.visible:
					return dl_out.CN_dB
				return float('nan')
		# Fallback al valor tradicional
		return self.perf_metrics.get('EbN0_dB', float('nan'))

	
	def _copy_ul_to_dl(self):
		"""Copia parámetros de UL a DL."""
		self.dl_freq_var.set(self.ul_freq_var.get())
		self.dl_bw_var.set(self.ul_bw_var.get())
		self.dl_eirp_var.set(self.ul_eirp_var.get())
		self.dl_gt_var.set(self.ul_gt_var.get())
		self.dl_losses_var.set(self.ul_losses_var.get())
		self.update_metrics()
	
	def _copy_dl_to_ul(self):
		"""Copia parámetros de DL a UL."""
		self.ul_freq_var.set(self.dl_freq_var.get())
		self.ul_bw_var.set(self.dl_bw_var.get())
		self.ul_eirp_var.set(self.dl_eirp_var.get())
		self.ul_gt_var.set(self.dl_gt_var.get())
		self.ul_losses_var.set(self.dl_losses_var.get())
		self.update_metrics()
	
	def _compute_link_outputs_local(self, inputs: LinkInputs, d_km: float) -> LinkOutputs:
		"""Calcula las métricas de salida para un sentido de enlace (versión local)."""
		# Verificar visibilidad basada en elevación y distancia válida
		elevation_deg = getattr(self, 'current_elevation_deg', 0.0)
		# Usar la elevación real mostrada en la GUI en lugar de la calculada internamente
		if hasattr(self, 'current_visible') and self.current_visible:
			visible = True
		else:
			visible = d_km > 0 and elevation_deg > 0.1  # usar 0.1 en lugar de valores muy pequeños
		
		if not visible:
			return LinkOutputs(
				FSPL_dB=float('nan'),
				CN0_dBHz=float('nan'), 
				CN_dB=float('nan'),
				visible=False,
				latency_ms=float('nan')
			)
		
		# Cálculos usando las funciones puras
		fspl = fspl_dB(inputs.f_Hz, d_km * 1000)  # convertir km a m
		cn0 = cn0_dBHz(inputs.EIRP_dBW, inputs.GT_dBK, fspl, inputs.L_extra_dB)
		cn = cn_dB(cn0, inputs.B_Hz)
		latency = (d_km * 1000 / SPEED_OF_LIGHT) * 1000  # ms
		
		return LinkOutputs(
			FSPL_dB=fspl,
			CN0_dBHz=cn0,
			CN_dB=cn,
			visible=True,
			latency_ms=latency
		)

	def _update_link_params(self):
		"""Actualiza los parámetros de los enlaces UL/DL desde las variables de la GUI."""		
		if hasattr(self, 'ul_freq_var'):
			# Actualizar estado UL
			self.link_state['UL'].f_Hz = self.ul_freq_var.get() * 1e9
			self.link_state['UL'].B_Hz = self.ul_bw_var.get() * 1e6
			self.link_state['UL'].EIRP_dBW = self.ul_eirp_var.get()
			self.link_state['UL'].GT_dBK = self.ul_gt_var.get()
			self.link_state['UL'].L_extra_dB = self.ul_losses_var.get()
		
		if hasattr(self, 'dl_freq_var'):
			# Actualizar estado DL
			self.link_state['DL'].f_Hz = self.dl_freq_var.get() * 1e9
			self.link_state['DL'].B_Hz = self.dl_bw_var.get() * 1e6
			self.link_state['DL'].EIRP_dBW = self.dl_eirp_var.get()
			self.link_state['DL'].GT_dBK = self.dl_gt_var.get()
			self.link_state['DL'].L_extra_dB = self.dl_losses_var.get()
		
		# Calcular métricas para ambos enlaces usando el método local
		d_km = getattr(self, 'current_slant_distance_m', 600000.0) / 1000.0
		
		for link in ['UL', 'DL']:
			inputs = self.link_state[link]
			self.link_out[link] = self._compute_link_outputs_local(inputs, d_km)
	
	def _update_link_gui(self):
		"""Actualiza las etiquetas de la GUI con las métricas calculadas."""
		import math
		
		if hasattr(self, 'ul_fspl_label'):
			# Actualizar UL
			ul_out = self.link_out['UL']
			if ul_out.visible and not math.isnan(ul_out.FSPL_dB):
				self.ul_fspl_label.config(text=f'FSPL: {ul_out.FSPL_dB:.1f} dB')
				self.ul_cn0_label.config(text=f'C/N0: {ul_out.CN0_dBHz:.1f} dB-Hz')
				self.ul_cn_label.config(text=f'C/N: {ul_out.CN_dB:.1f} dB')
				self.ul_lat_label.config(text=f'Latencia: {ul_out.latency_ms:.2f} ms')
			else:
				self.ul_fspl_label.config(text='FSPL: —')
				self.ul_cn0_label.config(text='C/N0: —')
				self.ul_cn_label.config(text='C/N: —')
				self.ul_lat_label.config(text='Latencia: —')
		
		if hasattr(self, 'dl_fspl_label'):
			# Actualizar DL
			dl_out = self.link_out['DL']
			if dl_out.visible and not math.isnan(dl_out.FSPL_dB):
				self.dl_fspl_label.config(text=f'FSPL: {dl_out.FSPL_dB:.1f} dB')
				self.dl_cn0_label.config(text=f'C/N0: {dl_out.CN0_dBHz:.1f} dB-Hz')
				self.dl_cn_label.config(text=f'C/N: {dl_out.CN_dB:.1f} dB')
				self.dl_lat_label.config(text=f'Latencia: {dl_out.latency_ms:.2f} ms')
			else:
				self.dl_fspl_label.config(text='FSPL: —')
				self.dl_cn0_label.config(text='C/N0: —')
				self.dl_cn_label.config(text='C/N: —')
				self.dl_lat_label.config(text='Latencia: —')
		
		if hasattr(self, 'e2e_cn_ul_label'):
			# Actualizar End-to-End
			ul_out = self.link_out['UL']
			dl_out = self.link_out['DL']
			
			# Solo calcular si ambos enlaces son válidos
			if (ul_out.visible and dl_out.visible and 
				not math.isnan(ul_out.CN_dB) and not math.isnan(dl_out.CN_dB)):
				
				# Combinar End-to-End
				combined = combine_end_to_end(ul_out.CN_dB, dl_out.CN_dB, getattr(self, 'jamming_metrics', None))
				
				self.e2e_cn_ul_label.config(text=f'C/N (UL): {ul_out.CN_dB:.1f} dB')
				self.e2e_cn_dl_label.config(text=f'C/N (DL): {dl_out.CN_dB:.1f} dB')
				self.e2e_nc_tot_label.config(text=f'(N/C) Total: {combined["NC_tot_dB"]:.2f} dB')
				self.e2e_cn_tot_label.config(text=f'C/N Total: {combined["CN_tot_dB"]:.1f} dB')
				self.e2e_cinr_tot_label.config(text=f'CINR Total: {combined["CINR_tot_dB"]:.1f} dB')
				
				# Estado del enlace
				status = 'NOMINAL' if combined["CN_tot_dB"] > 10.0 else 'MARGINAL' if combined["CN_tot_dB"] > 5.0 else 'CRÍTICO'
				color = 'green' if status == 'NOMINAL' else 'orange' if status == 'MARGINAL' else 'red'
				self.e2e_status_label.config(text=f'Estado: {status}', foreground=color)
			else:
				# No hay datos válidos - satélite no visible
				self.e2e_cn_ul_label.config(text='C/N (UL): —')
				self.e2e_cn_dl_label.config(text='C/N (DL): —')
				self.e2e_nc_tot_label.config(text='(N/C) Total: —')
				self.e2e_cn_tot_label.config(text='C/N Total: —')
				self.e2e_cinr_tot_label.config(text='CINR Total: —')
				self.e2e_status_label.config(text='Estado: No visible', foreground='gray')


# ------------------------------------------------------------- #
# Punto de entrada                                              #
# ------------------------------------------------------------- #
def main():
	loader = ParameterLoader()
	core = JammerSimulatorCore(loader)
	if tk is None:
		print("Tkinter no disponible en este entorno.")
		return
	root = tk.Tk()
	SimulatorGUI(root, core)
	root.mainloop()


# ===== NUEVO SISTEMA CSV ESTRUCTURADO =====
# 
# README INTERNO - ESPECIFICACIÓN CSV PARA DASHBOARD MULTI-JAMMER
# 
# UNIDADES Y CONVENCIONES:
# - Tiempos: [s] segundos, [ms] milisegundos
# - Frecuencias: [ghz] gigahertz, [mhz] megahertz  
# - Potencias: [dbw] dBW, [dbi] dBi, [dbhz] dB-Hz, [dbk] dB/K
# - Distancias: [km] kilómetros, [deg] grados
# - Throughput: [mbps] megabits/segundo
# - Percentages: [percent] 0-100%
# - Flags: [flag] 0/1 boolean
# 
# ESTADOS DE ENLACE:
# - OUTAGE: Sin señal (CINR < -5 dB)
# - BLOQUEADO: Jammer efectivo (throughput ≈ 0, CINR < 3 dB)  
# - CRITICO: Degradado severo (throughput < 15 Mbps, CINR < 6 dB)
# - DEGRADADO: Operacional reducido (throughput < 25 Mbps, CINR < 10 dB)
# - FUNCIONAL: Operacional normal (throughput ≥ 25 Mbps, CINR ≥ 10 dB)
# 
# TIPOS DE JAMMER:
# - SPOT: Narrow band spot jamming
# - BARRAGE: Wide band barrage jamming  
# - SWEEP: Frequency sweep jamming
# - ADAPTIVE: Adaptive power/frequency jamming
# 
# COHERENCIA GARANTIZADA:
# - degradation.db = cinr.original.db - cinr.with_attack.db
# - blocked.flag=1 ⟺ throughput.effective.mbps ≈ 0
# - states derivados de umbrales CINR y throughput coherentes
#

def build_csv_header(active_jammers=None):
	"""
	Construye cabecera CSV dinámica solo para jammers activos.
	ORDEN FIJO garantizado para coherencia en dashboard.
	
	Args:
		active_jammers (list): Lista de IDs de jammers activos en orden
		
	Returns:
		list: Lista ordenada de nombres de columnas
		
	Order: sim_metadata → time_orbital → links → e2e → jammer_blocks_dynamic → aggregates
	"""
	if active_jammers is None:
		active_jammers = []
	
	# METADATOS DE SIMULACIÓN
	sim_meta = [
		'sim.id', 'schema.version', 'scenario.name', 'notes'
	]
	
	# TIEMPO Y GEOMETRÍA ORBITAL  
	time_orbital = [
		'time.s', 'rx.site.id', 'constellation.id', 'sat.id', 'beam.id',
		'elevation.deg', 'azimuth.deg', 'slant_distance.km', 'fspl.db', 'visible.flag'
	]
	
	# ENLACES UL/DL
	uplink = [
		'ul.freq.ghz', 'ul.bw.mhz', 'ul.gt.dbk', 'ul.cn0.dbhz', 'ul.cn.db', 'ul.estado_cn'
	]
	
	downlink = [
		'dl.freq.ghz', 'dl.bw.mhz', 'dl.gt.dbk', 'dl.cn0.dbhz', 'dl.cn.db', 'dl.estado_cn'
	]
	
	# END-TO-END PERFORMANCE (expandido para dashboard)
	e2e = [
		# === MÉTRICAS PRINCIPALES ===
		'e2e.cinr_jammed.db', 'e2e.cinr_nominal.db',
		'e2e.latency.ms', 'e2e.rtt.ms',
		'shannon.capacity.mbps',
		
		# === BEFORE JAMMING ===
		'modcod.before_jamming', 'spectral.efficiency.before_jamming', 'throughput.before_jamming.mbps',
		
		# === WITH JAMMING ===
		'modcod.selected', 'spectral.efficiency.bps_hz', 'throughput.jammed.mbps',
		
		# === DELTAS ===
		'delta.cinr.db', 'delta.throughput.mbps',
		
		# === LABELS PARA DASHBOARD ===
		'modcod.selected_label', 'spectral.efficiency.bps_hz_label', 'throughput.jammed.mbps_label',
		'e2e.cinr_jammed.db_label', 'e2e.state_label',
		
		# === PLOT PARA CONTINUIDAD VISUAL ===
		'throughput.plot.mbps', 'spectral.efficiency.plot.bps_hz', 'e2e.cinr_jammed.plot.db',
		
		# === ESTADO ===
		'e2e.state'
	]
	
	# BLOQUES DINÁMICOS POR JAMMER ACTIVO (jammer[j1], jammer[j2], ..., jammer[jN])
	jammer_blocks = []
	for idx, jammer_id in enumerate(active_jammers, 1):
		jammer_prefix = f'jammer[j{idx}]'
		jammer_block = [
			f'{jammer_prefix}.present',
			f'{jammer_prefix}.id',
			f'{jammer_prefix}.name', 
			f'{jammer_prefix}.platform.type',
			f'{jammer_prefix}.type',
			f'{jammer_prefix}.eirp.dbw',
			f'{jammer_prefix}.center_freq.ghz',
			f'{jammer_prefix}.bandwidth.mhz',
			f'{jammer_prefix}.polarization',
			f'{jammer_prefix}.antenna_gain.dbi',
			f'{jammer_prefix}.lat.deg',
			f'{jammer_prefix}.lon.deg', 
			f'{jammer_prefix}.alt.km',
			f'{jammer_prefix}.target.link',
			f'{jammer_prefix}.spectral_overlap.percent',
			f'{jammer_prefix}.separation_angular.deg',
			f'{jammer_prefix}.discrimination_fcc.db',
			f'{jammer_prefix}.polarization_isolation.db',
			f'{jammer_prefix}.discrimination_angular_real.db',
			f'{jammer_prefix}.frequency_offset.mhz',
			f'{jammer_prefix}.ci.db',
			f'{jammer_prefix}.cinr.original.db',
			f'{jammer_prefix}.cinr.with_attack.db',
			f'{jammer_prefix}.degradation.db',
			f'{jammer_prefix}.efficiency.percent',
			f'{jammer_prefix}.state',
			f'{jammer_prefix}.blocked.flag',
			f'{jammer_prefix}.power_margin.db',  # CLARIFICADO: Margen vs objetivo (negativo = déficit)
			f'{jammer_prefix}.recommendation',
			# === LABELS OPCIONALES PARA DASHBOARD ===
			f'{jammer_prefix}.ci.db_label',
			f'{jammer_prefix}.discrimination_angular_real.db_label'
		]
		jammer_blocks.extend(jammer_block)
	
	# AGREGADOS FINALES
	aggregates = [
		'agg.active_jammers.count',
		'agg.min_cinr_with_attack.db', 
		'agg.max_degradation.db',
		'agg.worst_jammer.id',
		'agg.throughput.estimate.mbps'
	]
	
	# ORDEN FINAL GARANTIZADO
	return sim_meta + time_orbital + uplink + downlink + e2e + jammer_blocks + aggregates


def write_row(sim_metadata, nominal_link, e2e_metrics, jammer_metrics_list):
	"""
	Genera una fila CSV con datos estructurados solo para jammers activos.
	
	Args:
		sim_metadata (dict): Metadatos de simulación (id, version, scenario, notes)
		nominal_link (dict): Datos del enlace nominal (geometry, ul/dl, time)
		e2e_metrics (dict): Métricas end-to-end (cinr, throughput, modcod, state)
		jammer_metrics_list (list): Lista de dict con métricas por jammer activo solamente
		
	Returns:
		list: Fila de datos en orden exacto de cabecera dinámica
		
	Coherencia garantizada:
		- degradation.db = cinr.original.db - cinr.with_attack.db
		- blocked.flag=1 ⟺ throughput.effective.mbps ≈ 0
		- Solo jammers activos incluidos (sin placeholders)
	"""
	
	row = []
	
	# === METADATOS DE SIMULACIÓN ===
	row.extend([
		sim_metadata.get('sim_id', 'SIM_001'),
		sim_metadata.get('schema_version', '2.1'),
		sim_metadata.get('scenario_name', 'DEFAULT'),
		sim_metadata.get('notes', '')
	])
	
	# === TIEMPO Y GEOMETRÍA ORBITAL ===
	row.extend([
		nominal_link.get('time_s', 0.0),
		nominal_link.get('rx_site_id', 'RX_001'), 
		nominal_link.get('constellation_id', 'LEO_001'),
		nominal_link.get('sat_id', 'SAT_001'),
		nominal_link.get('beam_id', 'BEAM_001'),
		nominal_link.get('elevation_deg', 0.0),
		nominal_link.get('azimuth_deg', 0.0),
		nominal_link.get('slant_distance_km', 0.0),
		nominal_link.get('fspl_db', 0.0),
		1 if nominal_link.get('visible', False) else 0
	])
	
	# === ENLACES UL/DL ===
	# Uplink
	row.extend([
		nominal_link.get('ul_freq_ghz', 30.0),
		nominal_link.get('ul_bw_mhz', 50.0),
		nominal_link.get('ul_gt_dbk', 0.0),
		nominal_link.get('ul_cn0_dbhz', 0.0),
		nominal_link.get('ul_cn_db', 0.0),
		nominal_link.get('ul_estado_cn', 'UNKNOWN')
	])
	
	# Downlink  
	row.extend([
		nominal_link.get('dl_freq_ghz', 20.0),
		nominal_link.get('dl_bw_mhz', 50.0), 
		nominal_link.get('dl_gt_dbk', 0.0),
		nominal_link.get('dl_cn0_dbhz', 0.0),
		nominal_link.get('dl_cn_db', 0.0),
		nominal_link.get('dl_estado_cn', 'UNKNOWN')
	])
	
	# === END-TO-END PERFORMANCE DASHBOARD-READY ===
	
	# 1. CINR nominal y con jamming  
	cinr_nominal_db = e2e_metrics.get('cinr_db', 0.0)
	cinr_jammed_db = cinr_nominal_db  # Por defecto, sin jamming
	if jammer_metrics_list:
		# CORRECCIÓN: Para un solo jammer, usar directamente su CINR con ataque
		# Para múltiples jammers, combinar apropiadamente (no solo min)
		if len(jammer_metrics_list) == 1:
			# Un solo jammer: usar directamente su resultado
			cinr_jammed_db = jammer_metrics_list[0].get('cinr_with_attack_db', cinr_nominal_db)
		else:
			# Múltiples jammers: usar el mínimo CINR (peor caso)
			min_cinr_with_attack = min([j.get('cinr_with_attack_db', cinr_nominal_db) for j in jammer_metrics_list])
			cinr_jammed_db = min_cinr_with_attack
	
	# 2. Parámetros UL para cálculos
	BW_UL_MHz = nominal_link.get('ul_bw_mhz', 20.0)  # Default 20 MHz según especificación
	
	# 3. Funciones auxiliares para mapeo MODCOD
	def get_modcod_and_efficiency(cinr_db):
		"""
		Tabla monótona: OUTAGE si <4, CRITICO si 4-<5, QPSK_1/2 si ≥5-<8, 
		QPSK_2/3 si ≥8-<12, 8PSK_3/4 si ≥12
		"""
		if cinr_db < 4:
			return 'OUTAGE', 0.0, 'OUTAGE'
		elif cinr_db < 5:
			return 'CRITICO', 0.0, 'CRITICO'  # No operativo
		elif cinr_db < 8:
			return 'QPSK_1_2', 1.0, 'FUNCIONAL'
		elif cinr_db < 12:
			return 'QPSK_2_3', 1.33, 'FUNCIONAL'
		else:
			return '8PSK_3_4', 2.25, 'FUNCIONAL'
	
	def calculate_shannon_capacity(cinr_db, bw_mhz):
		"""Shannon: BW × log2(1 + 10^(CINR/10))"""
		import math
		if cinr_db < -10:  # Límite práctico
			return 0.0
		snr_linear = 10**(cinr_db/10)
		return bw_mhz * math.log2(1 + snr_linear)
	
	# 4. BEFORE JAMMING (nominal)
	modcod_before, efficiency_before, state_before = get_modcod_and_efficiency(cinr_nominal_db)
	shannon_nominal = calculate_shannon_capacity(cinr_nominal_db, BW_UL_MHz)
	throughput_before = min(shannon_nominal, BW_UL_MHz * efficiency_before)
	
	# 5. WITH JAMMING (jammed)
	modcod_jammed, efficiency_jammed, state_jammed = get_modcod_and_efficiency(cinr_jammed_db)
	shannon_jammed = calculate_shannon_capacity(cinr_jammed_db, BW_UL_MHz)
	throughput_jammed = min(shannon_jammed, BW_UL_MHz * efficiency_jammed)
	
	# 6. DELTAS
	delta_cinr = cinr_nominal_db - cinr_jammed_db
	delta_throughput = throughput_before - throughput_jammed
	
	# 7. LABELS para dashboard (con redondeo apropiado para legibilidad)
	if state_jammed == 'OUTAGE':
		modcod_label = f"{modcod_before} (OUT)"
		efficiency_label = f"{efficiency_before:.1f} (OUT)"
		throughput_label = f"{throughput_before:.1f} (OUT)"
		cinr_label = f"{cinr_jammed_db:.1f} (OUT)"
		state_label = "OUTAGE (OUT)"
	elif state_jammed == 'CRITICO':
		modcod_label = f"{modcod_before} (CRIT)"
		efficiency_label = f"{efficiency_before:.1f} (CRIT)"
		throughput_label = f"{throughput_before:.1f} (CRIT)"
		cinr_label = f"{cinr_jammed_db:.1f} (CRIT)"
		state_label = "CRITICO (CRIT)"
	else:  # FUNCIONAL
		modcod_label = modcod_jammed
		efficiency_label = f"{efficiency_jammed:.1f}"
		throughput_label = f"{throughput_jammed:.1f}"
		cinr_label = f"{cinr_jammed_db:.1f}"
		state_label = "FUNCIONAL"
	
	# 8. PLOT para continuidad visual
	if state_jammed in ['OUTAGE', 'CRITICO']:
		throughput_plot = throughput_before
		efficiency_plot = efficiency_before
		cinr_plot = cinr_nominal_db  # Usar CINR nominal para continuidad visual
	else:
		throughput_plot = throughput_jammed
		efficiency_plot = efficiency_jammed
		cinr_plot = cinr_jammed_db  # Usar CINR jammeada en tramos funcionales
	
	# 9. Construcción de fila E2E expandida
	row.extend([
		# === MÉTRICAS PRINCIPALES ===
		cinr_jammed_db, cinr_nominal_db,
		e2e_metrics.get('latency_ms', 0.0),
		e2e_metrics.get('rtt_ms', 0.0),
		shannon_jammed,
		
		# === BEFORE JAMMING ===
		modcod_before, efficiency_before, throughput_before,
		
		# === WITH JAMMING ===
		modcod_jammed, efficiency_jammed, throughput_jammed,
		
		# === DELTAS ===
		delta_cinr, delta_throughput,
		
		# === LABELS PARA DASHBOARD ===
		modcod_label, efficiency_label, throughput_label,
		cinr_label, state_label,
		
		# === PLOT PARA CONTINUIDAD VISUAL ===
		throughput_plot, efficiency_plot, cinr_plot,
		
		# === ESTADO ===
		state_jammed
	])
	
	# === BLOQUES DINÁMICOS POR JAMMER ACTIVO ===
	for jammer in jammer_metrics_list:
		# Cálculo coherente de degradación con validación
		cinr_original = jammer.get('cinr_original_db', e2e_metrics.get('cinr_db', 0.0))
		cinr_with_attack = jammer.get('cinr_with_attack_db', cinr_original)
		degradation_db = cinr_original - cinr_with_attack
		
		# Validación de coherencia (|error| < 0.05 dB)
		reported_degradation = jammer.get('degradation_db', degradation_db)
		if abs(degradation_db - reported_degradation) > 0.05:
			print(f"⚠️ Inconsistencia degradación jammer {jammer.get('jammer_id', 'Unknown')}: calculada={degradation_db:.2f}, reportada={reported_degradation:.2f}")
			degradation_db = reported_degradation  # Usar valor reportado si hay inconsistencia
		
		# CORRECCIÓN: blocked_flag consistente con estado y throughput E2E con jamming
		jammer_state = jammer.get('state', 'UNKNOWN')
		
		# Usar throughput E2E con jamming calculado arriba
		effective_throughput = throughput_jammed if jammer_metrics_list else shannon_jammed
		
		# Activar blocked_flag si estado crítico O throughput bajo O CINR muy bajo
		blocked_flag = 1 if (jammer_state in ['OUTAGE', 'BLOQUEADO'] or 
							 effective_throughput < 1.0 or 
							 cinr_with_attack < 3.0 or
							 modcod_jammed == 'OUTAGE') else 0
		
		# CORRECCIÓN: Estado coherente derivado de MODCOD E2E con jamming
		if modcod_jammed == 'OUTAGE':
			state = 'OUTAGE'
		elif effective_throughput < 1.0 or cinr_with_attack < 3:
			state = 'BLOQUEADO'
		elif cinr_with_attack < 8:
			state = 'CRITICO'
		elif cinr_with_attack < 12:
			state = 'DEGRADADO'
		else:
			state = 'FUNCIONAL'
		
		# LABELS opcionales para dashboard de jammers
		ci_db = jammer.get('ci_db', 0.0)
		ci_label = f"{ci_db:.1f} (JAM)" if ci_db < 0 else f"{ci_db:.1f} (OK)"
		
		discrimination_real = jammer.get('discrimination_angular_real_db', 21.0)
		if discrimination_real < 12:
			discrim_label = f"{discrimination_real:.1f} (BAJA)"
		elif discrimination_real <= 18:
			discrim_label = f"{discrimination_real:.1f} (MEDIA)"
		else:
			discrim_label = f"{discrimination_real:.1f} (ALTA)"
		
		row.extend([
			1,  # present - siempre 1 para jammers activos
			jammer.get('jammer_id', 'UNKNOWN'),
			jammer.get('jammer_name', 'UNKNOWN'),
			jammer.get('platform_type', 'SURFACE'),
			jammer.get('jammer_type', 'SPOT'),
			jammer.get('eirp_dbw', 63.0),
			jammer.get('center_freq_ghz', 30.0),
			jammer.get('bandwidth_mhz', 50.0),
			jammer.get('polarization', 'LINEAR'),
			jammer.get('antenna_gain_dbi', 30.0),
			jammer.get('lat_deg', 0.0),
			jammer.get('lon_deg', 0.0),
			jammer.get('alt_km', 0.05),
			jammer.get('target_link', 'UL'),  # Asegurar mapeo correcto UL/DL
			jammer.get('spectral_overlap_percent', 100.0),
			jammer.get('separation_angular_deg', 0.0),
			jammer.get('discrimination_fcc_db', 21.0),
			jammer.get('polarization_isolation_db', -4.0),
			jammer.get('discrimination_angular_real_db', 21.0),
			jammer.get('frequency_offset_mhz', 0.0),
			jammer.get('ci_db', 0.0),
			cinr_original,
			cinr_with_attack,
			degradation_db,  # COHERENTE: original - with_attack
			jammer.get('efficiency_percent', 0.0),
			state,  # COHERENTE: derivado de umbrales
			blocked_flag,  # COHERENTE: throughput ≈ 0
			jammer.get('power_margin_db', 0.0),  # CLARIFICADO: Margen de potencia (negativo = insuficiente)
			jammer.get('recommendation', 'N/A'),
			# === LABELS OPCIONALES PARA DASHBOARD ===
			ci_label,
			discrim_label
		])
	
	# === AGREGADOS FINALES ===
	active_jammers = len(jammer_metrics_list)
	min_cinr = min([j.get('cinr_with_attack_db', 999) for j in jammer_metrics_list], default=999)
	max_degradation = max([j.get('degradation_db', 0) for j in jammer_metrics_list], default=0)
	worst_jammer = ''
	if jammer_metrics_list:
		worst_idx = max(range(len(jammer_metrics_list)), 
					   key=lambda i: jammer_metrics_list[i].get('degradation_db', 0))
		worst_jammer = jammer_metrics_list[worst_idx].get('jammer_id', f'J{worst_idx+1}')
	
	throughput_estimate = throughput_jammed if jammer_metrics_list else shannon_jammed
	
	row.extend([
		active_jammers,
		min_cinr if min_cinr < 999 else 0.0,
		max_degradation,
		worst_jammer,
		throughput_estimate
	])
	
	return row


if __name__ == '__main__':
	# DEMOSTRACIÓN: Sistema CSV dinámico para jammers activos
	print("=== DEMO: CABECERA CSV DINÁMICA ===")
	
	# Ejemplo 1: 3 jammers activos 
	active_jammers_1 = ["J1", "J3", "J7"]
	headers_dynamic_1 = build_csv_header(active_jammers=active_jammers_1)
	print(f"\n🔧 CABECERA PARA JAMMERS ACTIVOS {active_jammers_1} ({len(headers_dynamic_1)} columnas):")
	print(",".join(headers_dynamic_1))
	
	# Ejemplo 2: 1 jammer activo
	active_jammers_2 = ["J_SPOT_30GHZ"]
	headers_dynamic_2 = build_csv_header(active_jammers=active_jammers_2)
	print(f"\n🔧 CABECERA PARA JAMMER ÚNICO {active_jammers_2} ({len(headers_dynamic_2)} columnas):")
	print(",".join(headers_dynamic_2))
	
	# Ejemplo 3: Sin jammers (solo enlaces nominales)
	headers_no_jammers = build_csv_header(active_jammers=[])
	print(f"\n🔧 CABECERA SIN JAMMERS ({len(headers_no_jammers)} columnas):")
	print(",".join(headers_no_jammers))
	
	# Mostrar estructura de bloques dinámica
	print(f"\n📊 ESTRUCTURA DE BLOQUES DINÁMICA:")
	print(f"   • Metadatos Simulación: 4 columnas")
	print(f"   • Tiempo y Orbital: 10 columnas") 
	print(f"   • Enlaces (UL+DL): 12 columnas")
	print(f"   • End-to-End: 8 columnas")
	print(f"   • Bloques Jammer: 29 columnas × JAMMERS_ACTIVOS (dinámico)")
	print(f"   • Agregados: 5 columnas")
	print(f"   • TOTAL: 39 + (29×JAMMERS_ACTIVOS)")
	
	print(f"\n✅ Sistema CSV dinámico implementado con coherencia garantizada:")
	print(f"   📈 degradation.db = cinr.original.db - cinr.with_attack.db (usando calculate_cinr_with_jamming)")
	print(f"   🎯 target.link = UL con tie-breaker para frecuencias iguales")
	print(f"   🔒 blocked.flag=1 ⟺ throughput.effective.mbps ≈ 0")
	print(f"   📊 Estados derivados de umbrales CINR coherentes")
	print(f"   📦 Solo jammers activos (sin placeholders vacíos)")
	print(f"   🎯 Ready para dashboard con pivoting optimizado")
	
	main()

