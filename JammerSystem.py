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
from enum import Enum

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
    power_tx_dbw: float = 40.0  # dBW
    antenna_gain_dbi: float = 3.0  # dBi  
    frequency_ghz: float = 12.0  # GHz
    bandwidth_mhz: float = 20.0  # MHz
    
    # Posición relativa a GS (km)
    distance_from_gs_km: float = 10.0
    azimuth_deg: float = 0.0  # Ángulo desde GS
    
    # Estado
    active: bool = True
    
    @property
    def eirp_dbw(self) -> float:
        """EIRP calculado"""
        return self.power_tx_dbw + self.antenna_gain_dbi
    
    @property
    def type_description(self) -> str:
        """Descripción del tipo de jammer"""
        descriptions = {
            JammerType.BARRAGE: "Banda Ancha (100-1000 MHz)",
            JammerType.SPOT: "Banda Estrecha (1-10 MHz)", 
            JammerType.SMART: "Adaptativo con ML"
        }
        return descriptions.get(self.jammer_type, "Desconocido")

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
        self.power_tx_var = tk.DoubleVar(value=40.0)
        ttk.Spinbox(power_frame, from_=20, to=80, increment=1, 
                   textvariable=self.power_tx_var, width=10).grid(row=0, column=1, sticky="w")
        
        # EIRP calculado (solo lectura)
        ttk.Label(power_frame, text="EIRP [dBW]:").grid(row=1, column=0, sticky="w")
        self.eirp_label = ttk.Label(power_frame, text="43.0", foreground="green")
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
        
        # === POSICIÓN ===
        pos_frame = ttk.LabelFrame(main_frame, text="Posición Relativa a GS", padding="5")
        pos_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=5)
        
        ttk.Label(pos_frame, text="Distancia [km]:").grid(row=0, column=0, sticky="w")
        self.distance_var = tk.DoubleVar(value=10.0)
        ttk.Spinbox(pos_frame, from_=1, to=1000, increment=1,
                   textvariable=self.distance_var, width=10).grid(row=0, column=1, sticky="w")
        
        ttk.Label(pos_frame, text="Azimut [°]:").grid(row=1, column=0, sticky="w")
        self.azimuth_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(pos_frame, from_=0, to=360, increment=15,
                   textvariable=self.azimuth_var, width=10).grid(row=1, column=1, sticky="w")
        
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
    
    def _save_config(self):
        """Guardar configuración"""
        try:
            # Validar nombre único
            name = self.name_var.get().strip()
            if not name:
                messagebox.showerror("Error", "El nombre no puede estar vacío")
                return
            
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
        inner_frame.pack(fill="x", padx=3, pady=2)
        
        # Nombre del jammer (izquierda)
        name_label = ttk.Label(inner_frame, text=config.name, font=("Segoe UI", 8, "bold"))
        name_label.pack(side="left")
        
        # Botón eliminar (derecha)
        delete_btn = ttk.Button(inner_frame, text="×", width=2,
                               command=lambda: self.delete_callback(config.id))
        delete_btn.pack(side="right")
        
        # Info técnica compacta (centro)
        info_text = f"{config.jammer_type.value[:4]} | {config.eirp_dbw:.0f}dBW | {config.distance_from_gs_km:.0f}km"
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
        self.jammers_frame = ttk.LabelFrame(self.parent_frame, text="Jammers", padding="3")
        
        # Botón añadir jammer siempre visible (más compacto)
        self.add_button = ttk.Button(self.jammers_frame, text="+ Añadir Jammer", 
                                    command=self._add_jammer)
        self.add_button.pack(pady=2)
        
        # Container para jammers con altura dinámica
        self.jammers_container = ttk.Frame(self.jammers_frame)
        self.jammers_container.pack(fill='x')
    
    def get_panel(self) -> ttk.Widget:
        """Obtener el panel principal"""
        return self.jammers_frame
    
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
    
    def get_jammer_positions(self, gs_lat: float, gs_lon: float, earth_rotation_deg: float) -> List[Dict]:
        """Calcular posiciones de jammers para visualización"""
        positions = []
        
        for config in self.get_active_jammers():
            # Calcular posición relativa a GS considerando rotación terrestre
            azimuth_corrected = (config.azimuth_deg + earth_rotation_deg) % 360
            
            # Conversión a coordenadas cartesianas (simplificada)
            dx = config.distance_from_gs_km * math.sin(math.radians(azimuth_corrected))
            dy = config.distance_from_gs_km * math.cos(math.radians(azimuth_corrected))
            
            positions.append({
                'id': config.id,
                'name': config.name,
                'lat': gs_lat + dy / 111.0,  # Aproximación: 1° ≈ 111 km
                'lon': gs_lon + dx / (111.0 * math.cos(math.radians(gs_lat))),
                'dx': dx,
                'dy': dy,
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
