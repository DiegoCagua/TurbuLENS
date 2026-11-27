def eval_folder_name(date: dt.date, start: dt.time, end: dt.time, now: dt.datetime, single: bool = False) -> str:
    """Nombre de la subcarpeta de una evaluación, p. ej. ``evaluadas_dia_20261019_18-23_20261126_100953``."""
    hrs = f"{start.hour:02d}" if single else f"{start.hour:02d}-{end.hour:02d}"
    return f"evaluadas_dia_{date:%Y%m%d}_{hrs}_{now:%Y%m%d_%H%M%S}"
