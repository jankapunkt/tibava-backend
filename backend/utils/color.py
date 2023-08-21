import random
import numpy as np


def random_rgb():
    h = random.random() * 359 / 360
    s = 0.6
    v = 0.6
    return hsv_to_rgb(h, s, v)


def rgb_to_hex(rgb):
    rgb_string = "".join(hex(round(255 * x))[-2:] for x in rgb)
    return f"#{rgb_string}"


def hsv_to_rgb(h, s, v):
    if s == 0.0:
        return (v, v, v)
    i = int(h * 6.0)  # XXX assume int() truncates!
    f = (h * 6.0) - i
    p, q, t = v * (1.0 - s), v * (1.0 - s * f), v * (1.0 - s * (1.0 - f))
    i %= 6
    if i == 0:
        return (v, t, p)
    if i == 1:
        return (q, v, p)
    if i == 2:
        return (p, v, t)
    if i == 3:
        return (p, q, v)
    if i == 4:
        return (t, p, v)
    if i == 5:
        return (v, p, q)


def get_closest_color(color):
    color_dict = np.asarray(
        [
            [1.0, 1.0, 0.0],  # yellow
            [0.0, 0.0, 1.0],  # blue
            [1.0, 0.0, 0.0],  # red
            [0.0, 1.0, 1.0],  # cyan
            [0.0, 1.0, 0.0],  # green
            [1.0, 0.0, 1.0],  # magenta
            [1.0, 1.0, 1.0],  # white
            [0.0, 0.0, 0.0],  # black
            [0.5, 0.5, 0.5],  # gray
            [102 / 255.0, 51 / 255.0, 0],  # brown
            [25 / 255.0, 51 / 255.0, 0],  # dark green
            [0.0, 51 / 255.0, 51 / 255.0],  # dark blue
            [1.0, 204 / 255.0, 153 / 255.0],  # beige
        ]
    )
    color_index = np.argmin(np.abs(np.sum(np.subtract(color_dict, color), axis=1)))
    return [
        "yellow",
        "blue",
        "red",
        "cyan",
        "green",
        "magenta",
        "white",
        "black",
        "gray",
        "brown",
        "dark green",
        "dark blue",
        "beige",
    ][color_index]
