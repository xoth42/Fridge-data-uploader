"""metric_metadata.py -- Metadata for all Prometheus metrics produced by push_metrics.py.

Each entry maps a fully-qualified metric name (with unit suffix already embedded) to:
  description  : Human-readable label with source file in brackets and raw key in parens.
  unit_suffix  : The suffix already embedded in the metric name key.
  grafana_unit : Grafana unit identifier string for auto-detection.
  group        : Logical grouping (used as Prometheus subsystem label).
"""

METRIC_METADATA: dict[str, dict] = {
    # ------------------------------------------------------------------
    # Status file -- compressor pressures
    # ------------------------------------------------------------------
    "cpahp_mbar": {
        "description": "Compressor high pressure [Status file] (cpahp_mbar)",
        "unit_suffix": "_mbar",
        "grafana_unit": "pressurembar",
        "group": "compressor",
    },
    "cpahpa_mbar": {
        "description": "Compressor high pressure actual [Status file] (cpahpa_mbar)",
        "unit_suffix": "_mbar",
        "grafana_unit": "pressurembar",
        "group": "compressor",
    },
    "cpalp_mbar": {
        "description": "Compressor low pressure [Status file] (cpalp_mbar)",
        "unit_suffix": "_mbar",
        "grafana_unit": "pressurembar",
        "group": "compressor",
    },
    "cpalpa_mbar": {
        "description": "Compressor low pressure actual [Status file] (cpalpa_mbar)",
        "unit_suffix": "_mbar",
        "grafana_unit": "pressurembar",
        "group": "compressor",
    },
    "cpadp_mbar": {
        "description": "Compressor differential pressure [Status file] (cpadp_mbar)",
        "unit_suffix": "_mbar",
        "grafana_unit": "pressurembar",
        "group": "compressor",
    },
    # ------------------------------------------------------------------
    # Status file -- compressor temperatures
    # ------------------------------------------------------------------
    "cpatempwi_celsius": {
        "description": "Compressor water inlet temperature [Status file] (cpatempwi_celsius)",
        "unit_suffix": "_celsius",
        "grafana_unit": "celsius",
        "group": "compressor",
    },
    "cpatempwo_celsius": {
        "description": "Compressor water outlet temperature [Status file] (cpatempwo_celsius)",
        "unit_suffix": "_celsius",
        "grafana_unit": "celsius",
        "group": "compressor",
    },
    "cpatempo_celsius": {
        "description": "Compressor output temperature [Status file] (cpatempo_celsius)",
        "unit_suffix": "_celsius",
        "grafana_unit": "celsius",
        "group": "compressor",
    },
    "cpatemph_celsius": {
        "description": "Compressor helium temperature [Status file] (cpatemph_celsius)",
        "unit_suffix": "_celsius",
        "grafana_unit": "celsius",
        "group": "compressor",
    },
    # ------------------------------------------------------------------
    # Status file -- compressor electrical / runtime
    # ------------------------------------------------------------------
    "cpacurrent_amperes": {
        "description": "Compressor motor current [Status file] (cpacurrent_amperes)",
        "unit_suffix": "_amperes",
        "grafana_unit": "amp",
        "group": "compressor",
    },
    "cpahours_hours": {
        "description": "Compressor total operating hours [Status file] (cpahours_hours)",
        "unit_suffix": "_hours",
        "grafana_unit": "h",
        "group": "compressor",
    },
    # ------------------------------------------------------------------
    # Status file -- turbo pump (TC400)
    # ------------------------------------------------------------------
    "tc400actualspd_hz": {
        "description": "Turbo pump actual speed [Status file] (tc400actualspd_hz)",
        "unit_suffix": "_hz",
        "grafana_unit": "hertz",
        "group": "turbo_pump",
    },
    "tc400drvpower_watts": {
        "description": "Turbo pump drive power [Status file] (tc400drvpower_watts)",
        "unit_suffix": "_watts",
        "grafana_unit": "watt",
        "group": "turbo_pump",
    },
    # ------------------------------------------------------------------
    # Status file -- scroll pump (nXDS)
    # ------------------------------------------------------------------
    "nxdspt": {
        "description": "Scroll pump tip temperature raw sensor value [Status file] (nxdspt)",
        "unit_suffix": "",
        "grafana_unit": "short",
        "group": "scroll_pump",
    },
    "nxdsct": {
        "description": "Scroll pump controller temperature raw sensor value [Status file] (nxdsct)",
        "unit_suffix": "",
        "grafana_unit": "short",
        "group": "scroll_pump",
    },
    "nxdsf_hz": {
        "description": "Scroll pump frequency [Status file] (nxdsf_hz)",
        "unit_suffix": "_hz",
        "grafana_unit": "hertz",
        "group": "scroll_pump",
    },
    "nxdstrs_seconds": {
        "description": "Scroll pump running time [Status file] (nxdstrs_seconds)",
        "unit_suffix": "_seconds",
        "grafana_unit": "s",
        "group": "scroll_pump",
    },
    # ------------------------------------------------------------------
    # Status file -- control pressure (PCU / probe control)
    # ------------------------------------------------------------------
    "ctrl_pres_mbar": {
        "description": "Control pressure [Status file] (ctrl_pres_mbar)",
        "unit_suffix": "_mbar",
        "grafana_unit": "pressurembar",
        "group": "probe_control",
    },
    # ------------------------------------------------------------------
    # CH1 -- 50K flange
    # ------------------------------------------------------------------
    "ch1_t_kelvin": {
        "description": "50K flange temperature [CH1 T file] (ch1_t_kelvin)",
        "unit_suffix": "_kelvin",
        "grafana_unit": "kelvin",
        "group": "fridge_temps",
    },
    "ch1_r_ohms": {
        "description": "50K flange resistance [CH1 R file] (ch1_r_ohms)",
        "unit_suffix": "_ohms",
        "grafana_unit": "ohm",
        "group": "fridge_resistance",
    },
    # ------------------------------------------------------------------
    # CH2 -- 4K flange
    # ------------------------------------------------------------------
    "ch2_t_kelvin": {
        "description": "4K flange temperature [CH2 T file] (ch2_t_kelvin)",
        "unit_suffix": "_kelvin",
        "grafana_unit": "kelvin",
        "group": "fridge_temps",
    },
    "ch2_r_ohms": {
        "description": "4K flange resistance [CH2 R file] (ch2_r_ohms)",
        "unit_suffix": "_ohms",
        "grafana_unit": "ohm",
        "group": "fridge_resistance",
    },
    # ------------------------------------------------------------------
    # CH5 -- Still
    # ------------------------------------------------------------------
    "ch5_t_kelvin": {
        "description": "Still temperature [CH5 T file] (ch5_t_kelvin)",
        "unit_suffix": "_kelvin",
        "grafana_unit": "kelvin",
        "group": "fridge_temps",
    },
    "ch5_r_ohms": {
        "description": "Still resistance [CH5 R file] (ch5_r_ohms)",
        "unit_suffix": "_ohms",
        "grafana_unit": "ohm",
        "group": "fridge_resistance",
    },
    # ------------------------------------------------------------------
    # CH6 -- MXC (mixing chamber, mK-range)
    # ------------------------------------------------------------------
    "ch6_t_kelvin": {
        "description": (
            "MXC (mixing chamber) temperature, mK-range raw value in K"
            " [CH6 T file] (ch6_t_kelvin)"
        ),
        "unit_suffix": "_kelvin",
        "grafana_unit": "kelvin",
        "group": "fridge_temps",
    },
    "ch6_r_ohms": {
        "description": "MXC (mixing chamber) resistance [CH6 R file] (ch6_r_ohms)",
        "unit_suffix": "_ohms",
        "grafana_unit": "ohm",
        "group": "fridge_resistance",
    },
    # ------------------------------------------------------------------
    # CH9 -- FSE (fridge sample environment, mK-range)
    # ------------------------------------------------------------------
    "ch9_t_kelvin": {
        "description": (
            "FSE (fridge sample environment) temperature, mK-range raw value in K"
            " [CH9 T file] (ch9_t_kelvin)"
        ),
        "unit_suffix": "_kelvin",
        "grafana_unit": "kelvin",
        "group": "fridge_temps",
    },
    "ch9_r_ohms": {
        "description": "FSE (fridge sample environment) resistance [CH9 R file] (ch9_r_ohms)",
        "unit_suffix": "_ohms",
        "grafana_unit": "ohm",
        "group": "fridge_resistance",
    },
    # ------------------------------------------------------------------
    # Flowmeter
    # ------------------------------------------------------------------
    "flowmeter_mmol_per_s": {
        "description": "Mixture flow rate [Flowmeter file] (flowmeter_mmol_per_s)",
        "unit_suffix": "_mmol_per_s",
        "grafana_unit": "moles",
        "group": "flow",
    },
    # ------------------------------------------------------------------
    # Maxigauge -- 6 pressure channels
    # ------------------------------------------------------------------
    "maxigauge_ch1_pressure_mbar": {
        "description": "Maxigauge CH1 pressure [maxigauge file] (maxigauge_ch1_pressure_mbar)",
        "unit_suffix": "_mbar",
        "grafana_unit": "pressurembar",
        "group": "maxigauge",
    },
    "maxigauge_ch2_pressure_mbar": {
        "description": "Maxigauge CH2 pressure [maxigauge file] (maxigauge_ch2_pressure_mbar)",
        "unit_suffix": "_mbar",
        "grafana_unit": "pressurembar",
        "group": "maxigauge",
    },
    "maxigauge_ch3_pressure_mbar": {
        "description": "Maxigauge CH3 pressure [maxigauge file] (maxigauge_ch3_pressure_mbar)",
        "unit_suffix": "_mbar",
        "grafana_unit": "pressurembar",
        "group": "maxigauge",
    },
    "maxigauge_ch4_pressure_mbar": {
        "description": "Maxigauge CH4 pressure [maxigauge file] (maxigauge_ch4_pressure_mbar)",
        "unit_suffix": "_mbar",
        "grafana_unit": "pressurembar",
        "group": "maxigauge",
    },
    "maxigauge_ch5_pressure_mbar": {
        "description": "Maxigauge CH5 pressure [maxigauge file] (maxigauge_ch5_pressure_mbar)",
        "unit_suffix": "_mbar",
        "grafana_unit": "pressurembar",
        "group": "maxigauge",
    },
    "maxigauge_ch6_pressure_mbar": {
        "description": "Maxigauge CH6 pressure [maxigauge file] (maxigauge_ch6_pressure_mbar)",
        "unit_suffix": "_mbar",
        "grafana_unit": "pressurembar",
        "group": "maxigauge",
    },
}


def get_metric_name_for_raw_key(raw_key: str) -> str:
    """Map a raw Status file key (e.g. 'cpahpa') to its metric name (e.g. 'cpahpa_mbar').

    Looks for an exact match first, then for any metadata entry whose name
    equals raw_key + '_' + suffix, and returns that full name.  Falls back to
    raw_key unchanged so unknown keys are still pushed.
    """
    if raw_key in METRIC_METADATA:
        return raw_key
    for metric_name in METRIC_METADATA:
        if metric_name.startswith(raw_key + "_"):
            return metric_name
    return raw_key


def get_description(key: str) -> str:
    """Return the human-readable description for a metric key.

    Falls back to a generic string that includes the key name and notes the
    source is unknown, so the metric can still be identified in Grafana.
    """
    meta = METRIC_METADATA.get(key)
    if meta:
        return meta["description"]
    return f"Unknown metric [unknown source] ({key})"


def get_unit_suffix(key: str) -> str:
    """Return the unit suffix embedded in a metric key (may be empty string)."""
    meta = METRIC_METADATA.get(key)
    if meta:
        return meta["unit_suffix"]
    return ""


def get_group(key: str) -> str:
    """Return the logical group for a metric key (used as Prometheus subsystem label)."""
    meta = METRIC_METADATA.get(key)
    if meta:
        return meta["group"]
    return "unknown"
