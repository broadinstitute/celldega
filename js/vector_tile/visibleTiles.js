export const visibleTiles = (minX, maxX, minY, maxY, tileSize) => {
	const startTileX = Math.floor(minX / tileSize);
	const endTileX = Math.floor(maxX / tileSize);
	const startTileY = Math.floor(minY / tileSize);
	const endTileY = Math.floor(maxY / tileSize);

	const tiles = [];
	for (let x = startTileX; x <= endTileX; x++) {
		for (let y = startTileY; y <= endTileY; y++) {
			tiles.push({ tileX: x, tileY: y, name: x + '_' + y });
		}
	}
	return tiles;
}