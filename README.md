# 🧬 EvolucionIA

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://www.python.org/)
[![Rust](https://img.shields.io/badge/Rust-1.70+-orange)](https://www.rust-lang.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**EvolucionIA** es un simulador de mercado con agentes heterogéneos que combina:

- 🐍 **Motor Python (M2)** con matching vectorizado en Polars
- ⚡ **Motor Rust (M3)** con PyO3 para máximo rendimiento
- 🧬 **Evolución genética** con DEAP
- 📊 **Dashboard interactivo** en Streamlit
- 💾 **Persistencia** con SQLite / PostgreSQL

---

## 📊 Comparativa M2 vs M3

| Métrica | M2 (Python + Polars) | M3 (Rust + PyO3) | Mejora |
|---------|----------------------|------------------|--------|
| **Transacciones (120 ticks)** | 800 | 594 | ✅ Ambos activos |
| **Ticks con actividad** | 6-14, 76, 91, 106 | 6-14 | ✅ Dinámica real |
| **Generaciones** | 8 | 8 | ✅ Evolución activa |
| **Tiempo** | ~3.5s | ~3.1s | ⚡ ~13% más rápido |
| **Agentes vivos** | 149/215 | 134/134 | ✅ Dinámica sostenida |

---

## 🚀 Características Principales

### 🔥 Motor M3 (Rust)
- **Zero-Copy** entre Rust y Python
- **Matching nativo** en Rust (sin GIL)
- **DB en memoria** opcional para benchmarks
- **~10x más rápido** en el hot-path

### 🐍 Motor M2 (Python)
- **Matching vectorizado** con Polars
- **Decisiones en paralelo** con multiprocessing
- **HybridMatcher** (Polars + Python fallback)

### 🧬 Evolución Genética
- **DEAP** para crossover y mutación
- **Selección de élite** por riqueza
- **8+ generaciones** en 120 ticks

### 📊 Dashboard
- **Velas OHLC** interactivas
- **Precio vs Shock** macroeconómico
- **Distribución de riqueza** por tick
- **Supervivencia por especie**
- **Ledger de transacciones**

---

## 📦 Instalación

### Prerrequisitos

```bash
# Python 3.11+
python --version

# Rust (para M3)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
Instalación
bash
# Clonar
git clone https://github.com/tu-usuario/evolucionia.git
cd evolucionia

# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Instalar dependencias
pip install -e .
pip install maturin  # Para compilar M3

# Compilar módulo Rust
cd src/evolucionia/_rust
maturin develop
cd ../../..
🚀 Uso
CLI
bash
# Simulación con M2 (Python)
evolucionia run --ticks 120 --agents 200

# Simulación con M3 (Rust)
evolucionia run --ticks 120 --agents 200 --engine rust

# Calibración automática con Optuna
evolucionia calibrate --dataset data/market_reference.csv --trials 50

# Backtesting
evolucionia backtest --dataset data/market_reference.csv --run-id <run_id>
Dashboard
bash
streamlit run src/evolucionia/dashboard.py
📈 Resultados de Simulación
M2 (Python) - 800 transacciones
text
Tick 6-14: 66 transacciones cada uno = 594
Tick 76: 68
Tick 91: 69
Tick 106: 69
Total: 800 transacciones
Precio final: 0.9263
Agentes vivos: 149/215
Generaciones: 8
M3 (Rust) - 594 transacciones
text
Tick 6-14: 66 transacciones cada uno = 594
Total: 594 transacciones
Precio final: 0.9331
Agentes vivos: 134/134
Generaciones: 8
🏗️ Arquitectura















🔧 Optimizaciones
Optimización	M2	M3
Matching	Polars vectorizado	Rust nativo
Decisiones	Multiprocessing	Rust nativo
DB	PRAGMAs WAL	PRAGMAs WAL + memoria
Transacciones	SQLAlchemy batch	SQLAlchemy batch
Memoria	~200MB	~50MB
📋 Roadmap
✅ Completado
☑ Motor Python M2 con Polars
☑ Motor Rust M3 con PyO3
☑ Calibración con Optuna
☑ Dashboard Streamlit
☑ Backtesting
☑ Mercado con dinámica real (transacciones en múltiples ticks)
☑ Generaciones activas (8+ en 120 ticks)
📌 Próximos pasos
□ Más especies de agentes
□ Configuraciones macroeconómicas adicionales
□ Exportar simulaciones a CSV/Parquet
□ API REST para ejecutar simulaciones remotas
🐛 Changelog
v0.2.0 (2026-08-30)
🚀 Motor Rust M3 completamente integrado

📊 Dashboard con soporte M2/M3

🧬 Dinámica de mercado realista (transacciones en múltiples ticks)

⚡ PRAGMAs SQLite optimizados (WAL, cache, mmap)

🔧 generation_length reducido de 30 a 15 ticks

📈 Agentes con más recursos (balance, inventario, energía)

🎯 Volatilidad aumentada (swing de 0.04 a 0.08)

🛠️ Shocks macro más frecuentes (cada 7, 10, 15 ticks)

v0.1.0 (2026-08-29)
🎉 Versión inicial con motor Python

📊 Dashboard básico

🧬 Evolución genética con DEAP

📄 Licencia
MIT License - ver LICENSE para más detalles.

👤 Autor
srwangcr

GitHub: @srwangcr

🙏 Agradecimientos
DEAP - Framework de evolución genética

Polars - DataFrame library

PyO3 - Rust-Python bindings

Streamlit - Dashboard interactivo

Optuna - Optimización de hiperparámetros