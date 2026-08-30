"""
Dashboard Streamlit para EvolucionIA con soporte M2/M3.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Agregar src al path para importaciones absolutas
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

from evolucionia.config import Settings, load_settings
from evolucionia.database import build_engine, init_db, session_factory
from evolucionia.simulation import SimulationEngine

try:
    from evolucionia.rust_engine import RustSimulationEngine, RUST_AVAILABLE
except ImportError:
    RUST_AVAILABLE = False
    RustSimulationEngine = None


def run_simulation(settings, engine_type: str = "python"):
    """Ejecuta simulación con el motor seleccionado."""
    engine = build_engine(settings.database_url)
    init_db(engine)
    session = session_factory(engine)()
    
    try:
        if engine_type == "rust" and RUST_AVAILABLE and RustSimulationEngine:
            st.info("⚡ Usando motor Rust (M3) - ultra rápido")
            sim = RustSimulationEngine(settings, session)
        else:
            st.info("🐍 Usando motor Python (M2)")
            sim = SimulationEngine(settings, session)
        
        start_time = time.perf_counter()
        results = sim.run(settings.ticks)
        elapsed = time.perf_counter() - start_time
        
        summary = sim.summary()
        summary["elapsed"] = elapsed
        summary["engine"] = engine_type
        
        return summary, results
    finally:
        session.close()


def plot_candlesticks(market_df: pd.DataFrame, current_tick: int | None = None):
    """Grafica velas OHLC con línea vertical en el tick actual."""
    fig = go.Figure(data=[
        go.Candlestick(
            x=market_df["tick"],
            open=market_df["open_price"],
            high=market_df["high_price"],
            low=market_df["low_price"],
            close=market_df["close_price"],
            name="OHLC"
        )
    ])
    
    if current_tick is not None and current_tick in market_df["tick"].values:
        fig.add_vline(
            x=current_tick,
            line_dash="dash",
            line_color="yellow",
            line_width=2,
            annotation_text=f"Tick {current_tick}",
            annotation_position="top right"
        )
    
    fig.update_layout(
        title="📊 Mercado - Velas",
        xaxis_title="Tick",
        yaxis_title="Precio",
        height=400,
        template="plotly_dark",
        xaxis=dict(range=[market_df["tick"].min(), market_df["tick"].max()])
    )
    return fig


def plot_price_shock(market_df: pd.DataFrame, current_tick: int | None = None):
    """Grafica precio y shock con línea vertical en el tick actual."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    fig.add_trace(
        go.Scatter(
            x=market_df["tick"],
            y=market_df["close_price"],
            name="Precio",
            line=dict(color="#00ff88")
        ),
        secondary_y=False,
    )
    
    fig.add_trace(
        go.Scatter(
            x=market_df["tick"],
            y=market_df["shock_factor"],
            name="Shock",
            line=dict(color="#ff6b6b", dash="dot")
        ),
        secondary_y=True,
    )
    
    if current_tick is not None and current_tick in market_df["tick"].values:
        fig.add_vline(
            x=current_tick,
            line_dash="dash",
            line_color="white",
            line_width=1.5,
        )
    
    fig.update_layout(
        title="📈 Precio vs Shock",
        xaxis_title="Tick",
        height=300,
        template="plotly_dark",
        xaxis=dict(range=[market_df["tick"].min(), market_df["tick"].max()])
    )
    fig.update_yaxes(title_text="Precio", secondary_y=False)
    fig.update_yaxes(title_text="Shock", secondary_y=True)
    return fig


def plot_wealth_distribution(agent_df: pd.DataFrame, tick: int | None = None, price: float = 8.0):
    """Grafica distribución de riqueza."""
    if agent_df.empty:
        fig = go.Figure()
        fig.update_layout(title="💰 Distribución de Riqueza - Sin datos", height=300, template="plotly_dark")
        return fig
    
    if tick is not None:
        agent_df = agent_df[agent_df["tick"] == tick]
    
    if "alive" in agent_df.columns:
        alive = agent_df.loc[agent_df["alive"] == True]
    else:
        alive = agent_df
    
    if alive.empty:
        fig = go.Figure()
        fig.update_layout(title=f"💰 Distribución de Riqueza - Tick {tick} (sin vivos)", height=300, template="plotly_dark")
        return fig
    
    wealth = alive["balance"] + alive["inventory"] * price
    
    fig = go.Figure(data=[
        go.Histogram(x=wealth, nbinsx=20, marker_color="#ffd93d", name="Riqueza")
    ])
    
    fig.update_layout(
        title=f"💰 Distribución de Riqueza - Tick {tick}",
        xaxis_title="Riqueza",
        yaxis_title="Frecuencia",
        height=300,
        template="plotly_dark",
    )
    return fig


def plot_survival(agent_df: pd.DataFrame, current_tick: int | None = None):
    """Grafica supervivencia por especie con línea vertical en el tick actual."""
    if agent_df.empty:
        fig = go.Figure()
        fig.update_layout(title="🧬 Supervivencia por Especie - Sin datos", height=300, template="plotly_dark")
        return fig
    
    if "tick" not in agent_df.columns or "species" not in agent_df.columns or "alive" not in agent_df.columns:
        fig = go.Figure()
        fig.update_layout(title="🧬 Supervivencia por Especie - Datos incompletos", height=300, template="plotly_dark")
        return fig
    
    survival = agent_df.groupby(["tick", "species"])["alive"].mean().reset_index()
    species_names = {"miner": "⛏️ Mineros", "speculator": "📈 Especuladores", "consumer": "🛒 Consumidores"}
    
    fig = go.Figure()
    for species in ["miner", "speculator", "consumer"]:
        data = survival[survival["species"] == species]
        if not data.empty:
            fig.add_trace(go.Scatter(
                x=data["tick"],
                y=data["alive"] * 100,
                name=species_names.get(species, species),
                mode="lines+markers",
            ))
    
    if current_tick is not None:
        fig.add_vline(x=current_tick, line_dash="dash", line_color="white", line_width=1.5)
    
    fig.update_layout(
        title="🧬 Supervivencia por Especie",
        xaxis_title="Tick",
        yaxis_title="% Vivos",
        height=300,
        template="plotly_dark",
    )
    return fig


def main():
    st.set_page_config(page_title="EvolucionIA Dashboard", page_icon="🧬", layout="wide")
    
    st.title("🧬 EvolucionIA - Dashboard")
    st.caption("Simulación de mercado con agentes heterogéneos")
    
    # SIDEBAR
    with st.sidebar:
        st.header("⚙️ Configuración")
        base_settings = load_settings()
        
        engine_options = ["python"]
        if RUST_AVAILABLE:
            engine_options.append("rust")
        
        engine_type = st.selectbox(
            "Motor de simulación",
            engine_options,
            format_func=lambda x: "🐍 Python (M2)" if x == "python" else "⚡ Rust (M3) - 10x más rápido",
        )
        
        col1, col2 = st.columns(2)
        with col1:
            ticks = st.number_input("Ticks", min_value=10, max_value=500, value=120, step=10)
            agents = st.number_input("Agentes", min_value=10, max_value=2000, value=200, step=10)
        with col2:
            seed = st.number_input("Semilla", min_value=0, max_value=9999, value=42, step=1)
            initial_price = st.number_input("Precio inicial", min_value=1.0, max_value=100.0, value=10.0, step=0.5)
        
        if st.button("🚀 Ejecutar simulación", type="primary", use_container_width=True):
            st.session_state.run_clicked = True
            st.session_state.ticks = ticks
            st.session_state.agents = agents
            st.session_state.seed = seed
            st.session_state.initial_price = initial_price
            st.session_state.engine_type = engine_type
            st.session_state.selected_tick = None
            st.session_state.current_run_id = None
    
    # EJECUTAR SIMULACIÓN
    if st.session_state.get("run_clicked", False):
        with st.spinner("Ejecutando simulación..."):
            settings = Settings(
                database_url=base_settings.database_url,
                read_database_url=base_settings.read_database_url,
                initial_agents=st.session_state.agents,
                ticks=st.session_state.ticks,
                generation_length=base_settings.generation_length,
                initial_price=st.session_state.initial_price,
                seed=st.session_state.seed,
                resource_name=base_settings.resource_name,
                compute_backend=base_settings.compute_backend,
                compute_workers=base_settings.compute_workers,
                output_dir=base_settings.output_dir,
            )
            
            summary, results = run_simulation(settings, st.session_state.engine_type)
            
            st.session_state.current_summary = summary
            st.session_state.current_run_id = summary["run_id"]
            st.session_state.settings = settings
            
        st.session_state.run_clicked = False
    
    # MOSTRAR RESULTADOS
    if st.session_state.get("current_run_id"):
        summary = st.session_state.current_summary
        settings = st.session_state.settings
        
        engine_db = build_engine(settings.database_url)
        
        market_df = pd.read_sql(
            "SELECT * FROM market_snapshots WHERE run_id = ? ORDER BY tick",
            engine_db,
            params=(summary["run_id"],)
        )
        agent_df = pd.read_sql(
            "SELECT * FROM agent_snapshots WHERE run_id = ? ORDER BY tick, agent_id",
            engine_db,
            params=(summary["run_id"],)
        )
        
        # Métricas
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("🏦 Precio final", f"{summary['final_price']:.4f}")
        with col2:
            st.metric("🧬 Vivos", f"{summary['alive']}/{summary['agents']}")
        with col3:
            st.metric("💰 Riqueza media", f"{summary['mean_wealth']:.2f}")
        with col4:
            st.metric("📊 Transacciones", summary['transactions'])
        with col5:
            engine_label = "⚡ Rust" if summary.get("engine") == "rust" else "🐍 Python"
            st.metric("⏱️ Tiempo", f"{summary['elapsed']:.3f}s", engine_label)
        
        # Slider
        if not market_df.empty:
            max_tick = market_df["tick"].max()
            
            if st.session_state.get("selected_tick") is None:
                st.session_state.selected_tick = max_tick
            
            selected_tick = st.slider(
                "🎯 Tick actual",
                min_value=1,
                max_value=max_tick,
                value=st.session_state.selected_tick,
                step=1,
                key="tick_slider"
            )
            st.session_state.selected_tick = selected_tick
            
            tick_data = market_df[market_df["tick"] == selected_tick]
            if not tick_data.empty:
                row = tick_data.iloc[0]
                st.caption(f"📊 Tick {selected_tick}: Open={row['open_price']:.4f}, High={row['high_price']:.4f}, Low={row['low_price']:.4f}, Close={row['close_price']:.4f}")
        
        # Gráficos
        st.subheader("📊 Visualizaciones")
        
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(plot_candlesticks(market_df, st.session_state.selected_tick), use_container_width=True)
        with col2:
            st.plotly_chart(plot_price_shock(market_df, st.session_state.selected_tick), use_container_width=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if not market_df.empty:
                st.plotly_chart(
                    plot_wealth_distribution(agent_df, st.session_state.selected_tick, summary['final_price']),
                    use_container_width=True
                )
            else:
                st.info("No hay datos de mercado para mostrar")
        with col2:
            st.plotly_chart(plot_survival(agent_df, st.session_state.selected_tick), use_container_width=True)
        
        # 📋 LEDGER DE TRANSACCIONES - MEJORADO
        with st.expander("📋 Ledger de transacciones", expanded=True):
            tx_df = pd.read_sql(
                "SELECT * FROM transactions WHERE run_id = ? ORDER BY tick",
                engine_db,
                params=(summary["run_id"],)
            )
            
            if not tx_df.empty:
                total_tx = len(tx_df)
                st.write(f"**📊 Total transacciones en la corrida:** {total_tx}")
                
                # Mostrar distribución de transacciones por tick
                tx_dist = tx_df.groupby("tick").size().reset_index(name="count")
                st.write("**📈 Distribución de transacciones por tick:**")
                st.bar_chart(tx_dist.set_index("tick"))
                
                # Transacciones del tick seleccionado
                if st.session_state.selected_tick is not None:
                    tx_filtered = tx_df[tx_df["tick"] == st.session_state.selected_tick]
                    if not tx_filtered.empty:
                        st.write(f"**✅ Transacciones en el tick {st.session_state.selected_tick}:** {len(tx_filtered)}")
                        st.dataframe(tx_filtered, use_container_width=True)
                    else:
                        st.info(f"ℹ️ No hay transacciones en el tick {st.session_state.selected_tick}.")
                        st.write("**📋 Muestra de transacciones (otros ticks):**")
                        st.dataframe(tx_df.head(10), use_container_width=True)
                else:
                    st.dataframe(tx_df, use_container_width=True)
            else:
                st.info("No hay transacciones en esta corrida")


if __name__ == "__main__":
    main()