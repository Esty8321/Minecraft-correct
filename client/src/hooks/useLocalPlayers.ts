import { useMemo } from 'react';
import { euclidean } from '../utils/distance';
// import {SEED_PLAYERS} from '../data/players'
export type LocalPlayer = {
  id: string;
  username: string;
  email: string;
  row: number;
  col: number;
  chunk_id: string;
};
const SEED_PLAYERS: LocalPlayer[] = [
  { id: "00000011", username: "Shira", email: "tamar48719@gmail.com", row: 3, col: 8, chunk_id: "chunk_0_0" },
  { id: "00000100", username: "AAA",   email: "AAA@gmail.com",        row: 5, col: 4, chunk_id: "chunk_0_0" }, // YOU
  { id: "00000101", username: "BBB",   email: "BBB@gmail.com",        row: 9, col: 6, chunk_id: "chunk_0_0" },
];

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

