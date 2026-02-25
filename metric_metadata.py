"""metric_metadata.py -- Metadata for all Prometheus metrics produced by push_metrics.py.

Each entry is keyed by the RAW name as it appears in the source file (e.g. "cpahpa",
"ch1_t", "flowmeter").  This lets push_metrics.py go directly from the file value to
a fully-qualified Prometheus metric name without a separate lookup table.

Each value dict contains:
  metric_name  : Fully-qualified Prometheus metric name (with unit suffix).
  description  : Human-readable label with raw key in parens.
  display_name : Short friendly name for Grafana.
  unit_suffix  : The suffix embedded in metric_name (empty string if none).
  grafana_unit : Grafana unit identifier string for auto-detection.
  group        : Logical grouping (used as Prometheus subsystem label).
  subgroup     : Physical/logical location for fridge channels (50K flange/4K flange/Still/MXC/FSE).
"""

METRIC_METADATA: dict[str, dict] = {
    # ------------------------------------------------------------------
    # Status file -- compressor pressures
    # ------------------------------------------------------------------
    "cpahp": {
        "metric_name": "cpahp_mbar",
        "description": "Compressor high pressure (cpahp)",
        "unit_suffix": "_mbar",
        "grafana_unit": "pressurembar",
        "group": "compressor",
    },
    "cpahpa": {
        "metric_name": "cpahpa_mbar",
        "description": "Compressor high pressure actual (cpahpa)",
        "unit_suffix": "_mbar",
        "grafana_unit": "pressurembar",
        "group": "compressor",
    },
    "cpalp": {
        "metric_name": "cpalp_mbar",
        "description": "Compressor low pressure (cpalp)",
        "unit_suffix": "_mbar",
        "grafana_unit": "pressurembar",
        "group": "compressor",
    },
    "cpalpa": {
        "metric_name": "cpalpa_mbar",
        "description": "Compressor low pressure actual (cpalpa)",
        "unit_suffix": "_mbar",
        "grafana_unit": "pressurembar",
        "group": "compressor",
    },
    "cpadp": {
        "metric_name": "cpadp_mbar",
        "description": "Compressor differential pressure (cpadp)",
        "unit_suffix": "_mbar",
        "grafana_unit": "pressurembar",
        "group": "compressor",
    },
    # ------------------------------------------------------------------
    # Status file -- compressor temperatures
    # ------------------------------------------------------------------
    "cpatempwi": {
        "metric_name": "cpatempwi_celsius",
        "description": "Compressor water inlet temperature (cpatempwi)",
        "unit_suffix": "_celsius",
        "grafana_unit": "celsius",
        "group": "compressor",
    },
    "cpatempwo": {
        "metric_name": "cpatempwo_celsius",
        "description": "Compressor water outlet temperature (cpatempwo)",
        "unit_suffix": "_celsius",
        "grafana_unit": "celsius",
        "group": "compressor",
    },
    "cpatempo": {
        "metric_name": "cpatempo_celsius",
        "description": "Compressor output temperature (cpatempo)",
        "unit_suffix": "_celsius",
        "grafana_unit": "celsius",
        "group": "compressor",
    },
    "cpatemph": {
        "metric_name": "cpatemph_celsius",
        "description": "Compressor helium temperature (cpatemph)",
        "unit_suffix": "_celsius",
        "grafana_unit": "celsius",
        "group": "compressor",
    },
    # ------------------------------------------------------------------
    # Status file -- compressor electrical / runtime
    # ------------------------------------------------------------------
    "cpacurrent": {
        "metric_name": "cpacurrent_amperes",
        "description": "Compressor motor current (cpacurrent)",
        "unit_suffix": "_amperes",
        "grafana_unit": "amp",
        "group": "compressor",
    },
    "cpahours": {
        "metric_name": "cpahours_hours",
        "description": "Compressor total operating hours (cpahours)",
        "unit_suffix": "_hours",
        "grafana_unit": "h",
        "group": "compressor",
    },
    # ------------------------------------------------------------------
    # Status file -- turbo pump (TC400)
    # ------------------------------------------------------------------
    "tc400actualspd": {
        "metric_name": "tc400actualspd_hz",
        "description": "Turbo pump actual speed (tc400actualspd)",
        "unit_suffix": "_hz",
        "grafana_unit": "hertz",
        "group": "turbo_pump",
    },
    "tc400drvpower": {
        "metric_name": "tc400drvpower_watts",
        "description": "Turbo pump drive power (tc400drvpower)",
        "unit_suffix": "_watts",
        "grafana_unit": "watt",
        "group": "turbo_pump",
    },
    # ------------------------------------------------------------------
    # Status file -- scroll pump (nXDS)
    # ------------------------------------------------------------------
    "nxdspt": {
        "metric_name": "nxdspt",
        "description": "Scroll pump tip temperature raw sensor value (nxdspt)",
        "unit_suffix": "",
        "grafana_unit": "short",
        "group": "scroll_pump",
    },
    "nxdsct": {
        "metric_name": "nxdsct",
        "description": "Scroll pump controller temperature raw sensor value (nxdsct)",
        "unit_suffix": "",
        "grafana_unit": "short",
        "group": "scroll_pump",
    },
    "nxdsf": {
        "metric_name": "nxdsf_hz",
        "description": "Scroll pump frequency (nxdsf)",
        "unit_suffix": "_hz",
        "grafana_unit": "hertz",
        "group": "scroll_pump",
    },
    "nxdstrs": {
        "metric_name": "nxdstrs_seconds",
        "description": "Scroll pump running time (nxdstrs)",
        "unit_suffix": "_seconds",
        "grafana_unit": "s",
        "group": "scroll_pump",
    },
    # ------------------------------------------------------------------
    # Status file -- control pressure (PCU / probe control)
    # ------------------------------------------------------------------
    "ctrl_pres": {
        "metric_name": "ctrl_pres_mbar",
        "description": "Control pressure (ctrl_pres)",
        "unit_suffix": "_mbar",
        "grafana_unit": "pressurembar",
        "group": "probe_control",
    },
    # ------------------------------------------------------------------
    # CH1 -- 50K flange
    # ------------------------------------------------------------------
    "ch1_t": {
        "metric_name": "ch1_t_kelvin",
        "description": "50K flange temperature (ch1_t)",
        "unit_suffix": "_kelvin",
        "grafana_unit": "kelvin",
        "group": "fridge_temps",
        "subgroup": "50K flange",
    },
    "ch1_r": {
        "metric_name": "ch1_r_ohms",
        "description": "50K flange resistance (ch1_r)",
        "unit_suffix": "_ohms",
        "grafana_unit": "ohm",
        "group": "fridge_resistance",
        "subgroup": "50K flange",
    },
    # ------------------------------------------------------------------
    # CH2 -- 4K flange
    # ------------------------------------------------------------------
    "ch2_t": {
        "metric_name": "ch2_t_kelvin",
        "description": "4K flange temperature (ch2_t)",
        "unit_suffix": "_kelvin",
        "grafana_unit": "kelvin",
        "group": "fridge_temps",
        "subgroup": "4K flange",
    },
    "ch2_r": {
        "metric_name": "ch2_r_ohms",
        "description": "4K flange resistance (ch2_r)",
        "unit_suffix": "_ohms",
        "grafana_unit": "ohm",
        "group": "fridge_resistance",
        "subgroup": "4K flange",
    },
    # ------------------------------------------------------------------
    # CH5 -- Still
    # ------------------------------------------------------------------
    "ch5_t": {
        "metric_name": "ch5_t_kelvin",
        "description": "Still temperature (ch5_t)",
        "unit_suffix": "_kelvin",
        "grafana_unit": "kelvin",
        "group": "fridge_temps",
        "subgroup": "Still",
    },
    "ch5_r": {
        "metric_name": "ch5_r_ohms",
        "description": "Still resistance (ch5_r)",
        "unit_suffix": "_ohms",
        "grafana_unit": "ohm",
        "group": "fridge_resistance",
        "subgroup": "Still",
    },
    # ------------------------------------------------------------------
    # CH6 -- MXC (mixing chamber, mK-range)
    # ------------------------------------------------------------------
    "ch6_t": {
        "metric_name": "ch6_t_kelvin",
        "description": "MXC (mixing chamber) temperature (ch6_t)",
        "unit_suffix": "_kelvin",
        "grafana_unit": "kelvin",
        "group": "fridge_temps",
        "subgroup": "MXC",
    },
    "ch6_r": {
        "metric_name": "ch6_r_ohms",
        "description": "MXC (mixing chamber) resistance (ch6_r)",
        "unit_suffix": "_ohms",
        "grafana_unit": "ohm",
        "group": "fridge_resistance",
        "subgroup": "MXC",
    },
    # ------------------------------------------------------------------
    # CH9 -- FSE (fridge sample environment, mK-range)
    # ------------------------------------------------------------------
    "ch9_t": {
        "metric_name": "ch9_t_kelvin",
        "description": "FSE temperature (ch9_t)",
        "unit_suffix": "_kelvin",
        "grafana_unit": "kelvin",
        "group": "fridge_temps",
        "subgroup": "FSE",
    },
    "ch9_r": {
        "metric_name": "ch9_r_ohms",
        "description": "FSE resistance (ch9_r)",
        "unit_suffix": "_ohms",
        "grafana_unit": "ohm",
        "group": "fridge_resistance",
        "subgroup": "FSE",
    },
    # ------------------------------------------------------------------
    # Flowmeter
    # ------------------------------------------------------------------
    "flowmeter": {
        "metric_name": "flowmeter_mmol_per_s",
        "description": "Mixture flow rate (flowmeter)",
        "unit_suffix": "_mmol_per_s",
        "grafana_unit": "moles",
        "group": "flow",
    },
    # ------------------------------------------------------------------
    # Maxigauge -- 6 pressure channels
    # ------------------------------------------------------------------
    "maxigauge_ch1": {
        "metric_name": "maxigauge_ch1_pressure_mbar",
        "description": "Maxigauge CH1 pressure (maxigauge_ch1)",
        "unit_suffix": "_pressure_mbar",
        "grafana_unit": "pressurembar",
        "group": "maxigauge",
    },
    "maxigauge_ch2": {
        "metric_name": "maxigauge_ch2_pressure_mbar",
        "description": "Maxigauge CH2 pressure (maxigauge_ch2)",
        "unit_suffix": "_pressure_mbar",
        "grafana_unit": "pressurembar",
        "group": "maxigauge",
    },
    "maxigauge_ch3": {
        "metric_name": "maxigauge_ch3_pressure_mbar",
        "description": "Maxigauge CH3 pressure (maxigauge_ch3)",
        "unit_suffix": "_pressure_mbar",
        "grafana_unit": "pressurembar",
        "group": "maxigauge",
    },
    "maxigauge_ch4": {
        "metric_name": "maxigauge_ch4_pressure_mbar",
        "description": "Maxigauge CH4 pressure (maxigauge_ch4)",
        "unit_suffix": "_pressure_mbar",
        "grafana_unit": "pressurembar",
        "group": "maxigauge",
    },
    "maxigauge_ch5": {
        "metric_name": "maxigauge_ch5_pressure_mbar",
        "description": "Maxigauge CH5 pressure (maxigauge_ch5)",
        "unit_suffix": "_pressure_mbar",
        "grafana_unit": "pressurembar",
        "group": "maxigauge",
    },
    "maxigauge_ch6": {
        "metric_name": "maxigauge_ch6_pressure_mbar",
        "description": "Maxigauge CH6 pressure (maxigauge_ch6)",
        "unit_suffix": "_pressure_mbar",
        "grafana_unit": "pressurembar",
        "group": "maxigauge",
    },
}

# Reverse lookup: fully-qualified output metric name -> metadata entry.
# Built automatically so get_description/get_group work whether they are
# given a raw key or an output metric name.
_BY_METRIC_NAME: dict[str, dict] = {
    entry["metric_name"]: entry
    for entry in METRIC_METADATA.values()
}


def _lookup(key: str) -> dict | None:
    """Return the metadata entry for either a raw key or an output metric name."""
    return METRIC_METADATA.get(key) or _BY_METRIC_NAME.get(key)


def get_metric_name_for_raw_key(raw_key: str) -> str:
    """Return the fully-qualified Prometheus metric name for a raw data key.

    For known keys (e.g. 'cpahpa' -> 'cpahpa_mbar', 'ch1_t' -> 'ch1_t_kelvin')
    the mapping comes directly from the metadata dict.  Unknown keys are returned
    unchanged so they are still pushed (with a TODO description).
    """
    meta = METRIC_METADATA.get(raw_key)
    if meta:
        return meta["metric_name"]
    return raw_key


def get_description(key: str) -> str:
    """Return the human-readable description for a raw key or output metric name.

    Unknown keys get a TODO-prefixed fallback so they are easy to spot in
    Pushgateway and Grafana.
    """
    meta = _lookup(key)
    if meta:
        return meta["description"]
    return f"TODO: unknown metric [unknown source] ({key})"


def get_unit_suffix(key: str) -> str:
    """Return the unit suffix for a raw key or output metric name (may be empty)."""
    meta = _lookup(key)
    if meta:
        return meta["unit_suffix"]
    return ""


def get_group(key: str) -> str:
    """Return the logical group for a raw key or output metric name."""
    meta = _lookup(key)
    if meta:
        return meta["group"]
    return "unknown"


def get_subgroup(key: str) -> str:
    """Return the physical/logical location subgroup for a raw key or output metric name.
    
    For fridge channels, returns values like "50K flange", "4K flange", "Still", "MXC", "FSE".
    For other metrics, returns empty string.
    """
    meta = _lookup(key)
    if meta:
        return meta.get("subgroup", "")
    return ""


def get_display_name(key: str) -> str:
    """Return a short display name for use in Grafana visualizations.
    
    Extracts the friendly part of the description without the file source
    and raw key info. For example:
      "Still temperature (ch5_t)" 
    """
    description = get_description(key)
    return description

