export const capture_deck_screenshot = (
  deck,
  file_prefix = 'celldega',
  scale = 3
) => {
  const canvas = deck?.canvas;
  if (!canvas) {
    return;
  }

  const safe_scale = Math.max(1, Number(scale) || 1);
  const export_canvas = document.createElement('canvas');
  export_canvas.width = Math.max(1, Math.floor(canvas.width * safe_scale));
  export_canvas.height = Math.max(1, Math.floor(canvas.height * safe_scale));

  const ctx = export_canvas.getContext('2d');
  if (!ctx) {
    return;
  }

  ctx.setTransform(safe_scale, 0, 0, safe_scale, 0, 0);
  ctx.drawImage(canvas, 0, 0);

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const filename = `${file_prefix}-${timestamp}.png`;

  export_canvas.toBlob((blob) => {
    if (!blob) {
      return;
    }

    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }, 'image/png');
};
