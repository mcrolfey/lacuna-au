from pathlib import Path
import yaml


def load_config(path: str = "config.yaml") -> dict:
    cfg = yaml.safe_load(Path(path).read_text())
    for key in ("data_dir", "report_dir"):
        Path(cfg["paths"][key]).mkdir(parents=True, exist_ok=True)
    return cfg
