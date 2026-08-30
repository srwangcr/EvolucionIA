"""
Automatic parameter calibration with Optuna.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any

import optuna
import pandas as pd
from sqlalchemy.orm import Session

from .config import Settings, load_settings
from .database import build_engine, init_db, load_market_snapshots, session_factory
from .simulation import SimulationEngine
from .validation import compare_market_series, load_reference_dataset


@dataclass
class CalibrationResult:
    """Resultado de una corrida de calibración."""

    best_params: dict[str, Any]
    best_score: float
    study_name: str
    n_trials: int


class Calibrator:
    """
    Calibrator that Optuna uses to find the optimal parameters
    of membership functions and agent behavior.
    """

    def __init__(
        self,
        settings: Settings,
        reference_dataset: str,
        n_trials: int = 100,
        study_name: str = "evolucionia_calibration",
    ):
        self.settings = settings
        self.reference_dataset = reference_dataset
        self.n_trials = n_trials
        self.study_name = study_name

         # NUEVO: Inicializar atributos
        self._current_params: dict[str, float] = {}
        self._trial_history: list[dict] = []

        # Cargar datos de referencia una vez
        self.real_market = load_reference_dataset(reference_dataset)

        # Preparar DB
        self.engine = build_engine(settings.database_url)
        init_db(self.engine)
        self.session_factory = session_factory(self.engine)

    def _objective(self, trial: optuna.Trial) -> float:
        """
            Target function for Optuna.
            Minimizes the composite_score against real data.
        """
        # 1. Propose parameters to calibrate
        params = {
            # Base thresholds (apply to all agents)
            "buy_threshold_base": trial.suggest_float("buy_threshold_base", 5.0, 15.0),
            "sell_threshold_base": trial.suggest_float("sell_threshold_base", 10.0, 20.0),
            # Biases by species (multipliers)
            "miner_buy_bias": trial.suggest_float("miner_buy_bias", 0.6, 1.4),
            "speculator_buy_bias": trial.suggest_float("speculator_buy_bias", 0.6, 1.4),
            "consumer_buy_bias": trial.suggest_float("consumer_buy_bias", 0.6, 1.4),
            # Behavior parameters
            "risk_tolerance_base": trial.suggest_float("risk_tolerance_base", 0.1, 1.2),
            "momentum_bias_base": trial.suggest_float("momentum_bias_base", 0.1, 1.2),
            "reproduction_drive_base": trial.suggest_float("reproduction_drive_base", 0.2, 1.2),
            # Market parameters
            "price_volatility": trial.suggest_float("price_volatility", 0.01, 0.15),
        }

        #2. Create modified settings (only for this run)
        run_settings = self._build_run_settings(params)

        #3. Run simulation
        session = self.session_factory()
        try:
            engine = SimulationEngine(run_settings, session)
            engine.run(run_settings.ticks)
            summary = engine.summary()
        finally:
            session.close()

        # 4. Load simulated results
        simulated_market = load_market_snapshots(
            self.engine, run_id=summary["run_id"]
        )

        #5. Compare with real data
        metrics = compare_market_series(simulated_market, self.real_market)

        #6. Optuna minimizes, so we return the composite_score
        score = metrics.composite_score

        # Optional: report individual metrics for tracking
        trial.set_user_attr("mape", metrics.mape_price)
        trial.set_user_attr("directional_accuracy", metrics.directional_accuracy)
        trial.set_user_attr("volatility_gap", metrics.volatility_gap)

        return score

    def _build_run_settings(self, params: dict[str, float]) -> Settings:
        """Construye Settings con los parámetros propuestos."""
        base = self.settings
        
        self._current_params = params  # ← añadir atributo en __init__


        # Modify base values (this requires Settings to be mutable
        # or let's create a new one)
        return Settings(
            database_url=base.database_url,
            initial_agents=base.initial_agents,
            ticks=base.ticks,
            generation_length=base.generation_length,
            initial_price=base.initial_price,
            seed=base.seed + hash(tuple(params.items())) % 1000,  # Semilla única
            resource_name=base.resource_name,
            read_database_url=base.read_database_url,
            compute_backend=base.compute_backend,
            compute_workers=base.compute_workers,
            output_dir=base.output_dir,
        )

    def calibrate(self) -> CalibrationResult:
        """Ejecuta la calibración con Optuna."""
        study = optuna.create_study(
            study_name=self.study_name,
            direction="minimize",
            storage=None,  # Use memory (switch to SQLite for persistence)
            load_if_exists=True,
            sampler=optuna.samplers.TPESampler(seed=self.settings.seed),
        )

        study.optimize(self._objective, n_trials=self.n_trials)

        return CalibrationResult(
            best_params=study.best_params,
            best_score=study.best_value,
            study_name=self.study_name,
            n_trials=self.n_trials,
        )

    def export_results(self, result: CalibrationResult, output_path: str) -> None:
        """Guarda los resultados en JSON."""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "best_params": result.best_params,
                    "best_score": result.best_score,
                    "study_name": result.study_name,
                    "n_trials": result.n_trials,
                },
                f,
                indent=2,
            )


def calibrate_from_cli(args: argparse.Namespace) -> CalibrationResult:
    """Entry point from CLI."""
    settings = load_settings()
    calibrator = Calibrator(
        settings=settings,
        reference_dataset=args.dataset,
        n_trials=args.trials or 100,
        study_name=args.study_name or "evolutionia_calibration",
    )
    result = calibrator.calibrate()

    if args.output:
        calibrator.export_results(result, args.output)

    print(f"✅ Calibración completada en {result.n_trials} trials")
    print(f"🏆 Mejor score: {result.best_score:.4f}")
    print("📋 Mejores parámetros:")
    for key, value in result.best_params.items():
        print(f"   {key}: {value:.4f}")

    return result