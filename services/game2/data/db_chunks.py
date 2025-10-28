import torch 
from pathlib import Path

class ChunkDB:
    def __init__(self, base_dir ="db_chunks"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents= True, exist_ok= True)
       
       
    def save_chunk(self, chunk_id: str, board: torch.Tensor):
        path = self.base_dir / f"{chunk_id}.pt"
        torch.save(board, path) 
   
   
    def load_chunk(self, chunk_id: str) -> torch.Tensor:
        path = self.base_dir / f"{chunk_id}.pt"
        if not path.exists():
            raise FileNotFoundError(f"Chunk {chunk_id} not found")
        return torch.load(path)
    
        