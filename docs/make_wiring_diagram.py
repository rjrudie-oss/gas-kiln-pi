"""Generate a labeled Raspberry Pi 5 wiring diagram for the kiln controller.

Phase 1 (thermocouple) + phase 2 (relay) connections on the 40-pin header.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# (physical pin) -> (label, category)
PINS = {
    1: ("3V3", "3v3"), 2: ("5V", "5v"),
    3: ("GPIO2 SDA", "io"), 4: ("5V", "5v"),
    5: ("GPIO3 SCL", "io"), 6: ("GND", "gnd"),
    7: ("GPIO4", "io"), 8: ("GPIO14 TXD", "io"),
    9: ("GND", "gnd"), 10: ("GPIO15 RXD", "io"),
    11: ("GPIO17", "io"), 12: ("GPIO18", "io"),
    13: ("GPIO27", "io"), 14: ("GND", "gnd"),
    15: ("GPIO22", "io"), 16: ("GPIO23", "io"),
    17: ("3V3", "3v3"), 18: ("GPIO24", "io"),
    19: ("GPIO10 MOSI", "spi"), 20: ("GND", "gnd"),
    21: ("GPIO9 MISO", "spi"), 22: ("GPIO25", "io"),
    23: ("GPIO11 SCLK", "spi"), 24: ("GPIO8 CE0", "io"),
    25: ("GND", "gnd"), 26: ("GPIO7 CE1", "io"),
    27: ("GPIO0", "io"), 28: ("GPIO1", "io"),
    29: ("GPIO5", "spi"), 30: ("GND", "gnd"),
    31: ("GPIO6", "io"), 32: ("GPIO12", "io"),
    33: ("GPIO13", "io"), 34: ("GND", "gnd"),
    35: ("GPIO19", "io"), 36: ("GPIO16", "io"),
    37: ("GPIO26", "io"), 38: ("GPIO20", "io"),
    39: ("GND", "gnd"), 40: ("GPIO21", "io"),
}

COLORS = {
    "3v3": "#f4a300", "5v": "#d62728", "gnd": "#555555",
    "spi": "#1f77b4", "io": "#2ca02c", "none": "#cfcfcf",
}

# pin -> (device wire label, highlight color)
USED = {
    1: ("MAX31856 VIN", "#f4a300"),
    6: ("MAX31856 GND", "#555555"),
    23: ("MAX31856 SCK", "#1f77b4"),
    21: ("MAX31856 SDO (MISO)", "#1f77b4"),
    19: ("MAX31856 SDI (MOSI)", "#1f77b4"),
    29: ("MAX31856 CS", "#1f77b4"),
    2: ("Relay VCC (5V)", "#d62728"),
    14: ("Relay GND", "#555555"),
    11: ("Relay IN1  (gas solenoid)", "#2ca02c"),
    13: ("Relay IN2  (optional watchdog cutoff)", "#8c564b"),
}

fig, ax = plt.subplots(figsize=(15, 11))
ax.set_xlim(0, 15)
ax.set_ylim(0, 22)
ax.axis("off")

ax.text(7.5, 21.2, "Raspberry Pi 5  \u2014  Kiln Controller Wiring (40-pin header)",
        ha="center", fontsize=17, fontweight="bold")
ax.text(7.5, 20.5, "Pin 1 is top-left (nearest the SD card / USB-C edge). "
        "BCM numbers match config.yaml.", ha="center", fontsize=10, color="#444")

top_y = 19.5
row_h = 0.9
header_cx = 7.5  # center; left col left of this, right col right

def pin_pos(pin):
    row = (pin - 1) // 2
    y = top_y - row * row_h
    if pin % 2 == 1:  # left column (odd)
        x = header_cx - 0.55
    else:             # right column (even)
        x = header_cx + 0.55
    return x, y

# draw header background
ax.add_patch(FancyBboxPatch((header_cx - 1.15, top_y - 19 * row_h - 0.45),
                            2.3, 19 * row_h + 0.9,
                            boxstyle="round,pad=0.05", fc="#1b1b1b", ec="#000"))

for pin, (label, cat) in PINS.items():
    x, y = pin_pos(pin)
    color = USED[pin][1] if pin in USED else COLORS[cat]
    ax.plot(x, y, "s", ms=15, color=color, mec="#000", mew=0.6, zorder=3)
    ax.text(x, y, str(pin), ha="center", va="center", fontsize=6.5,
            color="white", fontweight="bold", zorder=4)
    # pin function label placed OUTSIDE the dark header box
    if pin % 2 == 1:
        ax.text(header_cx - 1.35, y, label, ha="right", va="center",
                fontsize=7.5, color="#111")
    else:
        ax.text(header_cx + 1.35, y, label, ha="left", va="center",
                fontsize=7.5, color="#111")

# callout boxes: MAX31856 on the left, relay on the right
def callout(x, y, title, lines, color):
    ax.add_patch(FancyBboxPatch((x, y - len(lines) * 0.42 - 0.5), 4.6,
                                len(lines) * 0.42 + 0.9,
                                boxstyle="round,pad=0.1", fc="white",
                                ec=color, lw=2))
    ax.text(x + 0.2, y, title, fontsize=11, fontweight="bold", color=color)
    for i, ln in enumerate(lines):
        ax.text(x + 0.25, y - 0.5 - i * 0.42, ln, fontsize=9, color="#111")

callout(0.2, 14.0, "MAX31856  \u2192  Pi (SPI)", [
    "VIN         \u2192 pin 1  (3V3)",
    "GND         \u2192 pin 6  (GND)",
    "SCK         \u2192 pin 23 (GPIO11 SCLK)",
    "SDO (MISO)  \u2192 pin 21 (GPIO9)",
    "SDI (MOSI)  \u2192 pin 19 (GPIO10)",
    "CS          \u2192 pin 29 (GPIO5)",
    "TC+ / TC-   \u2192 K-type thermocouple",
], "#1f77b4")

callout(10.2, 14.0, "SainSmart Relay  \u2192  Pi", [
    "VCC   \u2192 pin 2  (5V)",
    "GND   \u2192 pin 14 (GND)",
    "IN1   \u2192 pin 11 (GPIO17)",
    "IN2   \u2192 pin 13 (GPIO27)  [optional]",
    "",
    "COM/NO switch 12V to solenoid",
    "(separate 12V supply, fused)",
], "#2ca02c")

# phase labels
ax.text(2.5, 9.0, "PHASE 1: wire & test this first\n(no gas, no 12V)",
        ha="center", fontsize=10, color="#1f77b4", fontweight="bold")
ax.text(12.5, 9.0, "PHASE 2: add after phase 1 works\n(solenoid still off gas)",
        ha="center", fontsize=10, color="#2ca02c", fontweight="bold")

# legend
lx = 0.4
for i, (cat, name) in enumerate([("3v3", "3.3V"), ("5v", "5V"), ("gnd", "GND"),
                                 ("spi", "SPI/CS"), ("io", "GPIO")]):
    ax.plot(lx + i * 1.6, 1.0, "s", ms=13, color=COLORS[cat], mec="#000")
    ax.text(lx + i * 1.6 + 0.2, 1.0, name, va="center", fontsize=9)

ax.text(7.5, 0.2, "Always wire so loss of power = gas OFF. Read SAFETY.md before connecting gas.",
        ha="center", fontsize=9, color="#b00", fontweight="bold")

fig.savefig("docs/wiring_diagram.png", dpi=130, bbox_inches="tight")
print("wrote docs/wiring_diagram.png")
