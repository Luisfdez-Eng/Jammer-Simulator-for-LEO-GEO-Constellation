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


class Constellation:
	"""Representa (por ahora) una colección simple de satélites.

	Más adelante: órbitas, planos, propagación temporal, handovers.
	"""
	def __init__(self, satellites: List[Satellite]):
		self.satellites = satellites

	@classmethod
	def single_leo(cls, altitude_m: float) -> 'Constellation':
		return cls([Satellite(name="LEO-SAT-1", altitude_m=altitude_m)])


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
		self.orbit_angle_deg = 0.0
		self.step_orbit_deg = 2.0
		alt_km = self.core.constellation.satellites[0].altitude_m / 1000.0
		self.Re_km = EARTH_RADIUS_M / 1000.0
		self.orbit_r_km = self.Re_km + alt_km
		self.geo_orbit_r_km = self.Re_km + self.core.geo_altitude_m/1000.0
		self.horizon_central_angle_deg = math.degrees(math.acos(self.Re_km / self.orbit_r_km))
		self.orbit_angle_deg = (360.0 - self.horizon_central_angle_deg)
		self.history: List[Dict[str, Any]] = []
		self.start_time: Optional[float] = None
		self._build_layout(); self._draw_static(); self.update_metrics()

	def _build_layout(self):
		self.mainframe = ttk.Frame(self.root, padding=5); self.mainframe.pack(fill='both', expand=True)
		left = ttk.Frame(self.mainframe); left.pack(side='left', fill='y')
		bold_lbl = ('Segoe UI', 10, 'bold')
		ttk.Label(left, text="Modo:", font=bold_lbl).pack(anchor='w')
		self.mode_var = tk.StringVar(value='LEO')
		mode_combo = ttk.Combobox(left, textvariable=self.mode_var, values=['LEO','GEO'], state='readonly')
		mode_combo.pack(anchor='w', pady=2)
		mode_combo.bind('<<ComboboxSelected>>', lambda e: self._change_mode())
		ttk.Label(left, text="EIRP (dBW):", font=bold_lbl).pack(anchor='w'); self.eirp_var = tk.DoubleVar(value=self.core.eirp_dbw); ttk.Entry(left, textvariable=self.eirp_var, width=10).pack(anchor='w')
		ttk.Label(left, text="G/T (dB/K):", font=bold_lbl).pack(anchor='w'); self.gt_var = tk.DoubleVar(value=self.core.gt_dbk); ttk.Entry(left, textvariable=self.gt_var, width=10).pack(anchor='w')
		ttk.Label(left, text="Frecuencia (GHz):", font=bold_lbl).pack(anchor='w'); self.freq_var = tk.DoubleVar(value=self.core.calc.frequency_hz/1e9); ttk.Entry(left, textvariable=self.freq_var, width=10).pack(anchor='w')
		ttk.Label(left, text="BW (MHz):", font=bold_lbl).pack(anchor='w'); self.bw_var = tk.DoubleVar(value=self.core.calc.default_bandwidth_hz/1e6); ttk.Entry(left, textvariable=self.bw_var, width=10).pack(anchor='w')
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
		self.orbit_slider_var = tk.DoubleVar(value=self.orbit_angle_deg); self.user_adjusting_slider = False
		self.orbit_slider = tk.Scale(slider_frame, from_=0, to=359.9, orient='horizontal', resolution=0.1, label='Ángulo Orbital LEO (0°=sobre GS)', variable=self.orbit_slider_var, command=lambda v: self._on_slider_change(float(v)))
		self.orbit_slider.pack(fill='x', pady=2)
		self.geo_slider_var = tk.DoubleVar(value=0.0)
		self.geo_slider = tk.Scale(slider_frame, from_=-180, to=180, orient='horizontal', resolution=0.5, label='Longitud GEO (°)', variable=self.geo_slider_var, command=lambda v: self._on_geo_slider(float(v)))
		self.geo_slider.pack(fill='x', pady=2); self.geo_slider.configure(state='disabled')
		self.orbit_slider.bind('<ButtonPress-1>', lambda e: self._begin_slider()); self.orbit_slider.bind('<ButtonRelease-1>', lambda e: self._end_slider())
		self.canvas.bind('<Configure>', lambda e: self._draw_static())
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
		self.export_btn = ttk.Button(right, text='Exportar CSV/XLSX', command=self.export_csv); self.export_btn.pack(side='bottom', pady=4)

	def toggle_run(self):
		self.running = not self.running
		if self.running and self.start_time is None: self.start_time = time.time()
		self.run_btn.config(text='Parar' if self.running else 'Iniciar')
		if self.running and self.mode_var.get() == 'LEO': self._animate()
		if not self.running: self.orbit_slider_var.set(self.orbit_angle_deg)

	def reset(self):
		self.orbit_angle_deg = (360.0 - self.horizon_central_angle_deg); self.history.clear(); self.start_time = None
		self.update_metrics(); self._draw_dynamic(); self.orbit_slider_var.set(self.orbit_angle_deg); self.geo_slider_var.set(0.0)

	def _begin_slider(self):
		if self.running:
			self.running = False; self.run_btn.config(text='Iniciar')
		self.user_adjusting_slider = True

	def _on_slider_change(self, val: float):
		if not self.user_adjusting_slider: return
		self.orbit_angle_deg = val % 360.0; self._draw_dynamic(); self.update_metrics()

	def _on_geo_slider(self, val: float):
		if self.mode_var.get() == 'GEO': self._draw_dynamic(); self.update_metrics()

	def _end_slider(self):
		self.user_adjusting_slider = False; self.orbit_slider_var.set(self.orbit_angle_deg)

	def export_csv(self):
		"""Exporta la historia en CSV (cabeceras amigables) o XLSX con formato.

		Si el usuario elige extensión .xlsx y está disponible openpyxl,
		se aplican negrita+itálica+size 13 a las cabeceras.
		"""
		if not self.history:
			self._append_metrics("No hay datos para exportar. Inicia la simulación primero.\n"); return
		from tkinter import filedialog
		path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV','*.csv'), ('Excel','*.xlsx')], title='Guardar resultados')
		if not path: return
		# Orden y mapeo legible
		field_order = [
			'time_s','mode','orbit_angle_deg','geo_longitude_deg','elevation_deg','visible','slant_range_km',
			'fspl_db','loss_total_extra_db','path_loss_total_db',
			'RFL_feeder','AML_misalignment','AA_atmos','Rain_att','PL_polarization','L_pointing','L_impl',
			'eirp_sat_dbw','input_backoff_db','output_backoff_db','eirp_dbw','manual_eirp_override',
			'latency_ms_one_way','latency_total_ms_one_way','latency_total_rtt_ms','cn0_dbhz','cn_db','gt_dbk','frequency_ghz','bandwidth_mhz',
			'T_sys_K','N0_dBHz','EbN0_dB','EbN0_req_dB','Eb_margin_dB','Shannon_capacity_Mbps','Spectral_eff_real_bps_hz','Utilization_pct'
			,'modcod_name','modcod_eff_bps_hz','modcod_ebn0_req_db','modcod_margin_db','modcod_status'
		]
		label_map = {
			'time_s':'TIME [s]',
			'mode':'MODE',
			'orbit_angle_deg':'LEO ANGLE [deg]',
			'geo_longitude_deg':'GEO LONG [deg]',
			'elevation_deg':'ELEVATION [deg]',
			'visible':'VISIBLE (1/0)',
			'slant_range_km':'SLANT RANGE [km]',
			'fspl_db':'FSPL [dB]',
			'loss_total_extra_db':'SUM EXTRA LOSSES [dB]',
			'path_loss_total_db':'PATH LOSS TOTAL [dB]',
			'RFL_feeder':'RFL FEEDER [dB]',
			'AML_misalignment':'AML MISALIGN [dB]',
			'AA_atmos':'AA ATMOS [dB]',
			'Rain_att':'RAIN ATT [dB]',
			'PL_polarization':'PL POL [dB]',
			'L_pointing':'POINTING [dB]',
			'L_impl':'IMPL [dB]',
			'eirp_sat_dbw':'EIRP SAT [dBW]',
			'input_backoff_db':'INPUT BO [dB]',
			'output_backoff_db':'OUTPUT BO [dB]',
			'eirp_dbw':'EIRP EFF [dBW]',
			'manual_eirp_override':'MAN EIRP OVERRIDE (1/0)',
			'latency_ms_one_way':'LATENCY OW [ms]',
			'latency_total_ms_one_way':'LATENCY TOTAL OW [ms]',
			'latency_total_rtt_ms':'LATENCY TOTAL RTT [ms]',
			'cn0_dbhz':'C/N0 [dBHz]',
			'cn_db':'C/N [dB]',
			'cn_quality':'C/N QUALITY',
			'eirp_dbw':'EIRP [dBW]',
			'gt_dbk':'G/T [dB/K]',
			'frequency_ghz':'FREQ [GHz]',
			'bandwidth_mhz':'BW [MHz]',
			'T_sys_K':'T_SYS [K]',
			'N0_dBHz':'N0 [dBHz]',
			'EbN0_dB':'EBN0 [dB]',
			'EbN0_req_dB':'EBN0 REQ [dB]',
			'Eb_margin_dB':'EB MARGIN [dB]',
			'Shannon_capacity_Mbps':'C_SHANNON [Mbps]',
			'Spectral_eff_real_bps_hz':'EFF REAL [b/Hz]',
			'Utilization_pct':'UTILIZATION [%]',
			'modcod_name':'MODCOD',
			'modcod_eff_bps_hz':'MODCOD EFF [b/Hz]',
			'modcod_ebn0_req_db':'MODCOD EBN0 REQ [dB]',
			'modcod_margin_db':'MODCOD MARGIN [dB]',
			'modcod_status':'MODCOD STATUS',
		}
		# Asegurar que campos adicionales (si hubieran) no se pierdan
		for k in self.history[0].keys():
			if k not in field_order:
				field_order.append(k)
				if k not in label_map:
					label_map[k] = k.upper()
		try:
			if path.lower().endswith('.xlsx'):
				try:
					from openpyxl import Workbook
					from openpyxl.styles import Font
				except ImportError:
					self._append_metrics("openpyxl no instalado. Usa pip install openpyxl o exporta como CSV.\n"); return
				wb = Workbook(); ws = wb.active; ws.title = 'Resultados'
				headers = [label_map[f] for f in field_order]
				ws.append(headers)
				for row in self.history:
					ws.append([row.get(f, '') for f in field_order])
				# Formato cabecera
				for cell in ws[1]:
					cell.font = Font(bold=True, italic=True, size=13)
				ws.freeze_panes = 'A2'
				wb.save(path)
			else:
				with open(path, 'w', newline='', encoding='utf-8') as f:
					writer = csv.writer(f)
					writer.writerow([label_map[f] for f in field_order])
					for row in self.history:
						writer.writerow([row.get(f,'') for f in field_order])
			self._append_metrics(f"Exportado: {path}\n")
		except Exception as e:
			self._append_metrics(f"Error exportando: {e}\n")

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
		# Tierra
		self.canvas.create_oval(self.cx-self.earth_radius_px, self.cy-self.earth_radius_px, self.cx+self.earth_radius_px, self.cy+self.earth_radius_px, fill='#e0f4ff', outline='#0077aa', width=2)
		# Ground station en "norte" del dibujo
		self.gs_x = self.cx; self.gs_y = self.cy - self.earth_radius_px
		self.canvas.create_oval(self.gs_x-5, self.gs_y-5, self.gs_x+5, self.gs_y+5, fill='green', outline='black')
		self.canvas.create_text(self.gs_x+10, self.gs_y-10, text='GS', anchor='w')
		self._draw_dynamic()

	def _change_mode(self):
		if self.mode_var.get() == 'LEO':
			self.eirp_var.set(self.core.eirp_dbw); self.gt_var.set(self.core.gt_dbk); self.orbit_slider.configure(state='normal'); self.geo_slider.configure(state='disabled')
		else:
			self.eirp_var.set(self.core.geo_eirp_dbw); self.gt_var.set(self.core.geo_gt_dbk); self.orbit_slider.configure(state='disabled'); self.geo_slider.configure(state='normal')
		self.update_metrics(); self._draw_dynamic()

	def _draw_dynamic(self):
		self.canvas.delete('dyn')
		if self.mode_var.get() == 'LEO':
			# Usamos radio visual para dibujo, pero cálculos geométricos con delta del ángulo orbital.
			orbit_r_px = self.leo_orbit_r_px_visual
			self.canvas.create_oval(self.cx-orbit_r_px, self.cy-orbit_r_px, self.cx+orbit_r_px, self.cy+orbit_r_px, outline='#cccccc', dash=(3,4), tags='dyn')
			phi = math.radians(self.orbit_angle_deg % 360.0)
			# Posición visual
			sx = self.cx + orbit_r_px * math.sin(phi); sy = self.cy - orbit_r_px * math.cos(phi)
			# Ángulo central desde el sub-satélite al GS (overhead=0). Tomamos simetría.
			delta_raw = self.orbit_angle_deg % 360.0
			if delta_raw > 180: delta_raw = 360 - delta_raw
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
			self.canvas.create_line(self.gs_x, self.gs_y, sx, sy, fill=('red' if visible else '#bbbbbb'), dash=(5,4) if visible else (2,4), width=2 if visible else 1, tags='dyn')
			self.canvas.create_oval(sx-7, sy-7, sx+7, sy+7, fill='orange', outline='black', tags='dyn')
			self.canvas.create_text(sx+10, sy, text=f"LEO {elev_deg:.0f}°" + ("" if visible else " (OCULTO)"), anchor='w', tags='dyn')
			self.current_elevation_deg = elev_deg; self.current_visible = visible; self.current_slant_distance_m = slant_km * 1000.0
			self.current_delta_deg = delta_deg  # Para Fase 1 (geometría/doppler)
		else:
			geo_r_px = self.geo_orbit_r_px
			self.canvas.create_oval(self.cx-geo_r_px, self.cy-geo_r_px, self.cx+geo_r_px, self.cy+geo_r_px, outline='#aaaaff', dash=(2,3), tags='dyn')
			phi_long = math.radians(self.geo_slider_var.get()); sx = self.cx + geo_r_px * math.sin(phi_long); sy = self.cy - geo_r_px * math.cos(phi_long)
			delta_long = abs(phi_long); Re = self.Re_km; Ro = self.geo_orbit_r_km
			slant_km = math.sqrt(Re*Re + Ro*Ro - 2*Re*Ro*math.cos(delta_long))
			# Elevación exacta (observador en ecuador) sin refracción: sin(E) = (Ro cos Δ - Re)/slant
			if slant_km == 0:
				elev_deg = 90.0
			else:
				sin_e = (Ro * math.cos(delta_long) - Re) / slant_km
				sin_e = max(-1.0, min(1.0, sin_e))
				elev_deg = math.degrees(math.asin(sin_e))
			visible = elev_deg > 0
			self.canvas.create_line(self.gs_x, self.gs_y, sx, sy, fill=('purple' if visible else '#bbbbbb'), dash=(5,3) if visible else (2,3), width=2 if visible else 1, tags='dyn')
			self.canvas.create_oval(sx-8, sy-8, sx+8, sy+8, fill='#6040ff', outline='black', tags='dyn')
			self.canvas.create_text(sx+10, sy, text=f"GEO {elev_deg:.0f}°", anchor='w', tags='dyn')
			self.current_elevation_deg = elev_deg; self.current_visible = visible; self.current_slant_distance_m = slant_km * 1000.0

	def _compute_slant_range_m(self, central_angle_deg: float) -> float:
		delta = math.radians(central_angle_deg); re = self.Re_km; ro = self.orbit_r_km; slant_km = math.sqrt(re*re + ro*ro - 2*re*ro*math.cos(delta)); return slant_km * 1000.0

	def _animate(self):
		if not self.running: return
		if self.mode_var.get() == 'LEO':
			self.orbit_angle_deg = (self.orbit_angle_deg + self.step_orbit_deg) % 360.0
			if not self.user_adjusting_slider: self.orbit_slider_var.set(self.orbit_angle_deg)
		self.update_metrics(); self._draw_dynamic(); self.root.after(300, self._animate)


	# ----------------------------- BLOQUES MODULARES (Fases 0-1) ----------------------------- #
	def update_metrics(self):
		"""Orquesta el refresco: parámetros -> geometría -> doppler -> enlace -> render tabla."""
		self._update_core_params()
		self._update_geometry_block()
		self._update_doppler_block()
		self._update_link_block()
		self._update_latency_block()  # Fase 5
		# Primero seleccionamos MODCOD (deriva Rb y Eb/N0 requerido) y luego calculamos performance real
		self._update_modcod_block()  # Fase 5 (genera Rb_Mbps & EbN0_req)
		self._update_performance_block()  # Fase 4 (usa Rb derivado)
		self._render_metrics()
		self._append_history_row()

	def _update_core_params(self):
		self.core.eirp_dbw = float(self.eirp_var.get())
		self.core.gt_dbk = float(self.gt_var.get())
		self.core.calc.frequency_hz = float(self.freq_var.get()) * 1e9
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
		if hasattr(self,'perf_metrics'):
			current_ebn0 = self.perf_metrics.get('EbN0_dB')
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
				self.modcod_status = 'Crítico'
			else:
				self.modcod_status = 'Insuficiente'
		else:
			self.modcod_margin_db = float('nan')
			self.modcod_status = '—'
		# Actualizar labels MODCOD
		self.modcod_eff_label.config(text=f"Eff: {best['efficiency_bps_hz']:.3f} b/Hz")
		self.modcod_req_label.config(text=f"Eb/N0 Req: {best['ebn0_req_db']:.2f} dB")
		color_map = {'Excelente':'#007700','Aceptable':'#c08000','Crítico':'#b05000','Insuficiente':'#b00000','—':'#666666'}
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
		}

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
		elv_txt = f"{self.current_elevation_deg:.1f} ({'OK' if visible else 'OCULTO'})"
		self.metric_labels['Elevación [°]'].config(text=elv_txt, foreground=('#004080' if visible else '#aa0000'))
		self.metric_labels['Distancia Slant [km]'].config(text=fmt(self.current_slant_distance_m/1000.0, "{:.0f}"))
		self.metric_labels['FSPL (Espacio Libre) [dB]'].config(text=fmt(self.link_metrics['fspl_db']))
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
		self.metric_labels['C/N0 [dBHz]'].config(text=fmt(self.link_metrics['cn0_dbhz']))
		self.metric_labels['C/N [dB]'].config(text=fmt(self.link_metrics['cn_db']))
		self.metric_labels['G/T [dB/K]'].config(text=f"{self.core.gt_dbk:.1f}")
		status_txt, color = self._assess_cn(self.link_metrics['cn_db'])
		self.metric_labels['Estado C/N'].config(text=status_txt, foreground=color)

		# Potencia / Backoff
		self.metric_labels['EIRP Saturado [dBW]'].config(text=f"{self.power_metrics.get('eirp_sat', float('nan')):.1f}")
		self.metric_labels['Back-off Entrada [dB]'].config(text=f"{self.power_metrics.get('input_bo', float('nan')):.1f}")
		self.metric_labels['Back-off Salida [dB]'].config(text=f"{self.power_metrics.get('output_bo', float('nan')):.1f}")
		self.metric_labels['EIRP Efectivo [dBW]'].config(text=f"{self.core.eirp_dbw:.1f}")
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
			return ("Crítico", "#b00000")

	def _append_history_row(self):
		if self.running and self.start_time is not None:
			elapsed = time.time() - self.start_time
			visible = getattr(self, 'current_visible', False)
			fspl = self.link_metrics['fspl_db']; lat_ow = self.link_metrics['latency_ms_ow']; cn0 = self.link_metrics['cn0_dbhz']; cn = self.link_metrics['cn_db']
			row = {
				'time_s': round(elapsed,3),
				'orbit_angle_deg': round(self.orbit_angle_deg,2),
				'mode': self.mode_var.get(),
				'geo_longitude_deg': None if self.mode_var.get()=='LEO' else round(self.geo_slider_var.get(),2),
				'elevation_deg': round(self.current_elevation_deg,2),
				'visible': int(visible),
				'slant_range_km': round(self.current_slant_distance_m/1000.0,2),
				'fspl_db': None if math.isnan(fspl) else round(fspl,2),
				'latency_ms_one_way': None if math.isnan(lat_ow) else round(lat_ow,3),
				'cn0_dbhz': None if math.isnan(cn0) else round(cn0,2),
				'cn_db': None if math.isnan(cn) else round(cn,2),
				'eirp_dbw': round(self.core.eirp_dbw,2),
				'eirp_sat_dbw': round(self.power_metrics.get('eirp_sat', float('nan')),2),
				'input_backoff_db': round(self.power_metrics.get('input_bo', float('nan')),2),
				'output_backoff_db': round(self.power_metrics.get('output_bo', float('nan')),2),
				'manual_eirp_override': self.power_metrics.get('manual_override',0),
				'gt_dbk': round(self.core.gt_dbk,2),
				'bandwidth_mhz': round(self.core.calc.default_bandwidth_hz/1e6,3),
				'frequency_ghz': round(self.core.calc.frequency_hz/1e9,4)
			}
			# Añadir pérdidas al historial
			row['loss_total_extra_db'] = round(self.link_metrics.get('loss_total_extra_db'),2) if 'loss_total_extra_db' in self.link_metrics else None
			pl_total = self.link_metrics.get('path_loss_total_db')
			row['path_loss_total_db'] = round(pl_total,2) if pl_total is not None and not math.isnan(pl_total) else None
			for k,v in self.core.losses.items():
				row[k] = round(v,2)
			row['cn_quality'] = self._assess_cn(cn)[0] if cn is not None else None
			# Métricas rendimiento
			if hasattr(self, 'perf_metrics'):
				pm = self.perf_metrics
				for key in ['T_sys_K','N0_dBHz','EbN0_dB','EbN0_req_dB','Eb_margin_dB','Shannon_capacity_Mbps','Spectral_eff_real_bps_hz','Utilization_pct']:
					val = pm.get(key)
					row[key] = None if (isinstance(val,float) and math.isnan(val)) else (round(val,3) if isinstance(val,(int,float)) else val)
			# MODCOD
			if hasattr(self, 'modcod_active'):
				row['modcod_name'] = self.modcod_active.get('name')
				row['modcod_eff_bps_hz'] = round(self.modcod_active.get('efficiency_bps_hz', float('nan')),3)
				row['modcod_ebn0_req_db'] = round(self.modcod_active.get('ebn0_req_db', float('nan')),2)
				row['modcod_margin_db'] = round(self.modcod_margin_db,2) if hasattr(self,'modcod_margin_db') else None
				row['modcod_status'] = self.modcod_status if hasattr(self,'modcod_status') else None
			# Latencias totales
			if 'total_latency_ow_ms' in self.link_metrics:
				row['latency_total_ms_one_way'] = round(self.link_metrics['total_latency_ow_ms'],3)
				row['latency_total_rtt_ms'] = round(self.link_metrics['total_latency_rtt_ms'],3)
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


if __name__ == '__main__':
	main()

