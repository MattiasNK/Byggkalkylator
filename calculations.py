"""
calculations.py – Geometri, kapnota och kostnadskalkyl för arbetsbänk.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional


# ---------------------------------------------------------------------------
# Materialkataloger (baserat på aktuellt sortiment hos jem & fix)
# ---------------------------------------------------------------------------

TIMBER_PROFILES: Dict[str, Tuple[int, int]] = {
    "45×45 mm":  (45, 45),
    "45×70 mm":  (45, 70),
    "45×95 mm":  (45, 95),
    "45×120 mm": (45, 120),
    "45×145 mm": (45, 145),
    "45×170 mm": (45, 170),
}

# Standardpriser per löpmeter baserat på jem & fix (ordinarie byggreglar)
DEFAULT_TIMBER_PRICES: Dict[str, float] = {
    "45×45 mm":  16.45,
    "45×70 mm":  25.25,
    "45×95 mm":  30.75,
    "45×120 mm": 39.95,
    "45×145 mm": 51.65,
    "45×170 mm": 60.45,
}

# Tillgängliga handelslängder och styckpriser hos butiken (jem & fix)
# Innehåller alla tillgängliga längder, styckpriser och meterpriser
STORE_CATALOG: Dict[str, List[Dict[str, any]]] = {
    "45×45 mm": [
        {"name": "Kortregel 45×45 mm 2,5 m", "length_mm": 2500, "price": 43.63, "price_per_m": 17.45},
        {"name": "Byggregel 45×45 mm 3,0 m", "length_mm": 3000, "price": 49.35, "price_per_m": 16.45},
        {"name": "Byggregel 45×45 mm 3,6 m", "length_mm": 3600, "price": 59.22, "price_per_m": 16.45},
        {"name": "Byggregel 45×45 mm 4,2 m", "length_mm": 4200, "price": 69.09, "price_per_m": 16.45},
    ],
    "45×70 mm": [
        {"name": "Kortregel 45×70 mm 2,5 m", "length_mm": 2500, "price": 65.88, "price_per_m": 26.35},
        {"name": "Byggregel 45×70 mm 3,0 m", "length_mm": 3000, "price": 75.75, "price_per_m": 25.25},
        {"name": "Byggregel 45×70 mm 3,6 m", "length_mm": 3600, "price": 90.90, "price_per_m": 25.25},
        {"name": "Byggregel 45×70 mm 4,2 m", "length_mm": 4200, "price": 106.05, "price_per_m": 25.25},
    ],
    "45×95 mm": [
        {"name": "Kortregel 45×95 mm 2,5 m", "length_mm": 2500, "price": 82.38, "price_per_m": 32.95},
        {"name": "Byggregel 45×95 mm 3,0 m", "length_mm": 3000, "price": 92.25, "price_per_m": 30.75},
        {"name": "Byggregel 45×95 mm 3,6 m", "length_mm": 3600, "price": 110.70, "price_per_m": 30.75},
        {"name": "Byggregel 45×95 mm 4,2 m", "length_mm": 4200, "price": 129.15, "price_per_m": 30.75},
    ],
    "45×120 mm": [
        {"name": "Byggregel 45×120 mm 3,0 m", "length_mm": 3000, "price": 119.85, "price_per_m": 39.95},
        {"name": "Byggregel 45×120 mm 3,6 m", "length_mm": 3600, "price": 143.82, "price_per_m": 39.95},
        {"name": "Byggregel 45×120 mm 4,2 m", "length_mm": 4200, "price": 167.79, "price_per_m": 39.95},
    ],
    "45×145 mm": [
        {"name": "Byggregel 45×145 mm 3,0 m", "length_mm": 3000, "price": 154.95, "price_per_m": 51.65},
        {"name": "Byggregel 45×145 mm 3,6 m", "length_mm": 3600, "price": 185.94, "price_per_m": 51.65},
        {"name": "Byggregel 45×145 mm 4,2 m", "length_mm": 4200, "price": 216.93, "price_per_m": 51.65},
        {"name": "Byggregel 45×145 mm 4,8 m", "length_mm": 4800, "price": 247.92, "price_per_m": 51.65},
    ],
    "45×170 mm": [
        {"name": "Byggregel 45×170 mm 3,0 m", "length_mm": 3000, "price": 181.35, "price_per_m": 60.45},
        {"name": "Byggregel 45×170 mm 3,6 m", "length_mm": 3600, "price": 217.62, "price_per_m": 60.45},
        {"name": "Byggregel 45×170 mm 4,2 m", "length_mm": 4200, "price": 253.89, "price_per_m": 60.45},
        {"name": "Byggregel 45×170 mm 4,8 m", "length_mm": 4800, "price": 290.16, "price_per_m": 60.45},
    ],
}

# ---------------------------------------------------------------------------
# Bordsskivor (jem & fix sortiment, 8 mm eller tjockare)
# ---------------------------------------------------------------------------

TABLETOP_CATALOG: List[Dict[str, Any]] = [
    # MDF (>= 8 mm)
    {"name": "MDF-skiva 12 x 800 x 1200 mm Hornbaek", "material": "MDF", "thickness": 12, "length": 1200, "width": 800, "price": 169.0},
    {"name": "MDF-skiva 16 x 800 x 1200 mm Hornbaek", "material": "MDF", "thickness": 16, "length": 1200, "width": 800, "price": 199.0},
    {"name": "MDF-skiva 19 x 800 x 1200 mm Hornbaek", "material": "MDF", "thickness": 19, "length": 1200, "width": 800, "price": 299.0},
    {"name": "MDF-skiva 16 x 1220 x 2440 mm Hornbaek", "material": "MDF", "thickness": 16, "length": 2440, "width": 1220, "price": 569.0},
    {"name": "MDF-skiva Svart 12 x 800 x 1200 mm Hornbaek", "material": "MDF (Svart)", "thickness": 12, "length": 1200, "width": 800, "price": 349.0},
    {"name": "MDF-skiva Svart 16 x 800 x 1200 mm Hornbaek", "material": "MDF (Svart)", "thickness": 16, "length": 1200, "width": 800, "price": 399.0},
    # OSB (>= 8 mm)
    {"name": "OSB-skiva Conti 10 x 1197 x 2390 mm", "material": "OSB", "thickness": 10, "length": 2390, "width": 1197, "price": 229.0},
    {"name": "OSB-skiva Conti 11 x 897 x 2390 mm", "material": "OSB", "thickness": 11, "length": 2390, "width": 897, "price": 199.0},
    {"name": "OSB-skiva TG4 12 x 600 x 2397 mm", "material": "OSB (TG4)", "thickness": 12, "length": 2397, "width": 600, "price": 149.0},
    {"name": "OSB-skiva SE 15 x 800 x 1200 mm Hornbaek", "material": "OSB", "thickness": 15, "length": 1200, "width": 800, "price": 229.0},
    {"name": "OSB-skiva TG4 18 x 600 x 2397 mm", "material": "OSB (TG4)", "thickness": 18, "length": 2397, "width": 600, "price": 199.0},
    # Plywood (>= 8 mm)
    {"name": "Konstruktionsplywood 12 x 1220 x 2400 mm", "material": "Plywood", "thickness": 12, "length": 2400, "width": 1220, "price": 399.0},
    {"name": "Plywood 8 x 800 x 1200 mm Hornbaek", "material": "Plywood", "thickness": 8, "length": 1200, "width": 800, "price": 229.0},
    {"name": "Plywood 12 x 800 x 1200 mm Hornbaek", "material": "Plywood", "thickness": 12, "length": 1200, "width": 800, "price": 289.0},
]

TABLETOP_OPTIONS: Dict[str, float] = {
    s["name"]: s["price"] for s in TABLETOP_CATALOG
}

TABLETOP_THICKNESS: Dict[str, int] = {
    s["name"]: s["thickness"] for s in TABLETOP_CATALOG
}

import math

def calculate_tabletop_coverage(sheet: Dict[str, Any], L: int, B: int) -> Dict[str, Any]:
    """
    Optimerar täckning av en bordsskiva (L x B mm) med en given skivprodukt.
    Minimerar i första hand antalet skarvar, därefter antal skivor och pris.
    """
    s_len = max(sheet['length'], sheet['width'])
    s_wid = min(sheet['length'], sheet['width'])
    price = sheet['price']
    area_bench_m2 = (L * B) / 1e6
    sheet_area_m2 = (s_len * s_wid) / 1e6

    layouts = []

    # 1. En hel skiva utan skarv?
    if (L <= s_len and B <= s_wid) or (L <= s_wid and B <= s_len):
        layouts.append({
            'sheets_needed': 1,
            'seams': 0,
            'layout_desc': 'Hel skiva (helt utan skarvar!)',
            'cuts_desc': f'1 st skiva kapas till {L} × {B} mm',
            'pieces': [{'x': 0, 'y': 0, 'dx': L, 'dy': B}],
            'seams_info': [],
        })

    # 2. Skarvad längsled (tvärgående skarvar, delar placerade längs L)
    # 2A: Skivans bredd s_wid täcker bänkens djup B (dvs s_wid >= B)
    if s_wid >= B:
        pieces_L = math.ceil(L / s_len)
        strips_per_sheet = max(1, int(s_wid // B))
        sheets = math.ceil(pieces_L / strips_per_sheet)
        seams = pieces_L - 1
        pcs = []
        sms = []
        for i in range(pieces_L):
            x0 = i * s_len
            x1 = min(L, (i + 1) * s_len)
            pcs.append({'x': x0, 'y': 0, 'dx': x1 - x0, 'dy': B})
            if i < pieces_L - 1:
                sms.append({'type': 'X', 'pos': x1, 'desc': f'Tvärgående skarv vid X = {x1} mm'})
        layouts.append({
            'sheets_needed': sheets,
            'seams': seams,
            'layout_desc': f'{pieces_L} sektioner längs bänken ({seams} st tvärgående skarv{"ar" if seams > 1 else ""})',
            'cuts_desc': f'{sheets} st skiva/skivor ger {pieces_L} st sektioner à djup {B} mm',
            'pieces': pcs,
            'seams_info': sms,
        })

    # 2B: Skivans längd s_len täcker bänkens djup B (dvs s_len >= B), delar läggs med s_wid längs L
    if s_len >= B:
        pieces_L = math.ceil(L / s_wid)
        strips_per_sheet = max(1, int(s_len // B))
        sheets = math.ceil(pieces_L / strips_per_sheet)
        seams = pieces_L - 1
        pcs = []
        sms = []
        for i in range(pieces_L):
            x0 = i * s_wid
            x1 = min(L, (i + 1) * s_wid)
            pcs.append({'x': x0, 'y': 0, 'dx': x1 - x0, 'dy': B})
            if i < pieces_L - 1:
                sms.append({'type': 'X', 'pos': x1, 'desc': f'Tvärgående skarv vid X = {x1} mm'})
        layouts.append({
            'sheets_needed': sheets,
            'seams': seams,
            'layout_desc': f'{pieces_L} sektioner längs bänken ({seams} st tvärgående skarv{"ar" if seams > 1 else ""})',
            'cuts_desc': f'{sheets} st skiva/skivor ger {pieces_L} st sektioner à djup {B} mm',
            'pieces': pcs,
            'seams_info': sms,
        })

    # 3. Skarvad djupled (längsgående skarvar, t.ex. TG4 spontade skivor som löper hela L)
    if s_len >= L:
        pieces_B = math.ceil(B / s_wid)
        strips_per_sheet = max(1, int(s_len // L))
        sheets = math.ceil(pieces_B / strips_per_sheet)
        seams = pieces_B - 1
        pcs = []
        sms = []
        for j in range(pieces_B):
            y0 = j * s_wid
            y1 = min(B, (j + 1) * s_wid)
            pcs.append({'x': 0, 'y': y0, 'dx': L, 'dy': y1 - y0})
            if j < pieces_B - 1:
                sms.append({'type': 'Y', 'pos': y1, 'desc': f'Längsgående skarv vid Y = {y1} mm'})
        layouts.append({
            'sheets_needed': sheets,
            'seams': seams,
            'layout_desc': f'{pieces_B} längsgående rader ({seams} st längsgående skarv{"ar" if seams > 1 else ""})',
            'cuts_desc': f'{sheets} st skiva/skivor klyvs till {pieces_B} st längsgående rader à {L} mm',
            'pieces': pcs,
            'seams_info': sms,
        })

    if s_wid >= L:
        pieces_B = math.ceil(B / s_len)
        strips_per_sheet = max(1, int(s_wid // L))
        sheets = math.ceil(pieces_B / strips_per_sheet)
        seams = pieces_B - 1
        pcs = []
        sms = []
        for j in range(pieces_B):
            y0 = j * s_len
            y1 = min(B, (j + 1) * s_len)
            pcs.append({'x': 0, 'y': y0, 'dx': L, 'dy': y1 - y0})
            if j < pieces_B - 1:
                sms.append({'type': 'Y', 'pos': y1, 'desc': f'Längsgående skarv vid Y = {y1} mm'})
        layouts.append({
            'sheets_needed': sheets,
            'seams': seams,
            'layout_desc': f'{pieces_B} längsgående rader ({seams} st längsgående skarv{"ar" if seams > 1 else ""})',
            'cuts_desc': f'{sheets} st skiva/skivor klyvs till {pieces_B} st längsgående rader à {L} mm',
            'pieces': pcs,
            'seams_info': sms,
        })

    # 4. Generellt rutnät (om bänken är mycket stor i både L och B)
    if not layouts:
        p_L1 = math.ceil(L / s_len)
        p_B1 = math.ceil(B / s_wid)
        tot1 = p_L1 * p_B1
        seams1 = (p_L1 - 1) + (p_B1 - 1)
        pcs1 = []
        sms1 = []
        for i in range(p_L1):
            x0 = i * s_len
            x1 = min(L, (i + 1) * s_len)
            if i < p_L1 - 1:
                sms1.append({'type': 'X', 'pos': x1, 'desc': f'Tvärgående skarv vid X = {x1} mm'})
            for j in range(p_B1):
                y0 = j * s_wid
                y1 = min(B, (j + 1) * s_wid)
                if i == 0 and j < p_B1 - 1:
                    sms1.append({'type': 'Y', 'pos': y1, 'desc': f'Längsgående skarv vid Y = {y1} mm'})
                pcs1.append({'x': x0, 'y': y0, 'dx': x1 - x0, 'dy': y1 - y0})

        p_L2 = math.ceil(L / s_wid)
        p_B2 = math.ceil(B / s_len)
        tot2 = p_L2 * p_B2
        seams2 = (p_L2 - 1) + (p_B2 - 1)
        pcs2 = []
        sms2 = []
        for i in range(p_L2):
            x0 = i * s_wid
            x1 = min(L, (i + 1) * s_wid)
            if i < p_L2 - 1:
                sms2.append({'type': 'X', 'pos': x1, 'desc': f'Tvärgående skarv vid X = {x1} mm'})
            for j in range(p_B2):
                y0 = j * s_len
                y1 = min(B, (j + 1) * s_len)
                if i == 0 and j < p_B2 - 1:
                    sms2.append({'type': 'Y', 'pos': y1, 'desc': f'Längsgående skarv vid Y = {y1} mm'})
                pcs2.append({'x': x0, 'y': y0, 'dx': x1 - x0, 'dy': y1 - y0})

        if tot1 <= tot2:
            layouts.append({
                'sheets_needed': tot1,
                'seams': seams1,
                'layout_desc': f'Rutnät {p_L1}×{p_B1} bitar ({seams1} skarvar)',
                'cuts_desc': f'{tot1} st skivor fördelat på {p_L1} längs × {p_B1} djup',
                'pieces': pcs1,
                'seams_info': sms1,
            })
        else:
            layouts.append({
                'sheets_needed': tot2,
                'seams': seams2,
                'layout_desc': f'Rutnät {p_L2}×{p_B2} bitar ({seams2} skarvar)',
                'cuts_desc': f'{tot2} st skivor fördelat på {p_L2} längs × {p_B2} djup',
                'pieces': pcs2,
                'seams_info': sms2,
            })

    # Välj bästa layout för denna skiva: 1) Minst skarvar, 2) Minst antal skivor / lägst totalkostnad
    best_layout = min(layouts, key=lambda x: (x['seams'], x['sheets_needed']))

    sheets_cnt = best_layout['sheets_needed']
    total_cost = sheets_cnt * price
    total_bought_area = sheets_cnt * sheet_area_m2
    used_area = area_bench_m2
    waste_area = max(0.0, total_bought_area - used_area)
    waste_pct = (waste_area / total_bought_area * 100.0) if total_bought_area > 0 else 0.0

    used_cost = (used_area / total_bought_area) * total_cost if total_bought_area > 0 else total_cost
    waste_cost = max(0.0, total_cost - used_cost)

    return {
        'sheet': sheet,
        'name': sheet['name'],
        'material': sheet['material'],
        'thickness': sheet['thickness'],
        'sheet_dim': f"{sheet['length']} × {sheet['width']} mm",
        'sheets_needed': sheets_cnt,
        'seams': best_layout['seams'],
        'seam_label': '0 skarvar (Hel skiva)' if best_layout['seams'] == 0 else f"{best_layout['seams']} st skarv{'ar' if best_layout['seams'] > 1 else ''}",
        'piece_price': price,
        'total_cost': total_cost,
        'used_cost': used_cost,
        'waste_cost': waste_cost,
        'waste_pct': waste_pct,
        'layout_desc': best_layout['layout_desc'],
        'cuts_desc': best_layout['cuts_desc'],
        'pieces': best_layout.get('pieces', [{'x': 0, 'y': 0, 'dx': L, 'dy': B}]),
        'seams_info': best_layout.get('seams_info', []),
    }


def rank_tabletop_options(L: int, B: int, material_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Utvärderar alla bordsskivor och rangordnar dem efter:
      1) Minst antal skarvar (0 skarvar har högsta prioritet)
      2) Lägst inköpspris
      3) Lägst spill
    """
    catalog = TABLETOP_CATALOG
    if material_filter and material_filter != "Alla":
        catalog = [s for s in catalog if material_filter in s['material']]

    results = [calculate_tabletop_coverage(s, L, B) for s in catalog]
    ranked = sorted(results, key=lambda x: (x['seams'], x['total_cost'], x['waste_pct']))
    return ranked

SCREW_COST_FLAT: float = 150.0   # schablonkostnad fästelement, SEK


# ---------------------------------------------------------------------------
# Data-klasser
# ---------------------------------------------------------------------------

@dataclass
class CutPiece:
    """En enskild bräddel i kapnotan."""
    name: str
    quantity: int
    length_mm: int
    profile: str          # t.ex. "45×95 mm"
    width_mm: int         # t.ex. 95
    height_mm: int        # t.ex. 45 (tjocklek i Z-led för 3D)
    category: str         # "Ben" | "Sarg" | "Tvärslå"
    # 3D-placering (origo nedre vänstra hörn)
    positions: List[Tuple[float, float, float]] = field(default_factory=list)
    orientations: List[str] = field(default_factory=list)  # "X" | "Y" | "Z" (längdaxel)


@dataclass
class BenchGeometry:
    """Komplett geometri och kapnota."""
    # Indata
    L: int              # Ramens / underredets längd mm
    B: int              # Ramens / underredets djup mm
    H: int              # Total arbetshöjd mm (inkl skiva)
    overhang_kortsida: int = 0   # Överhäng kortsidor (gavlar, vä/hö) mm (X-led)
    overhang_längssida: int = 0  # Överhäng längssidor (fram/bak) mm (Y-led)
    lower_rail_h: int = 250      # Höjd underkant nedre sarg från golv mm
    n_pairs: int = 3             # Antal benpar
    leg_profile: str = "45×95 mm"
    frame_profile: str = "45×95 mm"
    tabletop_option: str = "Bänkskiva"
    tabletop_thickness_mm: Optional[int] = None
    tabletop_pieces: Optional[List[Dict[str, Any]]] = None
    tabletop_seams: Optional[List[Dict[str, Any]]] = None
    overhang_L: Optional[int] = None  # Legacy alias
    overhang_B: Optional[int] = None  # Legacy alias
    # Beräknat
    cuts: List[CutPiece] = field(default_factory=list)
    tabletop_area_m2: float = 0.0
    tabletop_L: int = 0
    tabletop_B: int = 0
    leg_spans: List[Dict[str, Any]] = field(default_factory=list)
    pair_xs: List[int] = field(default_factory=list)
    front_leg_y: float = 0.0
    back_leg_y: float = 0.0
    frame_y0: float = 0.0
    frame_y1: float = 0.0
    frame_x0: float = 0.0
    frame_x1: float = 0.0
    leg_width_x: float = 45.0

    def compute(self):
        """
        Beräknar alla delars mått och 3D-positioner.

        Konstruktionslogik (vy uppifrån):
        ┌─────────────── Sarg (Y=ry0→ry0+fp_w, full X-längd) ────────────────┐
        │  Tvärs │ Ben │                                  │ Ben │ Tvärs      │
        │(X=rx0) │     │                                  │     │(X=rx1-fp_w)│
        │        │     │                                  │     │            │
        │  Tvärs │ Ben │                                  │ Ben │ Tvärs      │
        └─────────────── Sarg (Y=ry1-fp_w→ry1, full X-längd) ───────────────┘

        Tvärslåar:  vid rx0 och rx1-fp_w (ytterändarna), löper i Y innanför sargerna
        Ben:        innanför gavel-tvärslåarnas innerkant i X, innanför sargernas innerkant i Y
        Mellantvärs: vid mellanbenens X-position (nedre nivå), löper hela djupet innanför sarger
        """
        # Hantera legacy alias
        ov_kortsida = self.overhang_kortsida
        ov_längssida = self.overhang_längssida
        if self.overhang_L is not None and ov_kortsida == 0:
            ov_kortsida = self.overhang_L
        if self.overhang_B is not None and ov_längssida == 0:
            ov_längssida = self.overhang_B

        self.cuts = []
        lp = self.leg_profile
        fp = self.frame_profile
        lp_w, lp_h = TIMBER_PROFILES[lp]   # lp_w=45 (X-led), lp_h=95 (Y-led)
        fp_w, fp_h = TIMBER_PROFILES[fp]   # fp_w=45 (sarg Y-tjocklek / tvärs X-tjocklek), fp_h=95 (Z-höjd)

        t_top = self.tabletop_thickness_mm if self.tabletop_thickness_mm is not None else TABLETOP_THICKNESS.get(self.tabletop_option, 16)

        # ---- Skivans totala mått (ram + överhäng på båda sidor) ----
        top_L = self.L + 2 * ov_kortsida   # X-led (längd)
        top_B = self.B + 2 * ov_längssida  # Y-led (djup/bredd)
        self.tabletop_L = top_L
        self.tabletop_B = top_B
        self.tabletop_area_m2 = (top_L / 1000.0) * (top_B / 1000.0)

        # ---- Längdmått för virke ----
        leg_length        = self.H - t_top
        long_rail_length  = self.L          # sarger är hela ramens längd
        cross_rail_length = self.B - 2 * fp_w  # tvärslåar mellan sargerna (i Y-led)

        n_legs      = 2 * self.n_pairs
        n_cross_rails = 2 * self.n_pairs

        # ---- Ramens ytterkoordinater (placerad innanför skivans överhäng) ----
        rx0 = ov_kortsida           # vänster gavel i X
        rx1 = ov_kortsida + self.L  # höger gavel i X
        ry0 = ov_längssida          # framkant sarg i Y
        ry1 = ov_längssida + self.B # bakkant sarg i Y

        # ---- Gavel-tvärslåarnas X-positioner ----
        # Vänster gavel: X = rx0  →  rx0+fp_w
        # Höger gavel:   X = rx1-fp_w  →  rx1
        left_tvärs_x  = rx0
        right_tvärs_x = rx1 - fp_w

        # ---- Ben-positioner i X ----
        # Benen sitter INNANFÖR gavel-tvärslåarnas innerkant:
        #   Vänster ben: X-start = rx0 + fp_w
        #   Höger  ben:  X-start = rx1 - fp_w - lp_w
        left_leg_x  = rx0 + fp_w
        right_leg_x = rx1 - fp_w - lp_w

        # Fördelning av benpar jämnt längs bänken
        if self.n_pairs == 2:
            pair_xs = [left_leg_x, right_leg_x]
        else:
            step = (right_leg_x - left_leg_x) / (self.n_pairs - 1)
            pair_xs = [left_leg_x + i * step for i in range(self.n_pairs)]

        pair_xs_int = [int(round(x)) for x in pair_xs]

        self.pair_xs = pair_xs_int
        self.leg_width_x = lp_w
        self.frame_y0 = ry0
        self.frame_y1 = ry1
        self.frame_x0 = rx0
        self.frame_x1 = rx1

        # Beräkna spännvidder/benavstånd mellan benparen
        spans = []
        for i in range(len(pair_xs_int) - 1):
            x_left_inner = pair_xs_int[i] + lp_w
            x_right_inner = pair_xs_int[i+1]
            span_free = x_right_inner - x_left_inner
            span_cc = pair_xs_int[i+1] - pair_xs_int[i]
            spans.append({
                "bay": i + 1,
                "x_start": x_left_inner,
                "x_end": x_right_inner,
                "x_mid": (x_left_inner + x_right_inner) / 2.0,
                "span_free_mm": span_free,
                "span_cc_mm": span_cc,
                "leg_left_x": pair_xs_int[i],
                "leg_right_x": pair_xs_int[i+1],
            })
        self.leg_spans = spans

        # ---- Ben-positioner i Y ----
        # Benen sitter INNANFÖR sargernas innerkant:
        #   Fram-ben: Y-start = ry0 + fp_w  (sarg-tjocklek innanför)
        #   Bak-ben:  Y-start = ry1 - fp_w - lp_h
        front_leg_y = ry0 + fp_w
        back_leg_y  = ry1 - fp_w - lp_h
        self.front_leg_y = front_leg_y
        self.back_leg_y = back_leg_y

        # ---- Z-nivåer ----
        upper_rail_z = leg_length - fp_h   # underkant övre sarg (topp=leg_length)
        lower_rail_z = self.lower_rail_h   # underkant nedre sarg

        # ---- Y-start för tvärslåar (innanför framsarg) ----
        cross_y0 = ry0 + fp_w   # = framsargens innerkant

        # ==================================================================
        # BEN
        # ==================================================================
        leg_positions = []
        for px in pair_xs_int:
            leg_positions.append((px, front_leg_y, 0))   # Fram-ben
            leg_positions.append((px, back_leg_y,  0))   # Bak-ben

        self.cuts.append(CutPiece(
            name="Ben", quantity=n_legs,
            length_mm=leg_length,
            profile=lp, width_mm=lp_w, height_mm=lp_h,
            category="Ben",
            positions=leg_positions,
            orientations=["Z"] * n_legs
        ))

        # ==================================================================
        # SARGER (löper i X, full ramens längd)
        # Sarg-profil: fp_w=45mm i Y, fp_h=95mm i Z
        # Framsarg:  Y = ry0  →  ry0+fp_w   (ytteryta vid ry0)
        # Baksarg:   Y = ry1-fp_w  →  ry1   (ytteryta vid ry1)
        # ==================================================================
        for nm, y0, z0 in [
            ("Främre övre sarg",  ry0,        upper_rail_z),
            ("Bakre övre sarg",   ry1 - fp_w, upper_rail_z),
            ("Främre nedre sarg", ry0,        lower_rail_z),
            ("Bakre nedre sarg",  ry1 - fp_w, lower_rail_z),
        ]:
            self.cuts.append(CutPiece(
                name=nm, quantity=1,
                length_mm=long_rail_length,
                profile=fp, width_mm=fp_w, height_mm=fp_h,
                category="Sarg",
                positions=[(rx0, y0, z0)],
                orientations=["X"]
            ))

        # ==================================================================
        # TVÄRSLÅAR (löper i Y, innanför sargerna)
        # Tvärs-profil: fp_w=45mm i X, fp_h=95mm i Z
        # Gavel vänster:  X = rx0         →  rx0+fp_w
        # Gavel höger:    X = rx1-fp_w    →  rx1
        # Mellanpar:      X = pair_xs_int[i]  (innanför sarg, löper hela djupet)
        # Y-start: ry0+fp_w (framsargens innerkant), Y-slut: ry0+fp_w+cross_rail_length
        # ==================================================================
        cross_pieces = []

        # Gavel vänster – övre och nedre
        for nm, z0 in [
            ("Vänster gavel – övre tvärslå", upper_rail_z),
            ("Vänster gavel – nedre tvärslå", lower_rail_z),
        ]:
            cross_pieces.append(CutPiece(
                name=nm, quantity=1,
                length_mm=cross_rail_length,
                profile=fp, width_mm=fp_w, height_mm=fp_h,
                category="Tvärslå",
                positions=[(left_tvärs_x, cross_y0, z0)],
                orientations=["Y"]
            ))

        # Gavel höger – övre och nedre
        for nm, z0 in [
            ("Höger gavel – övre tvärslå", upper_rail_z),
            ("Höger gavel – nedre tvärslå", lower_rail_z),
        ]:
            cross_pieces.append(CutPiece(
                name=nm, quantity=1,
                length_mm=cross_rail_length,
                profile=fp, width_mm=fp_w, height_mm=fp_h,
                category="Tvärslå",
                positions=[(right_tvärs_x, cross_y0, z0)],
                orientations=["Y"]
            ))

        # Mellanpar – övre och nedre tvärslå
        for idx in range(1, self.n_pairs - 1):
            px = pair_xs_int[idx]
            for nm_suffix, z0 in [
                ("övre tvärslå", upper_rail_z),
                ("nedre tvärslå", lower_rail_z),
            ]:
                cross_pieces.append(CutPiece(
                    name=f"Mellanpar {idx} – {nm_suffix}", quantity=1,
                    length_mm=cross_rail_length,
                    profile=fp, width_mm=fp_w, height_mm=fp_h,
                    category="Tvärslå",
                    positions=[(px, cross_y0, z0)],
                    orientations=["Y"]
                ))

        self.cuts.extend(cross_pieces)

        # Bänkskiva
        if self.tabletop_pieces and len(self.tabletop_pieces) > 1:
            for idx, p in enumerate(self.tabletop_pieces, 1):
                p_dx = int(p["dx"])
                p_dy = int(p["dy"])
                p_x = float(p["x"])
                p_y = float(p["y"])
                self.cuts.append(CutPiece(
                    name=f"Bänkskiva – Del #{idx} ({p_dx}×{p_dy} mm)",
                    quantity=1,
                    length_mm=p_dx,
                    profile=self.tabletop_option,
                    width_mm=p_dy,
                    height_mm=t_top,
                    category="Skiva",
                    positions=[(p_x, p_y, self.H - t_top)],
                    orientations=["X"]
                ))
        else:
            self.cuts.append(CutPiece(
                name="Bänkskiva (hel skiva)",
                quantity=1,
                length_mm=top_L,
                profile=self.tabletop_option,
                width_mm=top_B,
                height_mm=t_top,
                category="Skiva",
                positions=[(0, 0, self.H - t_top)],
                orientations=["X"]
            ))


# ---------------------------------------------------------------------------
# Kostnadskalkyl
# ---------------------------------------------------------------------------

def compute_cost(
    geometry: BenchGeometry,
    leg_price: float,
    frame_price: float,
    tabletop_price: float,
    screw_cost: float,
    purchase_plan: dict,   # output from optimization
    tabletop_plan: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Returnerar komplett kostnadsspecifikation med både:
      1) Inköpt material (vad man betalar i butik för hela reglar/skivor)
      2) Faktiskt använt material (det effektiva virket/ytan som sitter i bänken)
      3) Spillkostnad (skillnaden)
    """
    is_combined = purchase_plan.get("is_combined", False)

    if tabletop_plan:
        top_bought = float(tabletop_plan.get("total_cost", 0.0))
        top_used   = float(tabletop_plan.get("used_cost", top_bought))
        top_waste  = float(tabletop_plan.get("waste_cost", 0.0))
        top_name   = tabletop_plan.get("name", geometry.tabletop_option)
    else:
        top_bought = float(geometry.tabletop_area_m2 * tabletop_price)
        top_used   = top_bought
        top_waste  = 0.0
        top_name   = geometry.tabletop_option

    if is_combined:
        timber_bought = float(purchase_plan.get("timber_total_cost", 0.0))
        timber_used   = float(purchase_plan.get("timber_used_cost", timber_bought))
        timber_waste  = max(0.0, timber_bought - timber_used)
        timber_prof   = purchase_plan.get("timber_profile", geometry.leg_profile)

        leg_bought = float(purchase_plan.get("leg_total_cost", 0.0))
        frame_bought = float(purchase_plan.get("frame_total_cost", 0.0))

        total_bought = timber_bought + top_bought + screw_cost
        total_used   = timber_used + top_used + screw_cost
        total_waste  = timber_waste + top_waste

        items = [
            {
                "Post": f"Virke – Ben, Sarger & Tvärslåar ({timber_prof})",
                "Inköpt material (kr)": timber_bought,
                "Faktiskt använt (kr)": timber_used,
                "Spillkostnad (kr)": timber_waste,
            },
            {
                "Post": f"Bänkskiva ({top_name})",
                "Inköpt material (kr)": top_bought,
                "Faktiskt använt (kr)": top_used,
                "Spillkostnad (kr)": top_waste,
            },
            {
                "Post": "Fästelement (schablon)",
                "Inköpt material (kr)": screw_cost,
                "Faktiskt använt (kr)": screw_cost,
                "Spillkostnad (kr)": 0.0,
            },
        ]
    else:
        leg_bought = float(purchase_plan.get("leg_total_cost", 0.0))
        leg_used   = float(purchase_plan.get("leg_used_cost", leg_bought))
        leg_waste  = max(0.0, leg_bought - leg_used)

        frame_bought = float(purchase_plan.get("frame_total_cost", 0.0))
        frame_used   = float(purchase_plan.get("frame_used_cost", frame_bought))
        frame_waste  = max(0.0, frame_bought - frame_used)

        total_bought = leg_bought + frame_bought + top_bought + screw_cost
        total_used   = leg_used + frame_used + top_used + screw_cost
        total_waste  = leg_waste + frame_waste + top_waste

        items = [
            {
                "Post": "Virke – Ben",
                "Inköpt material (kr)": leg_bought,
                "Faktiskt använt (kr)": leg_used,
                "Spillkostnad (kr)": leg_waste,
            },
            {
                "Post": "Virke – Sarger/Tvärslåar",
                "Inköpt material (kr)": frame_bought,
                "Faktiskt använt (kr)": frame_used,
                "Spillkostnad (kr)": frame_waste,
            },
            {
                "Post": f"Bänkskiva ({top_name})",
                "Inköpt material (kr)": top_bought,
                "Faktiskt använt (kr)": top_used,
                "Spillkostnad (kr)": top_waste,
            },
            {
                "Post": "Fästelement (schablon)",
                "Inköpt material (kr)": screw_cost,
                "Faktiskt använt (kr)": screw_cost,
                "Spillkostnad (kr)": 0.0,
            },
        ]

    return {
        # Detaljerad tabell
        "items": items,
        "total_bought": total_bought,
        "total_used": total_used,
        "total_waste": total_waste,

        # Nycklar för bakåtkompatibilitet
        "Totalt": total_bought,
        "Totalt_använt": total_used,
        "Totalt_spill": total_waste,
        "Virke – Ben": leg_bought,
        "Virke – Sarger/Tvärslåar": frame_bought,
        "Bänkskiva": top_bought,
        "Bänkskiva_använt": top_used,
        "Bänkskiva_spill": top_waste,
        "Fästelement (schablon)": screw_cost,
    }
