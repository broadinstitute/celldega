export const visibleTiles = (min_x, max_x, min_y, max_y, tileSize) => {
	const startTileX = Math.floor(min_x / tileSize);
	const endTileX = Math.floor(max_x / tileSize);
	const startTileY = Math.floor(min_y / tileSize);
	const endTileY = Math.floor(max_y / tileSize);

	const tiles = [];
	for (let x = startTileX; x <= endTileX; x++) {
		for (let y = startTileY; y <= endTileY; y++) {
			tiles.push({ tileX: x, tileY: y, name: x + '_' + y });
		}
	}
	return tiles;
}