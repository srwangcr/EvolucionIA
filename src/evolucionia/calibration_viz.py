from typing import Optional
import plotly.express as px
import optuna


def plot_study(study_name: str, storage: Optional[str] = None):
    """
    Visualiza el progreso de optimización.
    
    Args:
        study_name: Nombre del estudio (debe coincidir con --study-name)
        storage: URL de almacenamiento (ej: "sqlite:///optuna_estudio.db")
                 Si es None, intenta usar el storage por defecto.
    """
    # Si no se especifica storage, intentar con el nombre
    if storage is None:
        # Probar primero en memoria, luego en SQLite
        try:
            # Intentar cargar desde memoria (storage=None)
            study = optuna.load_study(study_name=study_name, storage=None)
        except KeyError:
            # Si falla, intentar desde SQLite
            storage = f"sqlite:///optuna_{study_name}.db"
            study = optuna.load_study(study_name=study_name, storage=storage)
    else:
        study = optuna.load_study(study_name=study_name, storage=storage)
    
    df = study.trials_dataframe()
    
    if df.empty:
        print("⚠️ No hay trials para visualizar.")
        return
    
    fig = px.line(
        df,
        x="number",
        y="value",
        title=f"Optimización - {study_name}",
        labels={"number": "Trial", "value": "Composite Score"}
    )
    fig.show()
    
    # Mostrar mejores parámetros
    param_cols = [c for c in df.columns if c.startswith("params_")]
    if param_cols:
        best = df.loc[df["value"].idxmin()]
        print("🏆 Mejores parámetros:")
        for col in param_cols:
            print(f"   {col.replace('params_', '')}: {best[col]:.4f}")