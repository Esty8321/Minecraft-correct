export function euclidean(
  a: { row: number; col: number },
  b: { row: number; col: number }
): number {
  const dr = a.row - b.row;
  const dc = a.col - b.col;
  return Math.sqrt(dr * dr + dc * dc);
}
