"""Load and validate all supply chain data from CSV files."""

import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def load_locations() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "locations.csv")
    return df


def load_inventory() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "inventory.csv")
    df["last_updated"] = pd.to_datetime(df["last_updated"])
    return df


def load_production_orders() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "production_orders.csv")
    df["planned_completion"] = pd.to_datetime(df["planned_completion"])
    df["actual_completion"] = pd.to_datetime(df["actual_completion"])
    return df


def load_shipments() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "shipments.csv")
    df["departure_date"] = pd.to_datetime(df["departure_date"])
    df["original_eta"] = pd.to_datetime(df["original_eta"])
    df["eta"] = pd.to_datetime(df["eta"])
    df["actual_arrival"] = pd.to_datetime(df["actual_arrival"], errors="coerce")
    # Treat blank vessel_id as None
    df["vessel_id"] = df["vessel_id"].where(df["vessel_id"].notna() & (df["vessel_id"] != ""), None)
    return df


def load_vessels() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "vessels.csv")
    df["departure_date"] = pd.to_datetime(df["departure_date"])
    df["scheduled_eta"] = pd.to_datetime(df["scheduled_eta"])
    df["estimated_eta"] = pd.to_datetime(df["estimated_eta"])
    df["last_position_update"] = pd.to_datetime(df["last_position_update"])
    return df


def load_all() -> dict:
    """Return a dict of all DataFrames."""
    return {
        "locations": load_locations(),
        "inventory": load_inventory(),
        "production_orders": load_production_orders(),
        "shipments": load_shipments(),
        "vessels": load_vessels(),
    }
