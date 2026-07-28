"""Unit system and physical constants.

We work in **astronomical units** internally (FR design decision, §9 of REQUIREMENTS):

    length : AU            (astronomical unit)
    mass   : Msun          (solar mass)
    time   : day           (24 h)

This keeps the dynamic range of the numbers small and well-conditioned compared to
raw SI (where mass ~1e30 and distance ~1e11), which is exactly the precision risk R2
called out in the requirements. Double precision (numpy float64) throughout.

In these units the gravitational constant is the square of the *Gaussian gravitational
constant* k = 0.01720209895, a defining astronomical constant:

    G = k^2 = 2.959122082855911e-04   [AU^3 / (Msun * day^2)]

A handy sanity check: a body in a circular 1 AU orbit around a 1 Msun star has speed
sqrt(G) ~= 0.0172 AU/day and a period of 2*pi/sqrt(G) ~= 365.25 days. Earth checks out.
"""

# Gaussian gravitational constant (defining IAU value).
GAUSS_K = 0.01720209895

# Gravitational constant in AU^3 / (Msun * day^2).
G_AU_MSUN_DAY = GAUSS_K ** 2  # 2.959122082855911e-04

# --- Conversion helpers (SI -> internal units) ------------------------------
KM_PER_AU = 1.495978707e8
S_PER_DAY = 86400.0
DAYS_PER_YEAR = 365.25

AU_PER_KM = 1.0 / KM_PER_AU          # kilometres  -> AU
MSUN_PER_KG = 1.0 / 1.98892e30       # kilograms   -> Msun
DAY_PER_S = 1.0 / S_PER_DAY          # seconds     -> day

# Earth's mass in Msun — handy for displaying body masses in Earth units.
EARTH_MASS_MSUN = 3.003e-6

# Speed conversion: AU/day -> km/s.
KMS_PER_AU_DAY = KM_PER_AU / S_PER_DAY
