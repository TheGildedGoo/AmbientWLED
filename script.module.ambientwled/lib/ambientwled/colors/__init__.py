"""Color pipeline stubs for Week 2+.

Week 2 will add:
  - four_edge_mapper: sample L/R/T/B edges from a downsampled frame
  - mean / p75 aggregators, blackbar detect, gamma 2.2, sat boost
  - RGBW: W = min(R,G,B) before DDP send
"""


def trivial_mean_rgb(pixels):
    """Trivial helper: mean of (r,g,b) tuples. Placeholder for Week 2 tests."""
    if not pixels:
        return (0, 0, 0)
    n = len(pixels)
    r = sum(p[0] for p in pixels) // n
    g = sum(p[1] for p in pixels) // n
    b = sum(p[2] for p in pixels) // n
    return (r, g, b)
