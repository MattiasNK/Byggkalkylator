"""
app.py – Interaktiv Kalkylator & 3D-Visualisering för Arbetsbänk
Kör med: streamlit run app.py
"""
from __future__ import annotations
import json
import os
import io
from pathlib import Path
from typing import Optional

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from calculations import (
    BenchGeometry,
    compute_cost,
    TIMBER_PROFILES,
    DEFAULT_TIMBER_PRICES,
    TABLETOP_CATALOG,
    TABLETOP_OPTIONS,
    TABLETOP_THICKNESS,
    calculate_tabletop_coverage,
    rank_tabletop_options,
    SCREW_COST_FLAT,
)
from optimization import run_optimization
from visualization import build_figure
from pdf_export import generate_pdf_report

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

PRESETS_DIR = Path("presets")
PRESETS_DIR.mkdir(exist_ok=True)

st.set_page_config(
    page_title="Byggkalkylator – Arbetsbänk",
    page_icon="🔨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS-tweaks
st.markdown("""
<style>
    .kpi-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px;
        padding: 16px 14px;
        text-align: center;
        border-left: 4px solid #e94560;
        margin-bottom: 8px;
        min-height: 112px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .kpi-label { color: #aaa; font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
    .kpi-value { color: #fff; font-size: 1.75rem; font-weight: 700; margin: 4px 0; white-space: nowrap; }
    .kpi-sub   { color: #88c; font-size: 0.75rem; white-space: nowrap; }
    .section-header { border-bottom: 2px solid #e94560; margin: 1.5rem 0 0.8rem; padding-bottom: 4px; }
    .info-box {
        background: rgba(74, 126, 255, 0.12);
        border-radius: 8px;
        padding: 14px;
        border: 1px solid rgba(74, 126, 255, 0.25);
        border-left: 4px solid #4a7eff;
    }
    /* Synkade sliders direkt under inmatningsrutor */
    [data-testid="stSidebar"] div[data-testid="stSlider"] {
        margin-top: -10px;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Hjälpfunktioner – preset-hantering
# ---------------------------------------------------------------------------

def _get_presets() -> list[str]:
    return sorted(p.stem for p in PRESETS_DIR.glob("*.json"))


def _save_preset(name: str, params: dict):
    path = PRESETS_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)
    st.success(f"Preset **{name}** sparad ✓")


def _load_preset(name: str) -> dict:
    path = PRESETS_DIR / f"{name}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _params_to_dict(ss) -> dict:
    return {
        "L": ss.L, "B": ss.B, "H": ss.H,
        "overhang_kortsida": getattr(ss, "overhang_kortsida", 0),
        "overhang_längssida": getattr(ss, "overhang_längssida", 0),
        "lower_rail_h": ss.lower_rail_h,
        "n_pairs": ss.n_pairs,
        "leg_profile": ss.leg_profile,
        "frame_profile": ss.frame_profile,
        "leg_price": ss.leg_price,
        "frame_price": ss.frame_price,
        "tabletop_option": getattr(ss, "selected_sheet_name", list(TABLETOP_OPTIONS.keys())[0]),
        "tabletop_price": getattr(ss, "tabletop_price", list(TABLETOP_OPTIONS.values())[0]),
        "top_mode_radio": getattr(ss, "top_mode_radio", "⭐ Automatisk optimering"),
        "top_mat_filter": getattr(ss, "top_mat_filter", "Alla"),
        "screw_cost": ss.screw_cost,
        "saw_kerf_mm": getattr(ss, "saw_kerf_mm", 5),
    }


def _apply_dict(params: dict):
    ss = st.session_state
    for k, v in params.items():
        ss[k] = v
        ss[f"{k}_slider"] = v
        ss[f"{k}_num"] = v
    # Bakåtkompatibilitet för äldre sparade presets
    if "overhang_kortsida" not in params and "overhang_L" in params:
        ss["overhang_kortsida"] = params["overhang_L"]
    if "overhang_längssida" not in params and "overhang_B" in params:
        ss["overhang_längssida"] = params["overhang_B"]


# ---------------------------------------------------------------------------
# Session state initialisering
# ---------------------------------------------------------------------------

def init_session_state():
    defaults = {
        "L": 2400,
        "B": 700,
        "H": 900,
        "overhang_kortsida": 0,
        "overhang_längssida": 0,
        "lower_rail_h": 250,
        "n_pairs": 3,
        "leg_profile": "45×95 mm",
        "frame_profile": "45×95 mm",
        "leg_price": DEFAULT_TIMBER_PRICES["45×95 mm"],
        "frame_price": DEFAULT_TIMBER_PRICES["45×95 mm"],
        "tabletop_option": list(TABLETOP_OPTIONS.keys())[0],
        "tabletop_price": list(TABLETOP_OPTIONS.values())[0],
        "top_mode_radio": "⭐ Automatisk optimering",
        "top_mat_filter": "Alla",
        "selected_sheet_name": None,
        "screw_cost": SCREW_COST_FLAT,
        "saw_kerf_mm": 5,
        "show_tabletop": True,
        "show_rails": True,
        "dark_3d": True,
        "show_edges": True,
        "show_seams": True,
        "show_legend": False,
        "show_dimensions": True,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
        if f"{k}_slider" not in st.session_state:
            st.session_state[f"{k}_slider"] = st.session_state[k]
        if f"{k}_num" not in st.session_state:
            st.session_state[f"{k}_num"] = st.session_state[k]


init_session_state()


def render_synced_dimension(
    label: str,
    key_base: str,
    min_val: int,
    max_val: int,
    step_num: int,
    step_slider: int,
    help: Optional[str] = None,
) -> int:
    """
    Rendrerar en inmatningsruta och en slider som är synkroniserade med varandra.
    Tillåter användaren att antingen dra slidern för snabba hopp, eller skriva exakta mått i rutan.
    """
    cur_val = int(st.session_state.get(key_base, min_val))
    if f"{key_base}_num" not in st.session_state:
        st.session_state[f"{key_base}_num"] = cur_val
    if f"{key_base}_slider" not in st.session_state:
        st.session_state[f"{key_base}_slider"] = cur_val

    def _on_num():
        val = int(st.session_state[f"{key_base}_num"])
        clamped = max(min_val, min(max_val, val))
        st.session_state[key_base] = clamped
        st.session_state[f"{key_base}_slider"] = clamped
        st.session_state[f"{key_base}_num"] = clamped

    def _on_slider():
        val = int(st.session_state[f"{key_base}_slider"])
        st.session_state[key_base] = val
        st.session_state[f"{key_base}_num"] = val

    st.number_input(
        label,
        min_value=min_val,
        max_value=max_val,
        step=step_num,
        key=f"{key_base}_num",
        help=help,
        on_change=_on_num,
    )
    st.slider(
        label,
        min_value=min_val,
        max_value=max_val,
        step=step_slider,
        key=f"{key_base}_slider",
        label_visibility="collapsed",
        on_change=_on_slider,
    )
    return int(st.session_state[key_base])


def render_pdf_export_widget(geo, purchase_plan, costs, chosen_top_plan, shopping_items, key_suffix=""):
    """
    Rendrerar en knapp för att generera och ladda ner en komplett PDF-rapport.
    Cachar den genererade PDF-filen så länge konfigurationen är oförändrad.
    """
    PDF_BUILD_VERSION = "v3.3_sawplan_drawings"
    config_id = f"{PDF_BUILD_VERSION}_{geo.L}_{geo.B}_{geo.H}_{geo.overhang_kortsida}_{geo.overhang_längssida}_{geo.lower_rail_h}_{geo.n_pairs}_{geo.leg_profile}_{geo.frame_profile}_{chosen_top_plan.get('name', '')}"

    has_valid_pdf = (
        st.session_state.get("cached_pdf_bytes") is not None and
        st.session_state.get("cached_pdf_config_id") == config_id
    )

    if has_valid_pdf:
        st.download_button(
            label="⬇️ Ladda ner PDF-rapport",
            data=st.session_state["cached_pdf_bytes"],
            file_name=f"Arbetsbank_Rapport_{geo.L}x{geo.B}mm.pdf",
            mime="application/pdf",
            use_container_width=True,
            key=f"dl_pdf_{key_suffix}",
        )
        if st.button("🔄 Generera om PDF", key=f"regen_pdf_{key_suffix}", use_container_width=True):
            st.session_state["cached_pdf_bytes"] = None
            st.rerun()
    else:
        if st.button("📄 Skapa PDF-rapport (med 3D-bild & sågplan)", key=f"gen_pdf_{key_suffix}", use_container_width=True):
            with st.spinner("Ritar 3D-modell och sammanställer PDF-rapport..."):
                pdf_bytes = generate_pdf_report(
                    geo=geo,
                    purchase_plan=purchase_plan,
                    costs=costs,
                    chosen_top_plan=chosen_top_plan,
                    shopping_items=shopping_items,
                )
                st.session_state["cached_pdf_bytes"] = pdf_bytes
                st.session_state["cached_pdf_config_id"] = config_id
                st.success("PDF-rapport skapad!")
                st.rerun()


def build_shopping_items(purchase_plan, geo, ss, chosen_top_plan) -> list[dict]:
    """Bygger bygghandelns samlade inköpslista."""
    items = []
    if purchase_plan.get("is_combined"):
        timber_summary = purchase_plan.get("timber_board_summary", [])
        if timber_summary:
            for b in timber_summary:
                items.append({
                    "Komponent": "Virke (Ben & Ram)",
                    "Artikel (jem & fix)": b["name"],
                    "Dimension": ss.leg_profile,
                    "Längd": f"{b['length_mm']/1000:.1f} m",
                    "Antal": f"{b['count']} st",
                    "Styckpris": b["piece_price"],
                    "Delsumma": b["total_cost"],
                })
        else:
            items.append({
                "Komponent": "Virke (Ben, Sarger & Tvärslåar)",
                "Artikel (jem & fix)": purchase_plan["timber_article_name"],
                "Dimension": ss.leg_profile,
                "Längd": f"{purchase_plan['timber_stock_length']/1000:.1f} m" if purchase_plan['timber_stock_length'] > 0 else "-",
                "Antal": f"{purchase_plan['timber_n_pieces']} st",
                "Styckpris": purchase_plan["timber_piece_price"],
                "Delsumma": purchase_plan["timber_total_cost"],
            })
    else:
        leg_summary = purchase_plan.get("leg_board_summary", [])
        if leg_summary:
            for b in leg_summary:
                items.append({
                    "Komponent": "Ben",
                    "Artikel (jem & fix)": b["name"],
                    "Dimension": ss.leg_profile,
                    "Längd": f"{b['length_mm']/1000:.1f} m",
                    "Antal": f"{b['count']} st",
                    "Styckpris": b["piece_price"],
                    "Delsumma": b["total_cost"],
                })
        elif purchase_plan["leg_n_pieces"] > 0:
            items.append({
                "Komponent": "Ben",
                "Artikel (jem & fix)": purchase_plan["leg_article_name"],
                "Dimension": ss.leg_profile,
                "Längd": f"{purchase_plan['leg_stock_length']/1000:.1f} m" if purchase_plan['leg_stock_length'] > 0 else "-",
                "Antal": f"{purchase_plan['leg_n_pieces']} st",
                "Styckpris": purchase_plan["leg_piece_price"],
                "Delsumma": purchase_plan["leg_total_cost"],
            })

        frame_summary = purchase_plan.get("frame_board_summary", [])
        if frame_summary:
            for b in frame_summary:
                items.append({
                    "Komponent": "Sarger & Tvärslåar",
                    "Artikel (jem & fix)": b["name"],
                    "Dimension": ss.frame_profile,
                    "Längd": f"{b['length_mm']/1000:.1f} m",
                    "Antal": f"{b['count']} st",
                    "Styckpris": b["piece_price"],
                    "Delsumma": b["total_cost"],
                })
        elif purchase_plan["frame_n_pieces"] > 0:
            items.append({
                "Komponent": "Sarger & Tvärslåar",
                "Artikel (jem & fix)": purchase_plan["frame_article_name"],
                "Dimension": ss.frame_profile,
                "Längd": f"{purchase_plan['frame_stock_length']/1000:.1f} m" if purchase_plan['frame_stock_length'] > 0 else "-",
                "Antal": f"{purchase_plan['frame_n_pieces']} st",
                "Styckpris": purchase_plan["frame_piece_price"],
                "Delsumma": purchase_plan["frame_total_cost"],
            })

    items.append({
        "Komponent": "Bänkskiva",
        "Artikel (jem & fix)": chosen_top_plan["name"],
        "Dimension": f"{chosen_top_plan['sheet']['length']} × {chosen_top_plan['sheet']['width']} mm ({chosen_top_plan['thickness']} mm)",
        "Längd": f"Kapas till {geo.tabletop_L} × {geo.tabletop_B} mm ({chosen_top_plan['seam_label']})",
        "Antal": f"{chosen_top_plan['sheets_needed']} st",
        "Styckpris": chosen_top_plan["piece_price"],
        "Delsumma": chosen_top_plan["total_cost"],
    })

    items.append({
        "Komponent": "Fästelement",
        "Artikel (jem & fix)": "Träskruv 5,0×80 mm + montageskruv",
        "Dimension": "Schablonpaket",
        "Längd": "-",
        "Antal": "1 paket",
        "Styckpris": ss.screw_cost,
        "Delsumma": ss.screw_cost,
    })
    return items

# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🔨 Byggkalkylator")
    st.caption("Interaktiv arbetsbänk – Konfigurator")

    # ---- Ladda preset ----
    presets = _get_presets()
    if presets:
        with st.expander("📂 Ladda preset", expanded=False):
            chosen_preset = st.selectbox("Sparade presets", presets, key="preset_select_load")
            if st.button("Ladda vald preset", use_container_width=True):
                _apply_dict(_load_preset(chosen_preset))
                st.rerun()

    st.divider()

    # ---- A. Geometri ----
    st.subheader("📐 A. Geometri & Mått")

    L = render_synced_dimension(
        "Ramens längd (mm)",
        "L",
        1000, 6000,
        step_num=50, step_slider=50,
        help="Underredets / ramens totala längd. Dra i slidern för snabb grovjustering eller skriv in exakt mått i rutan."
    )
    B = render_synced_dimension(
        "Ramens djup (mm)",
        "B",
        500, 1500,
        step_num=50, step_slider=50,
        help="Underredets / ramens totala djup. Dra i slidern eller skriv in exakt mått."
    )
    H = render_synced_dimension(
        "Total arbetshöjd inkl. skiva (mm)",
        "H",
        700, 1200,
        step_num=10, step_slider=10,
        help="Total arbetshöjd från golv till ovansida bänkskiva."
    )

    col_a, col_b = st.columns(2)
    with col_a:
        overhang_kortsida = st.number_input(
            "Överhäng kortsidor (gavlar) (mm)",
            0, 300, step=5, key="overhang_kortsida",
            help="Hur mycket skivan sticker ut utanför gavlarna till vänster och höger (i längsled X)."
        )
    with col_b:
        overhang_längssida = st.number_input(
            "Överhäng längssidor (fram/bak) (mm)",
            0, 300, step=5, key="overhang_längssida",
            help="Hur mycket skivan sticker ut framför och bakom sargerna (i djupled Y)."
        )

    # Faktiska yttermått för bänkskivan
    top_L = L + 2 * overhang_kortsida
    top_B = B + 2 * overhang_längssida

    if overhang_kortsida > 0 or overhang_längssida > 0:
        st.info(f"📏 **Bänkskivans mått:** **{top_L} × {top_B} mm**\n\n*(Ramens mått: {L} × {B} mm)*")

    lower_rail_h = render_synced_dimension(
        "Nedre sarg – UK från golv (mm)",
        "lower_rail_h",
        50, 500,
        step_num=10, step_slider=10,
        help="Höjd från golv till underkant av den nedre sargen."
    )

    st.divider()

    # ---- B. Konstruktion ----
    st.subheader("🏗️ B. Konstruktion")

    n_pairs = st.selectbox("Antal benpar", [2, 3, 4, 5, 6], index=1, key="n_pairs")

    # Info om tvärslåar
    n_cross = 2 * n_pairs
    st.info(f"ℹ️ {2*n_pairs} ben · 4 sarger · {n_cross} tvärslåar")

    st.divider()

    # ---- C. Material & Priser ----
    st.subheader("🪵 C. Material & Priser")
    st.caption("Aktuellt virkesutbud och priser från jem & fix")

    def on_leg_profile_change():
        st.session_state.leg_price = float(DEFAULT_TIMBER_PRICES.get(st.session_state.leg_profile, 30.75))

    def on_frame_profile_change():
        st.session_state.frame_price = float(DEFAULT_TIMBER_PRICES.get(st.session_state.frame_profile, 30.75))

    leg_profile = st.selectbox(
        "Benprofil",
        list(TIMBER_PROFILES.keys()),
        index=2,
        key="leg_profile",
        on_change=on_leg_profile_change
    )
    leg_price = st.number_input(
        f"Pris {leg_profile} (kr/lpm)", min_value=1.0, step=0.5,
        value=float(DEFAULT_TIMBER_PRICES.get(leg_profile, 30.75)), key="leg_price"
    )

    frame_profile = st.selectbox(
        "Sarg/Tvärslå-profil",
        list(TIMBER_PROFILES.keys()),
        index=2,
        key="frame_profile",
        on_change=on_frame_profile_change
    )
    frame_price = st.number_input(
        f"Pris {frame_profile} (kr/lpm)", min_value=1.0, step=0.5,
        value=float(DEFAULT_TIMBER_PRICES.get(frame_profile, 30.75)), key="frame_price"
    )

    st.markdown("**Bänkskiva**")
    top_mode = st.radio(
        "Urvalsmetod för bänkskiva",
        ["⭐ Automatisk optimering", "🎯 Välj specifik skiva"],
        key="top_mode_radio",
        help="Automatisk optimering prioriterar 0 skarvar (hel skiva) i första hand och därefter lägst inköpspris."
    )

    top_mat_filter = st.selectbox(
        "Filtrera material",
        ["Alla", "Plywood", "MDF", "OSB"],
        key="top_mat_filter"
    )

    # Rangordna skivor utifrån bänkskivans FAKTISKA mått top_L och top_B
    ranked_top_sheets = rank_tabletop_options(top_L, top_B, material_filter=top_mat_filter)

    if top_mode == "⭐ Automatisk optimering":
        chosen_top_plan = ranked_top_sheets[0]
        st.session_state["selected_sheet_name"] = chosen_top_plan["name"]
    else:
        sheet_options = [s["name"] for s in ranked_top_sheets]
        prev_sel = st.session_state.get("selected_sheet_name")
        default_idx = sheet_options.index(prev_sel) if prev_sel in sheet_options else 0

        def _format_sheet(sheet_name):
            matching = next((s for s in ranked_top_sheets if s["name"] == sheet_name), None)
            if not matching:
                return sheet_name
            seam_txt = "0 skarvar" if matching["seams"] == 0 else f"{matching['seams']} skarv(ar)"
            return f"{matching['name']} ({matching['thickness']} mm) — {seam_txt}, {matching['total_cost']:.0f} kr"

        selected_sheet_name = st.selectbox(
            "Välj skiva ur jem & fix sortiment (≥ 8 mm)",
            sheet_options,
            index=default_idx,
            format_func=_format_sheet,
            key="top_sheet_selectbox"
        )
        chosen_top_plan = next((s for s in ranked_top_sheets if s["name"] == selected_sheet_name), ranked_top_sheets[0])
        st.session_state["selected_sheet_name"] = chosen_top_plan["name"]

    # Snabbvisning av vald skiva i sidomenyn
    seam_badge = "🟢 0 skarvar (Hel skiva!)" if chosen_top_plan["seams"] == 0 else f"🟡 {chosen_top_plan['seams']} st skarv{'ar' if chosen_top_plan['seams'] > 1 else ''}"
    st.info(
        f"**Vald:** {chosen_top_plan['name']}\n\n"
        f"• **Skarvstatus:** {seam_badge}\n\n"
        f"• **Inköp:** {chosen_top_plan['sheets_needed']} st à {chosen_top_plan['piece_price']:.0f} kr = **{chosen_top_plan['total_cost']:.0f} kr**\n\n"
        f"• **Tjocklek:** {chosen_top_plan['thickness']} mm"
    )

    screw_cost = st.number_input("Fästelement schablon (kr)", min_value=0.0, step=10.0, key="screw_cost")

    st.markdown("**Kapinställningar**")
    saw_kerf_mm = st.number_input(
        "Sågspårsbredd / kapförlust (mm)",
        min_value=0,
        max_value=15,
        step=1,
        key="saw_kerf_mm",
        help="Extra millimeter som förbrukas av sågklingans snitt per kapning."
    )

    st.divider()

    # ---- Vyer ----
    st.subheader("👁️ Vy-alternativ")
    show_tabletop   = st.toggle("Visa bänkskiva", value=True, key="show_tabletop")
    show_rails      = st.toggle("Visa sarger & tvärslåar", value=True, key="show_rails")
    show_dimensions = st.toggle("Visa mått mellan benen", value=True, key="show_dimensions", help="Visar måttlinjer och fritt avstånd mellan benparen på golvet i 3D-modellen.")
    show_edges      = st.toggle("Visa konturer / kanter", value=True, key="show_edges")
    show_seams      = st.toggle("Visa skarvmarkeringar i 3D", value=True, key="show_seams")
    show_legend     = st.toggle("Visa dellista i 3D (legend)", value=False, key="show_legend", help="Visa eller dölj rutan 'Delar - klicka för att växla' uppe till höger i 3D-modellen.")
    dark_3d         = st.toggle("Mörk 3D-bakgrund", value=True, key="dark_3d")

    st.divider()

    # ---- Spara preset ----
    with st.expander("💾 Spara preset"):
        preset_name = st.text_input("Presetnamn", placeholder="Min arbetsbänk")
        if st.button("Spara preset", use_container_width=True):
            if preset_name.strip():
                _save_preset(preset_name.strip(), _params_to_dict(st.session_state))
            else:
                st.warning("Ange ett namn.")

    # ---- Export / Import ----
    with st.expander("📤 Export / Import JSON"):
        export_data = json.dumps(_params_to_dict(st.session_state), ensure_ascii=False, indent=2)
        st.download_button(
            "⬇️ Ladda ner konfiguration",
            data=export_data.encode("utf-8"),
            file_name="arbetsbänk_config.json",
            mime="application/json",
            use_container_width=True,
        )
        uploaded = st.file_uploader("Ladda upp konfiguration (.json)", type="json")
        if uploaded:
            try:
                _apply_dict(json.loads(uploaded.read().decode("utf-8")))
                st.success("Konfiguration laddad!")
                st.rerun()
            except Exception as e:
                st.error(f"Fel vid inläsning: {e}")


# ---------------------------------------------------------------------------
# BERÄKNINGAR
# ---------------------------------------------------------------------------

ss = st.session_state

geo = BenchGeometry(
    L=ss.L, B=ss.B, H=ss.H,
    overhang_kortsida=ss.overhang_kortsida,
    overhang_längssida=ss.overhang_längssida,
    lower_rail_h=ss.lower_rail_h,
    n_pairs=ss.n_pairs,
    leg_profile=ss.leg_profile,
    frame_profile=ss.frame_profile,
    tabletop_option=chosen_top_plan["name"],
    tabletop_thickness_mm=chosen_top_plan["thickness"],
    tabletop_pieces=chosen_top_plan.get("pieces"),
    tabletop_seams=chosen_top_plan.get("seams_info"),
)
geo.compute()

purchase_plan = run_optimization(
    geo.cuts,
    ss.leg_price,
    ss.frame_price,
    leg_profile=ss.leg_profile,
    frame_profile=ss.frame_profile,
    saw_kerf_mm=getattr(ss, "saw_kerf_mm", 5),
)
costs = compute_cost(
    geo,
    ss.leg_price,
    ss.frame_price,
    chosen_top_plan["piece_price"],
    ss.screw_cost,
    purchase_plan,
    tabletop_plan=chosen_top_plan,
)
shopping_items = build_shopping_items(purchase_plan, geo, ss, chosen_top_plan)

# ---------------------------------------------------------------------------
# HUVUD-LAYOUT
# ---------------------------------------------------------------------------

st.title("🔨 Arbetsbänkskalkylator")

# ---- KPI-kort ----
tot_waste_cost = costs['total_waste']
tot_bought_cost = costs['total_bought']
total_waste_pct = (tot_waste_cost / tot_bought_cost * 100.0) if tot_bought_cost > 0 else 0.0

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">Inköpt material</div>
        <div class="kpi-value">{costs['total_bought']:,.0f} kr</div>
        <div class="kpi-sub">att betala i butik</div>
    </div>""", unsafe_allow_html=True)
with k2:
    st.markdown(f"""<div class="kpi-card" style="border-left-color: #4CAF50;">
        <div class="kpi-label">Faktiskt använt</div>
        <div class="kpi-value" style="color: #69F0AE;">{costs['total_used']:,.0f} kr</div>
        <div class="kpi-sub">material i bänken</div>
    </div>""", unsafe_allow_html=True)
with k3:
    waste_color = "#FF6B6B" if total_waste_pct > 20 else "#FFB74D"
    st.markdown(f"""<div class="kpi-card" style="border-left-color: {waste_color};">
        <div class="kpi-label">Spillkostnad</div>
        <div class="kpi-value" style="color:{waste_color}">{tot_waste_cost:,.0f} kr</div>
        <div class="kpi-sub">{total_waste_pct:.1f}% totalt spill</div>
    </div>""", unsafe_allow_html=True)
with k4:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">Virkesbehov</div>
        <div class="kpi-value">{purchase_plan['total_lpm']:.1f} lpm</div>
        <div class="kpi-sub">varav {purchase_plan.get('total_used_lpm', 0.0):.1f} lpm i bänk</div>
    </div>""", unsafe_allow_html=True)
with k5:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">Bänkskiva / Ram</div>
        <div class="kpi-value">{geo.tabletop_L}×{geo.tabletop_B}</div>
        <div class="kpi-sub">Ram: {ss.L}×{ss.B} · H: {ss.H} mm</div>
    </div>""", unsafe_allow_html=True)

# ---- PDF-Rapport Banner ----
pdf_b1, pdf_b2 = st.columns([3, 1])
with pdf_b1:
    st.markdown("""
    <div style="background: rgba(2, 132, 199, 0.08); border: 1px solid rgba(2, 132, 199, 0.25); border-radius: 8px; padding: 10px 14px; margin-top: 4px; margin-bottom: 4px;">
        <div style="font-weight: 600; color: #38bdf8; font-size: 14px; margin-bottom: 2px;">📄 Redo att bygga eller handla virke?</div>
        <div style="color: #94a3b8; font-size: 12.5px;">Generera en komplett 2-sidig PDF-rapport med 3D-modell, mått, butikslista för jem & fix, sågplan och kapnota.</div>
    </div>
    """, unsafe_allow_html=True)
with pdf_b2:
    st.write("")
    render_pdf_export_widget(geo, purchase_plan, costs, chosen_top_plan, shopping_items, key_suffix="top_banner")

st.markdown("---")

# ---- 3D-VY + DETALJRUTA ----
st.markdown('<div class="section-header"><h3>🎯 Interaktiv 3D-modell</h3></div>', unsafe_allow_html=True)

# ---- 3D-VISUALISERING (Full bredd) ----
fig = build_figure(
    geo,
    highlighted_name=None,
    show_tabletop=ss.show_tabletop,
    show_rails=ss.show_rails,
    dark_theme=ss.get("dark_3d", True),
    show_edges=ss.get("show_edges", True),
    show_seams=ss.get("show_seams", True),
    show_legend=ss.get("show_legend", False),
    show_dimensions=ss.get("show_dimensions", True),
)
st.plotly_chart(fig, use_container_width=True, key="bench_3d")

# Kompakt färglegende under 3D-modellen
legend_badges = [
    '<span style="display:inline-block;width:12px;height:12px;background:#C88A38;border-radius:2px;margin-right:5px;vertical-align:middle;"></span>Ben',
    '<span style="display:inline-block;width:12px;height:12px;background:#72A852;border-radius:2px;margin-right:5px;vertical-align:middle;"></span>Sarger',
    '<span style="display:inline-block;width:12px;height:12px;background:#5090BB;border-radius:2px;margin-right:5px;vertical-align:middle;"></span>Tvärslåar',
    '<span style="display:inline-block;width:12px;height:12px;background:#C8A46A;border-radius:2px;margin-right:5px;vertical-align:middle;"></span>Bänkskiva',
    '<span style="display:inline-block;width:12px;height:12px;background:#38bdf8;border-radius:2px;margin-right:5px;vertical-align:middle;"></span>Benavstånd',
]
if chosen_top_plan.get("seams", 0) > 0:
    legend_badges.append(
        '<span style="display:inline-block;width:12px;height:12px;background:#FF4444;border-radius:2px;margin-right:5px;vertical-align:middle;"></span>Skarvlinje'
    )

badge_html = " &nbsp;&nbsp;•&nbsp;&nbsp; ".join(legend_badges)
st.markdown(
    f'<div style="text-align:center; padding:6px 12px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06); border-radius:6px; font-size:13px; color:#94a3b8; margin-top:-10px; margin-bottom:12px;">'
    f'🎨 <b>Färgförklaring:</b> &nbsp; {badge_html}'
    f'</div>',
    unsafe_allow_html=True
)

if chosen_top_plan.get("seams", 0) > 0:
    seams_desc_list = [s["desc"] for s in chosen_top_plan.get("seams_info", [])]
    st.info(f"📍 **Bänkskivans skarvar ({chosen_top_plan['seams']} st):** {', '.join(seams_desc_list)}. Markeras med röd linje i 3D-modellen.")

st.markdown("---")

# ---- KAPNOTA ----
st.markdown('<div class="section-header"><h3>📋 Kapnota</h3></div>', unsafe_allow_html=True)

cut_rows = []
for cut in geo.cuts:
    cut_rows.append({
        "Delnamn": cut.name,
        "Antal": cut.quantity,
        "Längd (mm)": cut.length_mm,
        "Profil / Material": cut.profile,
        "Kategori": cut.category,
    })

cut_df = pd.DataFrame(cut_rows)
st.dataframe(
    cut_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Längd (mm)": st.column_config.NumberColumn(format="%d mm"),
        "Antal": st.column_config.NumberColumn(format="%d st"),
    }
)

st.markdown("---")

# ---- INKÖP & SÅGPLAN ----
st.markdown('<div class="section-header"><h3>🛒 Inköp & Sågplan (jem & fix)</h3></div>', unsafe_allow_html=True)

# Varningar om något stycke är längre än tillgängligt virke
if purchase_plan.get("is_combined"):
    if purchase_plan.get("timber_warning"):
        st.warning(f"⚠️ {purchase_plan['timber_warning']}")
else:
    if purchase_plan.get("leg_warning"):
        st.warning(f"⚠️ {purchase_plan['leg_warning']}")
    if purchase_plan.get("frame_warning"):
        st.warning(f"⚠️ {purchase_plan['frame_warning']}")

# Samlad inköpslista för butiken
st.markdown("#### 📝 Inköpslista till bygghandeln")
st.dataframe(
    pd.DataFrame(shopping_items),
    hide_index=True,
    use_container_width=True,
    column_config={
        "Styckpris": st.column_config.NumberColumn("Styckpris", format="%.2f kr"),
        "Delsumma": st.column_config.NumberColumn("Delsumma", format="%.2f kr"),
    }
)

st.markdown("---")

def _render_saw_plan(bins, stock_len, article_name, unit_price, comparison, profile, board_summary=None, total_cost=None, total_lpm=None):
    if not bins:
        st.info("Inga delar i denna kategori.")
        return

    total = len(bins)
    cost = total_cost if total_cost is not None else (total * unit_price)
    tot_lpm = total_lpm if total_lpm is not None else (sum(b.stock_length for b in bins) / 1000.0)

    if board_summary and len(board_summary) > 1:
        st.markdown(f"**Valt inköp:** `Optimal mix ({total} st reglar)`")
        summary_bullets = " &nbsp;•&nbsp; ".join([f"**{b['count']} st** à {b['length_mm']/1000:.1f} m ({b['name']})" for b in board_summary])
        st.markdown(f"📦 {summary_bullets}")
        st.markdown(f"**Total inköpskostnad:** **{cost:,.2f} kr** ({tot_lpm:.1f} lpm virke)")
    else:
        st.markdown(f"**Vald artikel:** `{article_name}`")
        st.markdown(f"**Inköp:** **{total} st reglar** à {unit_price:.2f} kr = **{cost:,.2f} kr** ({tot_lpm:.1f} lpm)")

    # Expander med butikens sortiment för denna profil
    if comparison:
        with st.expander(f"🏬 Se tillgängliga regellängder hos jem & fix ({profile})", expanded=True):
            st.caption("Optimeraren pusslar och väljer automatiskt den kombination av regellängder som minimerar din totalkostnad och virkesspill.")
            formatted_comp = []
            for row in comparison:
                r = dict(row)
                is_selected = (
                    r.get("Status") == "Vald" or
                    r.get("length_mm") == stock_len or
                    r.get("Artikel") == article_name or
                    r.get("Artikel") == f"👉 {article_name}"
                )
                if is_selected:
                    art = str(r["Artikel"])
                    if not art.startswith("👉 "):
                        r["Artikel"] = f"👉 {art}"
                    r["Status"] = "Vald"
                formatted_comp.append(r)
            comp_df = pd.DataFrame(formatted_comp)[[
                "Längd", "Artikel", "Styckpris", "Antal som krävs", "Totalkostnad", "Spill", "Status"
            ]]
            st.dataframe(
                comp_df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Styckpris": st.column_config.NumberColumn("Styckpris", format="%.2f kr"),
                    "Antal som krävs": st.column_config.NumberColumn("Antal som krävs", format="%d st"),
                    "Totalkostnad": st.column_config.NumberColumn("Totalkostnad", format="%.2f kr"),
                    "Spill": st.column_config.NumberColumn("Spill", format="%.1f%%"),
                }
            )

    st.markdown("##### 🪚 Sågplan & Kapunderlag (hur reglarna ska kapas)")

    # Visuell färglegend
    st.markdown("""
    <div style="display: flex; gap: 14px; flex-wrap: wrap; align-items: center; background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(148, 163, 184, 0.15); border-radius: 6px; padding: 7px 12px; margin-bottom: 12px; font-size: 12px; color: #cbd5e1;">
        <span style="font-weight: 600; color: #f8fafc;">🎨 Färgförklaring:</span>
        <span style="display: inline-flex; align-items: center; gap: 5px;"><span style="width: 13px; height: 13px; background: #d97706; border-radius: 3px; display: inline-block;"></span> <b>Ben</b></span>
        <span style="display: inline-flex; align-items: center; gap: 5px;"><span style="width: 13px; height: 13px; background: #16a34a; border-radius: 3px; display: inline-block;"></span> <b>Sarger</b></span>
        <span style="display: inline-flex; align-items: center; gap: 5px;"><span style="width: 13px; height: 13px; background: #0284c7; border-radius: 3px; display: inline-block;"></span> <b>Tvärslåar</b></span>
        <span style="display: inline-flex; align-items: center; gap: 5px;"><span style="width: 3.5px; height: 13px; background: #ef4444; display: inline-block; border-radius: 1px;"></span> <b>Sågspår (5 mm)</b></span>
        <span style="display: inline-flex; align-items: center; gap: 5px;"><span style="width: 13px; height: 13px; background: repeating-linear-gradient(45deg, #334155, #334155 3px, #1e293b 3px, #1e293b 6px); border-radius: 3px; display: inline-block; border: 1px solid #475569;"></span> <b>Spill / Restbit</b></span>
    </div>
    """, unsafe_allow_html=True)

    def _get_part_info(name: str):
        n = name.lower()
        if "ben" in n:
            return "Ben", "#d97706", "linear-gradient(180deg, #d97706 0%, #b45309 100%)"
        elif "sarg" in n:
            return "Sarg", "#16a34a", "linear-gradient(180deg, #16a34a 0%, #15803d 100%)"
        elif "tvärslå" in n or "tvarsla" in n:
            return "Tvärslå", "#0284c7", "linear-gradient(180deg, #0284c7 0%, #0369a1 100%)"
        return "Övrigt", "#6366f1", "linear-gradient(180deg, #6366f1 0%, #4f46e5 100%)"

    for i, b in enumerate(bins, 1):
        b_len = b.stock_length
        pct = (b.remaining / b_len * 100.0) if b_len > 0 else 0.0
        kerf = getattr(b, "saw_kerf", 5)

        # Ackumulerade snittmått
        cut_marks = []
        cum = 0
        for idx, (name, length) in enumerate(b.cuts):
            if idx > 0:
                cum += kerf
            cum += length
            cut_marks.append(cum)

        marks_html = " &nbsp;➜&nbsp; ".join([f"<b style='color:#38bdf8;'>{m:,} mm</b>" for m in cut_marks])

        # Spill-badge färg
        if pct <= 4.0:
            spill_badge = f'<span style="background: rgba(34, 197, 94, 0.15); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.3); padding: 2px 8px; border-radius: 4px; font-weight: 600;">Spill: {b.remaining:,} mm ({pct:.1f}%)</span>'
        elif pct <= 15.0:
            spill_badge = f'<span style="background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); padding: 2px 8px; border-radius: 4px; font-weight: 600;">Spill: {b.remaining:,} mm ({pct:.1f}%)</span>'
        else:
            spill_badge = f'<span style="background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); padding: 2px 8px; border-radius: 4px; font-weight: 600;">Spill: {b.remaining:,} mm ({pct:.1f}%)</span>'

        # Bygg segment för balken
        segments_html = []
        for idx, (name, length) in enumerate(b.cuts):
            w_pct = (length / b_len) * 100.0
            cat, col, grad = _get_part_info(name)

            short_name = name
            for prefix in ["Vänster gavel – ", "Höger gavel – ", "Mellanpar 1 – ", "Mellanpar 2 – ", "Mellanpar 3 – "]:
                short_name = short_name.replace(prefix, "")
            short_name = short_name.replace("övre ", "Ö. ").replace("nedre ", "N. ")

            if w_pct >= 13.0:
                inner_text = f"<div style='font-size:11px; font-weight:600; color:#fff; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:92%; text-shadow:0 1px 2px rgba(0,0,0,0.8);'>{short_name}</div><div style='font-size:12px; font-weight:800; color:#fff; text-shadow:0 1px 2px rgba(0,0,0,0.8);'>{length} mm</div>"
            elif w_pct >= 6.5:
                inner_text = f"<div style='font-size:10px; font-weight:600; color:#fff; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:92%; text-shadow:0 1px 2px rgba(0,0,0,0.8);'>{short_name}</div><div style='font-size:11px; font-weight:700; color:#fff;'>{length}</div>"
            elif w_pct >= 3.5:
                inner_text = f"<div style='font-size:10px; font-weight:700; color:#fff;'>{length}</div>"
            else:
                inner_text = "<div style='font-size:8px; font-weight:700; color:#fff;'>•</div>"

            seg = f"""<div style="width: {w_pct:.3f}%; height: 100%; background: {grad}; border-right: 3px solid #ef4444; display: flex; flex-direction: column; align-items: center; justify-content: center; overflow: hidden; padding: 0 3px; box-sizing: border-box; cursor: default;" title="{name}: {length} mm ({cat})">{inner_text}</div>"""
            segments_html.append(seg)

        # Restbit / spill
        rem_pct = (b.remaining / b_len) * 100.0
        if rem_pct > 0.0:
            if rem_pct >= 10.0:
                waste_inner = f"<div style='font-size:10px; font-weight:600; color:#94a3b8;'>Spill</div><div style='font-size:11px; font-weight:700; color:#cbd5e1;'>{b.remaining} mm</div>"
            elif rem_pct >= 4.0:
                waste_inner = f"<div style='font-size:10px; font-weight:700; color:#cbd5e1;'>{b.remaining}</div>"
            else:
                waste_inner = ""
            waste_seg = f"""<div style="width: {rem_pct:.3f}%; height: 100%; background: repeating-linear-gradient(45deg, #334155, #334155 8px, #1e293b 8px, #1e293b 16px); display: flex; flex-direction: column; align-items: center; justify-content: center; overflow: hidden; padding: 0 2px; box-sizing: border-box;" title="Spill / restbit: {b.remaining} mm ({pct:.1f}%)">{waste_inner}</div>"""
            segments_html.append(waste_seg)

        board_bar_html = f"""
        <div style="background: #0f172a; border-radius: 8px; border: 1px solid #334155; margin-bottom: 14px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.25);">
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 9px 14px; background: #1e293b; border-bottom: 1px solid #334155; flex-wrap: wrap; gap: 8px;">
                <div>
                    <span style="font-size: 15px; font-weight: 700; color: #f8fafc;">Regel #{i}: {b_len:,} mm</span>
                    <span style="font-size: 13px; color: #94a3b8; margin-left: 6px;">({profile})</span>
                </div>
                <div style="display: flex; gap: 8px; font-size: 12px; align-items: center;">
                    <span style="background: rgba(2, 132, 199, 0.15); color: #38bdf8; border: 1px solid rgba(2, 132, 199, 0.3); padding: 2px 8px; border-radius: 4px; font-weight: 600;">{len(b.cuts)} kapade delar</span>
                    {spill_badge}
                </div>
            </div>
            <div style="padding: 12px 14px 10px 14px;">
                <div style="display: flex; width: 100%; height: 40px; border-radius: 6px; overflow: hidden; background: #1e293b; border: 1px solid #475569; box-shadow: inset 0 2px 4px rgba(0,0,0,0.5); position: relative;">
                    {''.join(segments_html)}
                </div>
                <div style="margin-top: 8px; font-size: 12px; color: #cbd5e1; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 6px;">
                    <div>
                        <span style="color: #ef4444; font-weight: 700;">✂️ Kapa vid:</span>
                        <span style="margin-left: 4px;">{marks_html}</span>
                        <span style="color: #94a3b8; margin-left: 8px;">• &nbsp; Restbit: <b style="color: #f1f5f9;">{b.remaining:,} mm</b></span>
                    </div>
                    <div style="color: #94a3b8; font-size: 11px;">
                        <i>5 mm sågspår inräknat per snitt</i>
                    </div>
                </div>
            </div>
        </div>
        """
        st.markdown(board_bar_html, unsafe_allow_html=True)

        with st.expander(f"📋 Visa mått- och deltabell för Regel #{i}", expanded=False):
            rows = []
            cum_m = 0
            for idx, (name, length) in enumerate(b.cuts):
                if idx > 0:
                    cum_m += kerf
                cum_m += length
                cat, _, _ = _get_part_info(name)
                rows.append({
                    "Del / Placering": name,
                    "Kategori": cat,
                    "Kaplängd (mm)": f"{length} mm",
                    "Snittmått från start (mm)": f"{cum_m} mm",
                })
            rows.append({
                "Del / Placering": "Spill / restbit",
                "Kategori": "Spill",
                "Kaplängd (mm)": f"{b.remaining} mm",
                "Snittmått från start (mm)": "-",
            })
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

if purchase_plan.get("is_combined"):
    summary_str = purchase_plan.get("timber_board_summary_str")
    tab_title = f"Virke (Ben & Ram): {purchase_plan['timber_n_pieces']} st ({summary_str})" if summary_str else f"Virke (Ben & Ram): {purchase_plan['timber_n_pieces']} st {purchase_plan['timber_article_name']}"
    tab_timber, tab_top = st.tabs([
        tab_title,
        f"Bänkskiva: {chosen_top_plan['sheets_needed']} st ({chosen_top_plan['seam_label']})"
    ])
    with tab_timber:
        st.info(f"💡 **Gemensam kapoptimering:** Eftersom ben, sarger och tvärslåar har samma dimension ({ss.leg_profile}) optimeras de tillsammans på reglar av blandade handelslängder för att minimera spill och totalkostnad.")
        _render_saw_plan(
            purchase_plan["timber_bins"],
            purchase_plan["timber_stock_length"],
            purchase_plan["timber_article_name"],
            purchase_plan["timber_piece_price"],
            purchase_plan["timber_comparison"],
            ss.leg_profile,
            board_summary=purchase_plan.get("timber_board_summary"),
            total_cost=purchase_plan.get("timber_total_cost"),
            total_lpm=purchase_plan.get("timber_total_lpm"),
        )
else:
    leg_summary_str = purchase_plan.get("leg_board_summary_str")
    leg_title = f"Ben: {purchase_plan['leg_n_pieces']} st ({leg_summary_str})" if leg_summary_str else f"Ben: {purchase_plan['leg_n_pieces']} st {purchase_plan['leg_article_name']}"
    frame_summary_str = purchase_plan.get("frame_board_summary_str")
    frame_title = f"Sarger & Tvärslåar: {purchase_plan['frame_n_pieces']} st ({frame_summary_str})" if frame_summary_str else f"Sarger & Tvärslåar: {purchase_plan['frame_n_pieces']} st {purchase_plan['frame_article_name']}"

    tab_leg, tab_frame, tab_top = st.tabs([
        leg_title,
        frame_title,
        f"Bänkskiva: {chosen_top_plan['sheets_needed']} st ({chosen_top_plan['seam_label']})"
    ])
    with tab_leg:
        _render_saw_plan(
            purchase_plan["leg_bins"],
            purchase_plan["leg_stock_length"],
            purchase_plan["leg_article_name"],
            purchase_plan["leg_piece_price"],
            purchase_plan["leg_comparison"],
            ss.leg_profile,
            board_summary=purchase_plan.get("leg_board_summary"),
            total_cost=purchase_plan.get("leg_total_cost"),
            total_lpm=purchase_plan.get("leg_total_lpm"),
        )

    with tab_frame:
        _render_saw_plan(
            purchase_plan["frame_bins"],
            purchase_plan["frame_stock_length"],
            purchase_plan["frame_article_name"],
            purchase_plan["frame_piece_price"],
            purchase_plan["frame_comparison"],
            ss.frame_profile,
            board_summary=purchase_plan.get("frame_board_summary"),
            total_cost=purchase_plan.get("frame_total_cost"),
            total_lpm=purchase_plan.get("frame_total_lpm"),
        )

with tab_top:
    st.markdown(f"**Vald bänkskiva:** `{chosen_top_plan['name']}`")
    st.markdown(
        f"**Inköp:** **{chosen_top_plan['sheets_needed']} st skiva/skivor** à {chosen_top_plan['piece_price']:.2f} kr = "
        f"**{chosen_top_plan['total_cost']:,.2f} kr**"
    )

    if chosen_top_plan["seams"] == 0:
        st.success(f"🟢 **Helt skarvfri bänkskiva!** Skivan täcker hela arbetsbänken ({geo.tabletop_L} × {geo.tabletop_B} mm inkl. överhäng) i ett enda stycke.")
    else:
        st.info(f"🟡 **{chosen_top_plan['seams']} st skarv{'ar' if chosen_top_plan['seams'] > 1 else ''}:** {chosen_top_plan['layout_desc']}.")

    st.markdown(f"**Såginstruktion:** {chosen_top_plan['cuts_desc']}")

    col_t1, col_t2, col_t3 = st.columns(3)
    with col_t1:
        st.metric("Behövd bänkyta", f"{geo.tabletop_area_m2:.2f} m²", help="Effektiv ovanyta på bänken.")
    with col_t2:
        tot_sheet_area = chosen_top_plan['sheets_needed'] * (chosen_top_plan['sheet']['length'] * chosen_top_plan['sheet']['width'] / 1e6)
        st.metric("Inköpt skivyta", f"{tot_sheet_area:.2f} m²", help="Total yta för hela skivorna som köps.")
    with col_t3:
        st.metric("Skivspill", f"{chosen_top_plan['waste_pct']:.1f}%", f"{chosen_top_plan['waste_cost']:.0f} kr spill", delta_color="inverse")

    st.markdown("---")
    st.markdown("##### 📊 Jämförelse av alla bänkskivor (jem & fix sortiment ≥ 8 mm)")
    st.caption("Skivorna är rangordnade efter: **1. Minst antal skarvar** (0 skarvar prioriteras högst) → **2. Lägst inköpspris** → **3. Minst spill**.")

    table_data = []
    for rank_idx, r in enumerate(ranked_top_sheets, 1):
        is_selected = (r["name"] == chosen_top_plan["name"])
        prefix = "👉 " if is_selected else ""
        table_data.append({
            "Rank": rank_idx,
            "Status": "Vald" if is_selected else "Möjlig",
            "Artikel (jem & fix)": f"{prefix}{r['name']}",
            "Material": r["material"],
            "Tjocklek": int(r["thickness"]),
            "Skivmått": r["sheet_dim"],
            "Skarvar": r["seam_label"],
            "Antal": int(r["sheets_needed"]),
            "Inköpspris": int(round(r["total_cost"])),
            "Använt värde": int(round(r["used_cost"])),
            "Spill": int(round(r["waste_pct"])),
        })

    st.dataframe(
        pd.DataFrame(table_data),
        hide_index=True,
        use_container_width=True,
        column_config={
            "Rank": st.column_config.NumberColumn("Rank", format="#%d"),
            "Status": st.column_config.TextColumn("Status"),
            "Tjocklek": st.column_config.NumberColumn("Tjocklek", format="%d mm"),
            "Antal": st.column_config.NumberColumn("Antal", format="%d st"),
            "Inköpspris": st.column_config.NumberColumn("Inköpspris", format="%d kr"),
            "Använt värde": st.column_config.NumberColumn("Använt värde", format="%d kr"),
            "Spill": st.column_config.NumberColumn("Spill", format="%d%%"),
        }
    )

st.markdown("---")

# ---- KOSTNADSSPECIFIKATION ----
st.markdown('<div class="section-header"><h3>💰 Kostnadsspecifikation</h3></div>', unsafe_allow_html=True)
st.caption("Jämförelse mellan vad som köps in hos byggvaruhuset och vad som faktiskt ingår i den färdiga arbetsbänken.")

cost_df = pd.DataFrame(costs["items"])
st.dataframe(
    cost_df,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Inköpt material (kr)": st.column_config.NumberColumn(format="%.2f kr"),
        "Faktiskt använt (kr)": st.column_config.NumberColumn(format="%.2f kr"),
        "Spillkostnad (kr)": st.column_config.NumberColumn(format="%.2f kr"),
    }
)

m1, m2, m3 = st.columns(3)
with m1:
    st.metric(
        "🛒 Totalt inköpt material",
        f"{costs['total_bought']:,.2f} kr",
        help="Totalsumma för hela reglar, skivmaterial och skruvpaket som betalas i butiken."
    )
with m2:
    st.metric(
        "🔨 Faktiskt använt material",
        f"{costs['total_used']:,.2f} kr",
        help="Det effektiva värdet av det material som sitter i den färdiga bänken."
    )
with m3:
    st.metric(
        "🗑️ Beräknad spillkostnad",
        f"{costs['total_waste']:,.2f} kr",
        delta=f"-{total_waste_pct:.1f}% spill",
        delta_color="inverse",
        help="Värdet av det överblivna virkesspillet och avsågade skivbitar."
    )

# ---- PDF-RAPPORT SEKTION ----
st.markdown("---")
st.markdown('<div class="section-header"><h3>📄 Exportera PDF-rapport</h3></div>', unsafe_allow_html=True)
pdf_c1, pdf_c2 = st.columns([2.5, 1.5])
with pdf_c1:
    st.write("Generera en professionell 2-sidig PDF-rapport som du kan skriva ut eller ta med i mobilen till bygghandeln och snickeriet:")
    st.markdown("""
    - **🎯 3D-konstruktionsritning i färg** med måttlinjer och benavstånd
    - **🛒 Inköpslista till jem & fix** med artiklar, längder och priser
    - **🪚 Sågplan** för hur varje enskild regel kapas med minimalt spill
    - **📋 Komplett kapnota** med mått och antal för alla delar
    - **💰 Kostnadsspecifikation & spillanalys**
    """)
with pdf_c2:
    st.write("")
    st.write("")
    render_pdf_export_widget(geo, purchase_plan, costs, chosen_top_plan, shopping_items, key_suffix="bottom_section")

# Sidomeny-widget för PDF
with st.sidebar:
    st.divider()
    st.subheader("📄 PDF-Rapport")
    st.caption("Ladda ner ritning & inköpslista:")
    render_pdf_export_widget(geo, purchase_plan, costs, chosen_top_plan, shopping_items, key_suffix="sidebar")

# Footer
st.markdown("---")
st.caption("Byggkalkylator v1.0 · Lokalt verktyg · Alla priser är uppskattningar utan moms.")
