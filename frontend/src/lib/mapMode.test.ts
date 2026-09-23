import { describe, expect, it } from 'vitest';
import { assertNoGridTiles } from './mapMode';

describe('GridSim basemap guard', () => {
  it('rejects tile URLs in GridSim mode', () => expect(() => assertNoGridTiles('gridsim', ['https://tiles.example/{z}/{x}/{y}.png'])).toThrow('GridSim cannot use basemap tiles'));
  it('allows no-tile vector mode', () => expect(() => assertNoGridTiles('gridsim', [])).not.toThrow());
});
