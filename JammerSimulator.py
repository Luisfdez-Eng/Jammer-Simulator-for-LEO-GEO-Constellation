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
		ttk.Label(left, text="Modo:").pack(anchor='w')
		self.mode_var = tk.StringVar(value='LEO')
		mode_combo = ttk.Combobox(left, textvariable=self.mode_var, values=['LEO','GEO'], state='readonly')
		mode_combo.pack(anchor='w', pady=2)
		mode_combo.bind('<<ComboboxSelected>>', lambda e: self._change_mode())
		ttk.Label(left, text="EIRP (dBW):").pack(anchor='w'); self.eirp_var = tk.DoubleVar(value=self.core.eirp_dbw); ttk.Entry(left, textvariable=self.eirp_var, width=10).pack(anchor='w')
		ttk.Label(left, text="G/T (dB/K):").pack(anchor='w'); self.gt_var = tk.DoubleVar(value=self.core.gt_dbk); ttk.Entry(left, textvariable=self.gt_var, width=10).pack(anchor='w')
		ttk.Label(left, text="Frecuencia (GHz):").pack(anchor='w'); self.freq_var = tk.DoubleVar(value=self.core.calc.frequency_hz/1e9); ttk.Entry(left, textvariable=self.freq_var, width=10).pack(anchor='w')
		ttk.Label(left, text="BW (MHz):").pack(anchor='w'); self.bw_var = tk.DoubleVar(value=self.core.calc.default_bandwidth_hz/1e6); ttk.Entry(left, textvariable=self.bw_var, width=10).pack(anchor='w')
		sep2 = ttk.Separator(left, orient='horizontal'); sep2.pack(fill='x', pady=6)
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
		# Panel de métricas tabular
		self.metrics_panel = ttk.Frame(right)
		self.metrics_panel.pack(fill='both', expand=True)
		self._init_metrics_table()
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
			'fspl_db','latency_ms_one_way','cn0_dbhz','cn_db','eirp_dbw','gt_dbk','frequency_ghz','bandwidth_mhz'
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
			'latency_ms_one_way':'LATENCY OW [ms]',
			'cn0_dbhz':'C/N0 [dBHz]',
			'cn_db':'C/N [dB]',
			'eirp_dbw':'EIRP [dBW]',
			'gt_dbk':'G/T [dB/K]',
			'frequency_ghz':'FREQ [GHz]',
			'bandwidth_mhz':'BW [MHz]',
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
		rows = [
			('Modo', '—'),
			('Elevación [°]', '—'),
			('Distancia [km]', '—'),
			('FSPL [dB]', '—'),
			('Latencia OW [ms]', '—'),
			('C/N0 [dBHz]', '—'),
			('C/N [dB]', '—'),
			('EIRP [dBW]', '—'),
			('G/T [dB/K]', '—'),
		]
		self.metric_labels = {}
		for r,(name, val) in enumerate(rows):
			lbl = ttk.Label(self.metrics_panel, text=name+':', font=font_label, anchor='w')
			lbl.grid(row=r, column=0, sticky='w', padx=(2,4), pady=1)
			val_lbl = ttk.Label(self.metrics_panel, text=val, font=font_value, foreground='#004080', anchor='e')
			val_lbl.grid(row=r, column=1, sticky='e', padx=(4,6), pady=1)
			self.metric_labels[name] = val_lbl
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

	def update_metrics(self):
		self.core.eirp_dbw = float(self.eirp_var.get()); self.core.gt_dbk = float(self.gt_var.get())
		self.core.calc.frequency_hz = float(self.freq_var.get()) * 1e9; self.core.calc.default_bandwidth_hz = float(self.bw_var.get()) * 1e6
		if not hasattr(self, 'current_slant_distance_m'): self._draw_dynamic()
		d = self.current_slant_distance_m; visible = getattr(self, 'current_visible', True)
		calc = self.core.calc if self.mode_var.get() == 'LEO' else self.core.geo_calc
		if calc is self.core.geo_calc:
			calc.frequency_hz = self.core.calc.frequency_hz; calc.default_bandwidth_hz = self.core.calc.default_bandwidth_hz
		fspl = calc.free_space_path_loss_db(d) if visible else float('nan'); lat_ow = calc.propagation_delay_ms(d) if visible else float('nan')
		if visible: cn0 = calc.cn0_dbhz(self.core.eirp_dbw, self.core.gt_dbk, fspl); cn = calc.cn_db(cn0)
		else: cn0 = float('nan'); cn = float('nan')
		# Actualiza tabla visual
		def fmt(v, fmt_str="{:.2f}"):
			return '—' if (isinstance(v,float) and math.isnan(v)) else (fmt_str.format(v) if isinstance(v,(int,float)) else str(v))
		self.metric_labels['Modo'].config(text=self.mode_var.get())
		elv_txt = f"{self.current_elevation_deg:.1f} ({'OK' if visible else 'OCULTO'})"
		self.metric_labels['Elevación [°]'].config(text=elv_txt, foreground=('#004080' if visible else '#aa0000'))
		self.metric_labels['Distancia [km]'].config(text=fmt(d/1000.0,"{:.0f}"))
		self.metric_labels['FSPL [dB]'].config(text=fmt(fspl,"{:.2f}"))
		self.metric_labels['Latencia OW [ms]'].config(text=fmt(lat_ow,"{:.2f}"))
		self.metric_labels['C/N0 [dBHz]'].config(text=fmt(cn0,"{:.2f}"))
		self.metric_labels['C/N [dB]'].config(text=fmt(cn,"{:.2f}"))
		self.metric_labels['EIRP [dBW]'].config(text=f"{self.core.eirp_dbw:.1f}")
		self.metric_labels['G/T [dB/K]'].config(text=f"{self.core.gt_dbk:.1f}")
		if self.running and self.start_time is not None:
			elapsed = time.time() - self.start_time
			self.history.append({'time_s': round(elapsed,3), 'orbit_angle_deg': round(self.orbit_angle_deg,2), 'mode': self.mode_var.get(), 'geo_longitude_deg': None if self.mode_var.get()=='LEO' else round(self.geo_slider_var.get(),2), 'elevation_deg': round(self.current_elevation_deg,2), 'visible': int(visible), 'slant_range_km': round(d/1000.0,2), 'fspl_db': None if math.isnan(fspl) else round(fspl,2), 'latency_ms_one_way': None if math.isnan(lat_ow) else round(lat_ow,3), 'cn0_dbhz': None if math.isnan(cn0) else round(cn0,2), 'cn_db': None if math.isnan(cn) else round(cn,2), 'eirp_dbw': round(self.core.eirp_dbw,2), 'gt_dbk': round(self.core.gt_dbk,2), 'bandwidth_mhz': round(self.core.calc.default_bandwidth_hz/1e6,3), 'frequency_ghz': round(self.core.calc.frequency_hz/1e9,4)})


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

