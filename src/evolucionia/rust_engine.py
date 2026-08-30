"""
Wrapper para el motor Rust (M3) - TODO EN RUST (con DB en disco).
"""

from __future__ import annotations

from dataclasses import dataclass
import random
from statistics import mean
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from .config import Settings
from .database import build_engine, finalize_run, init_db, new_run_id, save_tick, start_run, session_factory
from .models import Agent, Species, create_agent

try:
    import evolucionia_rust
    RUST_AVAILABLE = True
    print("✅ Módulo Rust cargado correctamente")
except ImportError:
    try:
        from ._rust import evolucionia_rust
        RUST_AVAILABLE = True
        print("✅ Módulo Rust cargado (desde _rust)")
    except ImportError:
        RUST_AVAILABLE = False
        print("⚠️ Módulo Rust no disponible. Usando fallback Python.")


@dataclass
class TickResult:
    tick: int
    price: float
    transactions: int
    buyers: int
    sellers: int
    survivors: int


class RustSimulationEngine:
    """Motor de simulación con Rust (todo incluido)."""

    def __init__(self, settings: Settings, session: Session):
        if not RUST_AVAILABLE:
            raise RuntimeError("Módulo Rust no disponible. Compila con 'maturin develop'.")

        self.settings = settings
        self.session = session
        self.tick_results: list[TickResult] = []
        self.generation_index = 0
        self.run_id = new_run_id()
        
        self._original_db_url = settings.database_url

        print("🔧 Creando agentes para Rust...")
        agents_data = self._create_agents_data(settings.initial_agents)
        print(f"🔧 {len(agents_data)} agentes creados")
        
        print("🔧 Inicializando motor Rust...")
        self._rust_engine = evolucionia_rust.RustSimulationEngine(
            agents_data=agents_data,
            initial_price=settings.initial_price,
            seed=settings.seed,
            generation_length=settings.generation_length,
            resource_name=settings.resource_name,
        )
        self.price = self._rust_engine.get_price()
        print(f"🔧 Precio inicial: {self.price}")

    def _create_agents_data(self, count: int) -> list[dict]:
        species_cycle = ["miner", "speculator", "consumer"]
        agents: list[dict] = []
        for agent_id in range(1, count + 1):
            species = species_cycle[(agent_id - 1) % len(species_cycle)]
            if species == "miner":
                balance, inventory, energy = 100.0, 10, 15.0
                buy_threshold, sell_threshold, production_rate = 9.5, 14.0, 3
                risk_tolerance, momentum_bias, reproduction_drive = 0.35, 0.55, 0.85
            elif species == "speculator":
                balance, inventory, energy = 150.0, 5, 12.0
                buy_threshold, sell_threshold, production_rate = 8.5, 13.5, 1
                risk_tolerance, momentum_bias, reproduction_drive = 0.8, 0.9, 0.55
            else:
                balance, inventory, energy = 80.0, 3, 18.0
                buy_threshold, sell_threshold, production_rate = 10.5, 15.5, 1
                risk_tolerance, momentum_bias, reproduction_drive = 0.2, 0.35, 0.45

            agents.append({
                "agent_id": agent_id,
                "species": species,
                "balance": balance,
                "inventory": inventory,
                "energy": energy,
                "buy_threshold": buy_threshold,
                "sell_threshold": sell_threshold,
                "production_rate": production_rate,
                "risk_tolerance": risk_tolerance,
                "momentum_bias": momentum_bias,
                "reproduction_drive": reproduction_drive,
            })
        return agents

    def _get_agents_from_rust(self) -> list[dict]:
        return self._rust_engine.get_agents()

    def _agent_rows(self) -> list[dict]:
        rust_agents = self._get_agents_from_rust()
        return [
            {
                "agent_id": data["agent_id"],
                "species": data["species"],
                "balance": round(data["balance"], 4),
                "inventory": data["inventory"],
                "energy": round(data["energy"], 4),
                "risk_tolerance": round(data["risk_tolerance"], 4),
                "momentum_bias": round(data["momentum_bias"], 4),
                "reproduction_drive": round(data["reproduction_drive"], 4),
                "alive": data["alive"],
                "generation": data["generation"],
            }
            for data in rust_agents
        ]

    def _macro_shock(self, tick: int) -> float:
        if tick % 15 == 0 and tick > 0:
            return 1.25
        if tick % 10 == 0 and tick > 0:
            return 0.88
        if tick % 7 == 0 and tick > 0:
            return 1.08
        return 1.0

    def run(self, ticks: int | None = None) -> list[TickResult]:
        original_url = self._original_db_url
        
        print("🔄 Usando DB en disco para M3...")
        engine = build_engine(original_url)
        init_db(engine)
        self.session = session_factory(engine)()
        
        total_ticks = ticks or self.settings.ticks
        print(f"🔄 Iniciando simulación con {total_ticks} ticks...")

        start_run(
            self.session,
            run_id=self.run_id,
            seed=self.settings.seed,
            ticks=total_ticks,
            initial_agents=self.settings.initial_agents,
            generation_length=self.settings.generation_length,
            initial_price=self.settings.initial_price,
            resource_name=self.settings.resource_name,
        )
        self.session.commit()

        previous_close = self.price
        last_close = self.price

        try:
            for tick in range(1, total_ticks + 1):
                if tick % 5 == 0 or tick == 1:
                    print(f"🔄 Tick {tick}/{total_ticks}")
                
                shock = self._macro_shock(tick)

                result = self._rust_engine.run_tick(tick, shock)
                self.price = result.price

                transactions = []
                if hasattr(result, 'tx_list') and result.tx_list:
                    for tx in result.tx_list:
                        transactions.append({
                            "buyer_id": tx[0],
                            "seller_id": tx[1],
                            "resource": self.settings.resource_name,
                            "price": round(tx[2], 4),
                            "quantity": tx[3],
                        })

                agent_rows = self._agent_rows()

                open_price = previous_close
                close_price = self.price
                market_row = {
                    "open_price": round(open_price, 4),
                    "high_price": round(max(open_price, close_price), 4),
                    "low_price": round(min(open_price, close_price), 4),
                    "close_price": round(close_price, 4),
                    "shock_factor": round(shock, 4),
                    "buyers_count": result.buyers,
                    "sellers_count": result.sellers,
                    "active_agents": result.survivors,
                }

                self.tick_results.append(
                    TickResult(
                        tick=tick,
                        price=close_price,
                        transactions=result.transactions,
                        buyers=result.buyers,
                        sellers=result.sellers,
                        survivors=result.survivors,
                    )
                )

                save_tick(
                    self.session,
                    self.run_id,
                    tick,
                    market_row,
                    transactions,
                    agent_rows,
                )

                last_close = previous_close
                previous_close = close_price

                if tick % self.settings.generation_length == 0:
                    self.generation_index += 1

            print("🔄 Simulación completada, guardando en DB...")

        except Exception as e:
            print(f"❌ Error en M3: {e}")
            import traceback
            traceback.print_exc()
            raise

        summary = self.summary()
        finalize_run(self.session, self.run_id, summary)
        self.session.commit()
        
        print("✅ Simulación M3 completada")
        return self.tick_results

    def summary(self) -> dict:
        alive = self._rust_engine.get_alive_count()
        rust_agents = self._get_agents_from_rust()
        wealths = []
        for data in rust_agents:
            if data["alive"]:
                wealths.append(data["balance"] + data["inventory"] * self.price)

        return {
            "run_id": self.run_id,
            "agents": len(rust_agents),
            "alive": alive,
            "final_price": round(self.price, 4),
            "mean_wealth": round(mean(wealths), 4) if wealths else 0.0,
            "generations": self.generation_index,
            "transactions": sum(r.transactions for r in self.tick_results),
        }