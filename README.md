# Educational LEO / GEO Satellite Link Simulator & Progressive Jamming Analysis Framework

An evolving project whose core is an interactive Tkinter GUI simulating a single satellite ↔ ground station link. It is designed to: (1) visualise LEO vs GEO orbital geometry, (2) expose and demystify a dynamic link budget, and (3) act as an interference scenarios (jamming), counter‑measures and large–scale constellation resilience analysis.

![alt text](image.png)
## Overview
The repository currently ships with one self‑contained script `JammerSimulator.py` implementing:
- Parameter loading (JSON) and a thin separation between core state and GUI.
- Simplified 2D rendering of Earth, an animated LEO satellite and a draggable GEO slot.
- Fundamental calculations: slant range, elevation, free space path loss (FSPL), propagation latency, C/N0 and C/N.
- Real‑time metrics panel plus CSV/XLSX historical export.

On top of this base we will iteratively build a modular framework covering operational and hostile phenomena in contemporary satellite systems (mega‑constellations, hybrid links, coordinated attacks, adaptive counter‑measures, environmental degradation, resilience strategies, etc.).

## Core Educational Objectives
1. Make the geometric & energy gap between LEO and GEO tangible (distance, FSPL, latency, future Doppler).
2. Provide link budget transparency: every term visible and traceable.
3. Layer complexity gradually: start with “ideal vacuum” (no extra losses, no interference); add factors incrementally with clear rationale.
4. Encourage rapid experimentation: editable parameters + clean exports.
5. Prepare a substrate for advanced evolutions (adaptive jamming, severe weather, hybrid redundancy, systemic resilience).

## Current State (MVP)
- Orbits: LEO (altitude from params) and GEO (fixed altitude). LEO orbit visually re‑scaled for clarity without altering physics.
- Displayed metrics: Elevation, Distance, FSPL, One‑way latency, C/N0, C/N, EIRP, G/T.
- Export: CSV and XLSX (formatted headers when `openpyxl` present).
- Progressive documentation in `PROGRESO.md` plus narrative scenario definitions under `Escenarios/` (Spanish source notes retained).

## Metrics & Models (Baseline)
| Category  | Implemented                      | Next expansion                                  |
|-----------|----------------------------------|-------------------------------------------------|
| Geometry  | Elevation, slant range           | Central angle, orbital period, visibility window|
| Dynamics  | (pending)                        | Orbital velocity, range rate, Doppler inst/max  |
| Power     | Fixed EIRP                       | Back‑off, saturated EIRP, power flux, received C|
| Losses    | FSPL                             | Feeder, misalignment, atmosphere, rain, polarisation, implementation |
| Noise     | Aggregate G/T                    | T_sky (clear / rain), T_rx, T_sys, N0, interference degradation |
| Performance| C/N0, C/N                       | Eb/N0, margin, Shannon capacity, spectral efficiency |
| Latency   | One‑way                          | RTT, processing & switching components          |
| Interf.   | —                                | C/I, C/(N+I), multi‑jammer aggregation          |
| Coverage  | —                                | Coverage area, estimated satellites for global, LEO+GEO hybrid |

## Layered Roadmap (Planned Evolution)
Rather than freezing “scenarios” into the README, we track cumulative functional layers:
1. Extended fundamentals: Doppler, RTT, power back‑off, detailed losses, decomposed noise.
2. Basic interference: single ground jammer, C/I and CINR.
3. Adaptive threat models: dynamic jammers (barrage / spot / swept / pulse) and carrier tracking.
4. Environmental impacts: rain attenuation, gaseous absorption, scintillation and margin erosion.
5. Multi‑source interference: aggregation, cooperative geometry analysis.
6. Constellation dynamics: handovers, opportunity windows, Doppler exploitation, satellite selection.
7. Progressive counter‑measures: adaptive power control, basic → advanced beam steering, frequency diversity.
8. Hybrid architectures: LEO+GEO continuity / failover and transparent switching.
9. Systemic resilience: mega‑constellation capacity retention, fragmentation, self‑healing behaviour.
10. Advanced / military layers: low probability of intercept, enriched hopping, coordinated multi‑satellite defence.

Each layer adds configurable inputs, new metrics and explanatory documentation to preserve physical traceability and conceptual clarity.

## Code Architecture
```
JammerSimulator.py
 ├─ ParameterLoader            (JSON parameter ingestion)
 ├─ Satellite / Constellation  (minimal orbital model)
 ├─ LEOEducationalCalculations (core formulas: FSPL, C/N0, latency)
 ├─ JammerSimulatorCore        (shared state + LEO/GEO calculators)
 └─ SimulatorGUI (Tkinter)     (interaction, drawing, metrics, export)
```
Future extensions will factor out modules (e.g. `losses.py`, `interference.py`, `orbital.py`) to keep the pedagogic core legible.

## Current Usage Flow
1. Run `python JammerSimulator.py`.
2. Select LEO or GEO mode.
3. Adjust EIRP, G/T, frequency and bandwidth.
4. (LEO) Start animation or drag the orbital angle slider to explore metric variation.
5. Observe right‑panel metrics (FSPL, latency, C/N0, etc.).
6. Export the time series to CSV/XLSX for offline analysis.

## Quick Install
Minimum: Python 3.10+ (Tkinter usually bundled). Optional: `openpyxl` for XLSX export.
```
pip install openpyxl
python JammerSimulator.py
```
On Windows, install the official Python distribution if Tkinter is missing.

## Parameters (JSON)
`SimulatorParameters.json` centralises altitudes, EIRP, G/T and base values. Upcoming loss, noise and interference parameters will extend it in a backward compatible manner.

## Design Principles
- Numerical transparency (show before over‑abstracting).
- Simplicity before maximal physical fidelity (e.g. aesthetic orbit scaling while keeping physics correct).
- Gradual layering: every new term (loss, noise, interference) accompanied by rationale & formula.
- Structured export for spreadsheets / scientific notebooks.

## Planned Extensibility (Technical Summary)
- Doppler: derived from orbital velocity & radial component → compensation illustration.
- Loss model: flexible dB summation with per‑component toggles & typical range annotations.
- Noise: decomposition T_sys = T_ant + T_rx + (∑ losses × equivalent temperature).
- Interference: configurable spectral density, multiple sources aggregated linearly.
- Advanced metrics: Eb/N0, margin, Shannon capacity, spectral utilisation.
- Coverage: per‑satellite area and constellation sizing for a minimum elevation.
- Hybrid failover: automatic link selection based on latency, margin, interference.

## Data Export
Current fields: time, mode, orbital angle / GEO longitude, elevation, visibility, distance, FSPL, latency, C/N0, C/N, EIRP, G/T, frequency, bandwidth.
Planned fields: RTT, Doppler, individual losses, total path loss, carrier power C, N0, Eb/N0, margin, SNR, capacity, utilisation, interference metrics, processing latencies.

## Contributing
While the core stabilises we welcome contributions focused on:
- Modular refactor (external calculation packages).
- Loss & noise implementations (simplified ITU‑R inspired models).
- Unit tests for formulas (pytest).
- Multi‑satellite / handover visuals.
- Basic GUI internationalisation (i18n).

Please open issues describing: (1) educational purpose, (2) formula & reference, (3) UI/export impact.

## Current Limitations
- Simplified 2D geometry (ground station at equator, no real inclination modeling yet).
- No atmospheric, rain or miscellaneous losses applied (all 0 dB by default).
- No interference or channel jitter modelling yet.
- Limited input validation (ranges / types) presently.

## Short‑Term Roadmap (Priorities)
1. Add RTT, Doppler and orbital period.
2. Introduce configurable loss block (all 0 by default).
3. Decompose noise and add Eb/N0 + margin.
4. Reorganise metrics panel into collapsible / basic vs advanced modes.
5. Document new formulas & update export schema.

## License
TBD (provisional). Recommendation: a permissive license (MIT / Apache‑2.0) to encourage educational adoption.

---
This README outlines the holistic direction without locking into rigid “scenario” sections: evolution is incremental and cumulative, focused on making each physical and operational layer of modern satellite ecosystems observable while preparing a foundation for threat and resilience analysis.
