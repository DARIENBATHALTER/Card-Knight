"""Global story flags — gate tutorial events and NPC dialogue."""

flags: dict = {
    # Tutorial Act 0 — Cardhollow
    'package_accepted':      False,   # courier master gave Oden the delivery
    # Tutorial Act 1 — Briar Road
    'misdeal_road_beaten':   False,   # first road encounter won
    # Tutorial Act 2 — Veilgate
    'arrived_veilgate':      False,   # player entered Veilgate
    'met_edric':             False,   # talked to Edric
    'received_deck':         False,   # Edric gave Oden the full starter deck
    # Tutorial Act 3 — Return
    'saw_smoke':             False,   # smoke cutscene triggered leaving Veilgate
    'home_shrine_defeated':  False,   # shrine misdeals defeated on return
}


def get(key: str) -> bool:
    return flags.get(key, False)


def set_flag(key: str) -> None:
    flags[key] = True
