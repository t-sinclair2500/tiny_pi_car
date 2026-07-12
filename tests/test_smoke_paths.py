from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_masterpi_layout():
    assert (ROOT / "MasterPi" / "MasterPi.py").is_file()
    assert (ROOT / "MasterPi" / "masterpi_sdk").is_dir()


def test_playground_package():
    assert (ROOT / "playground" / "smoke.py").is_file()
