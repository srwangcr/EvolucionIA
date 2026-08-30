from __future__ import annotations

import argparse
import json

from .config import Settings, load_settings
from .database import build_engine, init_db, load_latest_run_id, load_market_snapshots, session_factory
from .validation import compare_market_series, load_reference_dataset, membership_adjustment_recommendations


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evolucionia")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the market simulation")
    run_parser.add_argument("--ticks", type=int, default=None)
    run_parser.add_argument("--agents", type=int, default=None)
    run_parser.add_argument("--seed", type=int, default=None)
    run_parser.add_argument("--database-url", type=str, default=None)
    run_parser.add_argument("--initial-price", type=float, default=None)
    run_parser.add_argument("--compute-backend", choices=["serial", "process"], default=None)
    run_parser.add_argument("--compute-workers", type=int, default=None)
    run_parser.add_argument("--engine", choices=["python", "rust"], default="python",
                            help="Simulation engine: python (default) or rust")

    backtest_parser = subparsers.add_parser("backtest", help="Validate simulation outputs against a real market dataset")
    backtest_parser.add_argument("--dataset", type=str, required=True, help="CSV path with real market prices")
    backtest_parser.add_argument("--run-id", type=str, default=None, help="Simulation run_id to validate (latest by default)")
    backtest_parser.add_argument("--database-url", type=str, default=None)
    backtest_parser.add_argument("--output-json", type=str, default=None, help="Optional path to write metrics as JSON")

    calibrate_parser = subparsers.add_parser(
        "calibrate",
        help="Calibrate simulation parameters against real market data using Optuna"
    )
    calibrate_parser.add_argument(
        "--dataset", type=str, required=True,
        help="CSV path with real market prices for calibration"
    )
    calibrate_parser.add_argument(
        "--trials", type=int, default=100,
        help="Number of Optuna trials (default: 100)"
    )
    calibrate_parser.add_argument(
        "--study-name", type=str, default="evolucionia_calibration",
        help="Optuna study name"
    )
    calibrate_parser.add_argument(
        "--output", type=str, default=None,
        help="JSON file to export best parameters"
    )
    return parser


def _resolve_settings(args: argparse.Namespace) -> Settings:
    base = load_settings()
    return Settings(
        database_url=args.database_url or base.database_url,
        initial_agents=args.agents or base.initial_agents,
        ticks=args.ticks or base.ticks,
        generation_length=base.generation_length,
        initial_price=args.initial_price or base.initial_price,
        seed=args.seed or base.seed,
        resource_name=base.resource_name,
        read_database_url=base.read_database_url,
        compute_backend=args.compute_backend or base.compute_backend,
        compute_workers=args.compute_workers or base.compute_workers,
        output_dir=base.output_dir,
    )


def run_simulation(args: argparse.Namespace) -> dict:
    settings = _resolve_settings(args)
    engine = build_engine(settings.database_url)
    init_db(engine)
    session = session_factory(engine)()

    try:
        if args.engine == "rust":
            try:
                from .rust_engine import RustSimulationEngine
                simulation = RustSimulationEngine(settings, session)
                print("⚡ Usando motor Rust (M3)")
            except (ImportError, RuntimeError) as e:
                print(f"⚠️ Motor Rust no disponible: {e}")
                print("🐍 Usando motor Python (M2)")
                from .simulation import SimulationEngine
                simulation = SimulationEngine(settings, session)
        else:
            from .simulation import SimulationEngine
            simulation = SimulationEngine(settings, session)
            print("🐍 Usando motor Python (M2)")

        simulation.run(settings.ticks)
        return simulation.summary()
    finally:
        session.close()


def run_backtest(args: argparse.Namespace) -> dict:
    base = load_settings()
    database_url = args.database_url or base.database_url
    engine = build_engine(database_url)
    init_db(engine)

    run_id = args.run_id or load_latest_run_id(engine)
    if run_id is None:
        raise ValueError("No hay corridas disponibles para validar.")

    simulated_market = load_market_snapshots(engine, run_id)
    real_market = load_reference_dataset(args.dataset)
    metrics = compare_market_series(simulated_market, real_market)
    recommendations = membership_adjustment_recommendations(metrics)

    result = {
        "run_id": run_id,
        "dataset": args.dataset,
        "metrics": {
            "aligned_points": metrics.aligned_points,
            "mape_price": metrics.mape_price,
            "mean_return_gap": metrics.mean_return_gap,
            "volatility_gap": metrics.volatility_gap,
            "directional_accuracy": metrics.directional_accuracy,
            "ks_distance": metrics.ks_distance,
            "composite_score": metrics.composite_score,
        },
        "membership_recommendations": recommendations,
    }

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, ensure_ascii=False)

    return result


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "run":
        summary = run_simulation(args)
        print("\n" + "=" * 50)
        print("Simulation complete")
        print("=" * 50)
        for key, value in summary.items():
            print(f"{key}: {value}")
    elif args.command == "backtest":
        report = run_backtest(args)
        print("\n" + "=" * 50)
        print("Backtesting complete")
        print("=" * 50)
        print(f"run_id: {report['run_id']}")
        print(f"dataset: {report['dataset']}")
        for key, value in report["metrics"].items():
            print(f"{key}: {value}")
        print("membership_recommendations:")
        for recommendation in report["membership_recommendations"]:
            print(f"- {recommendation}")
    elif args.command == "calibrate":
        from .calibration import calibrate_from_cli
        calibrate_from_cli(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()