from typing import Tuple

def chunk_id_from_coords(cx: int, cy: int) -> str:
    return f"{cx},{cy}"

def coords_from_chunk_id(cid: str) -> Tuple[int, int]:
    a, b = cid.split(",")
    return int(a), int(b)
