def _avg_region(frame, width, height, x0, y0, x1, y1):
    x0 = max(0, min(width - 1, x0))
    x1 = max(x0 + 1, min(width, x1))
    y0 = max(0, min(height - 1, y0))
    y1 = max(y0 + 1, min(height, y1))
    total = [0, 0, 0]
    count = 0
    stride = width * 4
    for y in range(y0, y1):
        row = y * stride
        for x in range(x0, x1):
            i = row + x * 4
            total[0] += frame[i + 2]
            total[1] += frame[i + 1]
            total[2] += frame[i]
            count += 1
    if not count:
        return (0, 0, 0)
    return (total[0] // count, total[1] // count, total[2] // count)


def map_edges(frame, width, height, led_count):
    """Kodi RenderCapture is BGRA. Returns list of (r, g, b)."""
    band = max(1, min(width, height) // 8)
    top = max(1, int(led_count * 0.32))
    bottom = max(1, int(led_count * 0.32))
    sides = max(1, (led_count - top - bottom) // 2)
    extra = led_count - (top + bottom + sides * 2)
    top += extra

    colors = []
    for i in range(top):
        x0 = int(i * width / top)
        x1 = int((i + 1) * width / top)
        colors.append(_avg_region(frame, width, height, x0, 0, x1, band))
    for i in range(sides):
        y0 = int(i * height / sides)
        y1 = int((i + 1) * height / sides)
        colors.append(_avg_region(frame, width, height, width - band, y0, width, y1))
    for i in range(bottom):
        x0 = int((bottom - 1 - i) * width / bottom)
        x1 = int((bottom - i) * width / bottom)
        colors.append(_avg_region(frame, width, height, x0, height - band, x1, height))
    for i in range(sides):
        y0 = int((sides - 1 - i) * height / sides)
        y1 = int((sides - i) * height / sides)
        colors.append(_avg_region(frame, width, height, 0, y0, band, y1))
    return colors[:led_count]


def rgb_to_rgbw(r, g, b):
    white = min(r, g, b)
    return (r - white, g - white, b - white, white)
