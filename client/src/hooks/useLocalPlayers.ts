import { useMemo } from 'react';
import { SEED_PLAYERS } from '../data/players';
import { euclidean } from '../utils/distance';

export function useLocalPlayers(
  currentChunkId: string = 'chunk_0_0',
  currentPlayerId: string = '00000100'
) {
  const all = SEED_PLAYERS;

  const playersInChunk = useMemo(() => {
    return all.filter(p => p.chunk_id === currentChunkId);
  }, [all, currentChunkId]);

  const me = useMemo(() => {
    return playersInChunk.find(p => p.id === currentPlayerId) || null;
  }, [playersInChunk, currentPlayerId]);

  // ✅ חדש: רשימת "אחרים בלבד"
  const othersInChunk = useMemo(() => {
    return me ? playersInChunk.filter(p => p.id !== me.id) : playersInChunk;
  }, [playersInChunk, me]);

  // ✅ nearest שלא יכול להיות אני
  const nearest = useMemo(() => {
    if (!me) return null;
    let best = null as typeof me | null;
    let bestDist = Number.POSITIVE_INFINITY;
    for (const p of othersInChunk) {
      const d = euclidean(me, p);
      if (d < bestDist) {
        bestDist = d;
        best = p;
      }
    }
    return best;
  }, [me, othersInChunk]);

  return { playersInChunk, othersInChunk, nearest, me };
}

