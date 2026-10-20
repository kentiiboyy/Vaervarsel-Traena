#!/usr/bin/env python3
"""Henter vær, vannstand, bølger og nordlysvarsel for Træna og skriver data.json.

Kilder (åpne data, CC BY 4.0 / offentlig):
  - Kartverket: vannstand (varsel med vær, tidevann, målt)
  - MET Norway: værvarsel (locationforecast) og bølger (oceanforecast)
  - NOAA SWPC: Kp-indeks (nordlysaktivitet)

Kjøres av GitHub Actions hver time. Bruker bare Pythons standardbibliotek.
Kontaktinfo til MET settes i miljøvariabelen CONTACT (f.eks. lenken til repoet).
"""
import json
import os
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

OSLO = ZoneInfo("Europe/Oslo")
LAT, LON = 66.50, 12.10          # Træna
WAVE_LAT, WAVE_LON = 66.48, 11.95  # åpent hav like vest for Træna
OUT = os.environ.get("OUT", "site/data.json")
CONTACT = os.environ.get("CONTACT", "https://github.com")
UA = f"vaervarsel-traena/1.0 {CONTACT}"
MOCK_DIR = os.environ.get("MOCK_DIR")  # brukes bare til testing

LEVELS = {"HAT": 303.8, "MHW": 232.9, "MSL": 154.3, "Y1": 328.1, "Y5": 345.4,
          "Y10": 353.1, "Y20": 360.0, "Y100": 374.3, "Y200": 380.0}


def get(url, mock_name):
    if MOCK_DIR:
        with open(os.path.join(MOCK_DIR, mock_name), "rb") as f:
            return f.read()
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Klarte ikke å hente {url}: {last}")


def z(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def parse_time(s):
    s = s.strip().replace(" ", "T")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ---------- Kartverket ----------
def fetch_water(now):
    start = now.astimezone(OSLO).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=4)
    f = "%Y-%m-%dT%H:%M"
    url = ("https://vannstand.kartverket.no/tideapi.php?tide_request=locationdata&lang=nb"
           f"&lat={LAT:.2f}&lon={LON:.2f}&refcode=cd&datatype=all&interval=60&dst=1&tzone=1"
           f"&fromtime={start.strftime(f)}&totime={end.strftime(f)}")
    root = ET.fromstring(get(url, "kartverket.xml"))
    series = {}
    for data in root.iter("data"):
        typ = data.get("type")
        vals = {}
        for wl in data:
            if wl.get("value") is None or wl.get("time") is None:
                continue
            vals[parse_time(wl.get("time"))] = float(wl.get("value"))
        if typ:
            series[typ] = vals
    fc, pre, obs = series.get("forecast", {}), series.get("prediction", {}), series.get("observation", {})
    if not fc or not pre:
        raise RuntimeError("Kartverket-svaret manglet forecast eller prediction")
    water = []
    for t in sorted(set(fc) | set(pre)):
        if t not in fc or t not in pre:
            continue
        r = {"t": z(t), "fc": fc[t], "pre": pre[t]}
        if t in obs:
            r["obs"] = obs[t]
        water.append(r)
    return water


# ---------- MET bølger ----------
def fetch_waves(now):
    url = f"https://api.met.no/weatherapi/oceanforecast/2.0/complete?lat={WAVE_LAT}&lon={WAVE_LON}"
    js = json.loads(get(url, "ocean.json"))
    out = []
    for step in js["properties"]["timeseries"]:
        t = parse_time(step["time"])
        det = step["data"]["instant"]["details"]
        if "sea_surface_wave_height" not in det:
            continue
        if t < now - timedelta(hours=3) or t > now + timedelta(hours=92):
            continue
        out.append({"t": z(t), "hs": det["sea_surface_wave_height"],
                    "dir": det.get("sea_surface_wave_from_direction", 0.0)})
    return out


# ---------- MET vær ----------
def fetch_weather(now):
    url = f"https://api.met.no/weatherapi/locationforecast/2.0/complete?lat={LAT:.2f}&lon={LON:.2f}"
    js = json.loads(get(url, "locationforecast.json"))
    ts = js["properties"]["timeseries"]
    times = [parse_time(s["time"]) for s in ts]
    hourly, six = [], []
    for i, step in enumerate(ts):
        t = times[i]
        if t < now - timedelta(hours=4):   # litt historikk så trykkendring siste 3 t kan vises
            continue
        d = step["data"]
        inst = d["instant"]["details"]
        prev_gap = (t - times[i - 1]) if i > 0 else None
        next_gap = (times[i + 1] - t) if i + 1 < len(ts) else None
        is_hourly = "next_1_hours" in d or prev_gap == timedelta(hours=1) or next_gap == timedelta(hours=1)
        r = {"t": z(t)}
        for src, key in (("wind_speed", "ws"), ("wind_speed_of_gust", "wg"), ("wind_from_direction", "wd"),
                         ("air_pressure_at_sea_level", "p"), ("air_temperature", "ta"),
                         ("cloud_area_fraction", "cl")):
            if src in inst:
                r[key] = inst[src]
        if is_hourly:
            n1 = d.get("next_1_hours")
            if n1:
                if "precipitation_amount" in n1.get("details", {}):
                    r["pr"] = n1["details"]["precipitation_amount"]
                if n1.get("summary", {}).get("symbol_code"):
                    r["sym"] = n1["summary"]["symbol_code"]
            hourly.append(r)
        else:
            n6 = d.get("next_6_hours")
            if not n6:
                continue
            det6 = n6.get("details", {})
            r.pop("wg", None)
            if "precipitation_amount" in det6:
                r["pr"] = det6["precipitation_amount"]
            if "air_temperature_max" in det6:
                r["tmax"] = det6["air_temperature_max"]
            if "air_temperature_min" in det6:
                r["tmin"] = det6["air_temperature_min"]
            if n6.get("summary", {}).get("symbol_code"):
                r["sym"] = n6["summary"]["symbol_code"]
            six.append(r)
    return hourly, six


# ---------- NOAA Kp ----------
def fetch_kp(now):
    url = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
    js = json.loads(get(url, "kp.json"))
    rows = []
    if js and isinstance(js[0], list):          # gammelt format: første rad er overskrifter
        head = js[0]
        for row in js[1:]:
            rows.append(dict(zip(head, row)))
    else:
        rows = js
    out = []
    for r in rows:
        t = parse_time(str(r.get("time_tag")))
        if t < now - timedelta(days=1, hours=3):
            continue
        try:
            kp = float(r.get("kp"))
        except (TypeError, ValueError):
            continue
        out.append({"t": z(t), "kp": kp, "k": str(r.get("observed") or "predicted")})
    return out


def main():
    now = datetime.now(timezone.utc)
    if os.environ.get("NOW"):
        now = parse_time(os.environ["NOW"])
    errors = []
    old = {}
    try:
        with open(OUT, encoding="utf-8") as f:
            old = json.load(f)
    except Exception:  # noqa: BLE001
        pass

    def attempt(name, fn, fallback):
        try:
            return fn(now)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
            return fallback

    water = attempt("vannstand", fetch_water, old.get("water"))
    waves = attempt("bølger", fetch_waves, old.get("waves"))
    wx = attempt("vær", fetch_weather, (old.get("weather"), old.get("weather6")))
    kp = attempt("nordlys", fetch_kp, old.get("kp"))
    if not water:
        print("Ingen vannstandsdata, avbryter.", errors, file=sys.stderr)
        sys.exit(1)
    weather, weather6 = wx

    doc = {"updated": z(now), "station": "Træna (TAZ)", "levels": LEVELS,
           "water": water, "waves": waves or [], "weather": weather or [], "weather6": weather6 or [],
           "kp": kp or []}
    if errors:
        doc["errors"] = errors

    def fut(arr):
        f = [r for r in arr if parse_time(r["t"]) >= now - timedelta(hours=1)]
        return f or arr
    s = {}
    fw = fut(water)
    m = max(fw, key=lambda r: r["fc"]); s.update(maxWater=m["fc"], maxWaterAt=m["t"])
    if waves:
        m = max(fut(waves), key=lambda r: r["hs"]); s.update(maxWave=m["hs"], maxWaveAt=m["t"])
    if weather:
        fa = fut(weather)
        m = max(fa, key=lambda r: r.get("ws", 0)); s.update(maxWind=m.get("ws"), maxWindAt=m["t"])
        g = [r for r in fa if "wg" in r]
        if g:
            m = max(g, key=lambda r: r["wg"]); s.update(maxGust=m["wg"], maxGustAt=m["t"])
    doc["summary"] = s

    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, OUT)
    print(f"Skrev {OUT}: {len(water)} vannstand, {len(doc['waves'])} bølger, "
          f"{len(doc['weather'])}+{len(doc['weather6'])} vær, {len(doc['kp'])} Kp. {s}")
    if errors:
        print("Feil (gamle data beholdt der det gikk):", *errors, sep="\n  ", file=sys.stderr)


if __name__ == "__main__":
    main()
