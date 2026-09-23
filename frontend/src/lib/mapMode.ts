/** GridSim must never initialize remote map tile sources. */
export function assertNoGridTiles(mode: string, tileUrls: string[]): void {
  if (mode === 'gridsim' && tileUrls.length) {
    throw new Error(`GridSim cannot use basemap tiles: ${tileUrls.join(', ')}`);
  }
}
