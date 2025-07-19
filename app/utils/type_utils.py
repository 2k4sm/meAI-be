def safe_str(val) -> str:
    return str(val) if val is not None else ""

def safe_int(val) -> int:
    try:
        return int(val)
    except Exception:
        return 0 