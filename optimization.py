"""
optimization.py – 1D kap- och inköpsoptimering (bin-packing) mot tillgängliga handelslängder.
Optimerar mot det faktiska virkesutbudet och priserna hos bygghandeln (jem & fix).
"""
from __future__ import annotations
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
import copy

import numpy as np
try:
    from scipy.optimize import milp, LinearConstraint
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

from calculations import STORE_CATALOG, DEFAULT_TIMBER_PRICES

DEFAULT_SAW_KERF_MM = 5   # standard sågspår/kapförlust per snitt (mm)


@dataclass
class StockPiece:
    """En inköpt regel med dess kapade delar."""
    stock_length: int
    cuts: List[Tuple[str, int]] = field(default_factory=list)  # (namn, längd_mm)
    remaining: int = 0
    saw_kerf: int = DEFAULT_SAW_KERF_MM

    def __post_init__(self):
        self.remaining = self.stock_length

    def can_fit(self, length: int) -> bool:
        # Kräver längd + sågspår för att få plats om det inte är första snittet
        needed = length + self.saw_kerf if self.cuts else length
        return self.remaining >= needed

    def add_cut(self, name: str, length: int):
        cost = length + self.saw_kerf if self.cuts else length
        self.cuts.append((name, length))
        self.remaining -= cost


def _first_fit_decreasing(items: List[Tuple[str, int]], stock_len: int, saw_kerf: int = DEFAULT_SAW_KERF_MM) -> List[StockPiece]:
    """FFD (First Fit Decreasing) bin-packing algoritm."""
    # Sortera fallande efter längd
    sorted_items = sorted(items, key=lambda x: x[1], reverse=True)
    bins: List[StockPiece] = []

    for name, length in sorted_items:
        placed = False
        for b in bins:
            if b.can_fit(length):
                b.add_cut(name, length)
                placed = True
                break
        if not placed:
            new_bin = StockPiece(stock_length=stock_len, saw_kerf=saw_kerf)
            new_bin.add_cut(name, length)
            bins.append(new_bin)
    return bins


def evaluate_stock_option(
    items: List[Tuple[str, int]],
    option: Dict[str, Any],
    profile: str,
    price_per_m_override: Optional[float] = None,
    saw_kerf: int = DEFAULT_SAW_KERF_MM,
) -> Optional[Dict[str, Any]]:
    """
    Utvärderar ett specifikt handelslängds-alternativ för en lista av delar.
    Returnerar None om någon del är för lång för denna regel.
    """
    stock_len = option["length_mm"]
    max_item_len = max(length for _, length in items) if items else 0

    if max_item_len > stock_len:
        # Delen får inte plats på denna regellängd
        return None

    bins = _first_fit_decreasing(items, stock_len, saw_kerf=saw_kerf)
    n_pieces = len(bins)
    total_bought_mm = n_pieces * stock_len
    total_used_mm = sum(length for _, length in items)
    waste_mm = max(0, total_bought_mm - total_used_mm)
    waste_pct = (waste_mm / total_bought_mm * 100.0) if total_bought_mm > 0 else 0.0

    # Prisberäkning: använd butikens exakta styckpris från katalogen
    # Om användaren aktivt angett ett eget meterpris som avviker från standardpriset, beräkna utifrån det
    default_m_price = DEFAULT_TIMBER_PRICES.get(profile, option.get("price_per_m", 0.0))
    is_user_custom = (
        price_per_m_override is not None and
        abs(price_per_m_override - default_m_price) > 0.01
    )

    if is_user_custom:
        piece_price = round(price_per_m_override * (stock_len / 1000.0), 2)
    else:
        piece_price = option["price"]

    total_cost = n_pieces * piece_price
    total_lpm = n_pieces * (stock_len / 1000.0)
    used_lpm = total_used_mm / 1000.0
    used_cost = (total_used_mm / total_bought_mm) * total_cost if total_bought_mm > 0 else 0.0
    waste_cost = max(0.0, total_cost - used_cost)

    return {
        "name": option["name"],
        "stock_length": stock_len,
        "piece_price": piece_price,
        "n_pieces": n_pieces,
        "total_cost": total_cost,
        "total_lpm": total_lpm,
        "used_lpm": used_lpm,
        "used_cost": used_cost,
        "waste_cost": waste_cost,
        "waste_pct": waste_pct,
        "waste_mm": waste_mm,
        "bins": bins,
        "fits": True,
    }


def _solve_vsbpp_milp(
    items: List[Tuple[str, int]],
    catalog: List[Dict[str, Any]],
    price_per_m_override: Optional[float] = None,
    saw_kerf: int = DEFAULT_SAW_KERF_MM,
) -> Optional[Dict[str, Any]]:
    """
    Löser Variable Size Bin Packing Problem (VSBPP) med Mixed Integer Linear Programming (MILP).
    Pusslar fritt bland alla tillgängliga handelslängder i katalogen för att hitta den exakta
    kombination av regellängder som ger lägst inköpskostnad och minsta möjliga virkesspill.
    """
    if not items or not HAS_SCIPY:
        return None

    sorted_items = sorted(items, key=lambda x: x[1], reverse=True)
    m = len(sorted_items)
    max_item_len = sorted_items[0][1]

    valid_catalog = [opt for opt in catalog if opt["length_mm"] >= max_item_len]
    if not valid_catalog:
        return None

    # Beräkna styckpris för varje längdalternativ
    opt_prices: Dict[int, float] = {}
    for opt in valid_catalog:
        s_len = opt["length_mm"]
        if price_per_m_override is not None:
            opt_prices[s_len] = round(price_per_m_override * (s_len / 1000.0), 2)
        else:
            opt_prices[s_len] = opt["price"]

    # Generera alla icke-dominerade kapmönster (patterns) för varje handelslängd
    patterns: List[Tuple[Dict[str, Any], List[int], float, int]] = []
    for opt in valid_catalog:
        s_len = opt["length_mm"]
        cost = opt_prices[s_len]

        def dfs(idx: int, cur_cuts: List[int], cur_rem: int):
            added = False
            for i in range(idx, m):
                l = sorted_items[i][1]
                needed = l + saw_kerf if cur_cuts else l
                if cur_rem >= needed:
                    dfs(i + 1, cur_cuts + [i], cur_rem - needed)
                    added = True
            if not added and cur_cuts:
                patterns.append((opt, cur_cuts, cost, cur_rem))

        dfs(0, [], s_len)

    P = len(patterns)
    if P == 0:
        return None

    c = np.zeros(P)
    A = np.zeros((m, P))

    for j, (opt, cuts, cost, rem) in enumerate(patterns):
        # Målfunktion: minimera inköpskostnad. Mycket liten vikt på spill för att bryta likalägen
        c[j] = cost + 0.0001 * rem
        for i in cuts:
            A[i, j] = 1.0

    # Exakt partition: varje bit i kaplistan ska kapas exakt en gång (A x == 1)
    constraints = LinearConstraint(A, lb=np.ones(m), ub=np.ones(m))
    integrality = np.ones(P)

    milp_res = milp(c=c, constraints=constraints, integrality=integrality)
    if not milp_res.success:
        return None

    x = np.round(milp_res.x).astype(int)
    bins: List[StockPiece] = []
    total_cost = 0.0
    total_bought_mm = 0
    total_used_mm = sum(l for _, l in sorted_items)
    board_counts: Dict[str, Dict[str, Any]] = {}

    for j, cnt in enumerate(x):
        if cnt > 0:
            opt, cuts, cost, rem = patterns[j]
            for _ in range(cnt):
                b = StockPiece(stock_length=opt["length_mm"], saw_kerf=saw_kerf)
                for i in cuts:
                    b.add_cut(sorted_items[i][0], sorted_items[i][1])
                bins.append(b)
                total_cost += cost
                total_bought_mm += opt["length_mm"]

                b_name = opt["name"]
                if b_name not in board_counts:
                    board_counts[b_name] = {
                        "name": b_name,
                        "length_mm": opt["length_mm"],
                        "piece_price": cost,
                        "count": 0,
                        "total_cost": 0.0,
                    }
                board_counts[b_name]["count"] += 1
                board_counts[b_name]["total_cost"] += cost

    # Sortera reglar med längst först
    bins.sort(key=lambda b: (b.stock_length, -len(b.cuts)), reverse=True)

    waste_mm = max(0, total_bought_mm - total_used_mm)
    waste_pct = (waste_mm / total_bought_mm * 100.0) if total_bought_mm > 0 else 0.0
    used_cost = (total_used_mm / total_bought_mm) * total_cost if total_bought_mm > 0 else total_cost
    waste_cost = max(0.0, total_cost - used_cost)

    summary_list = sorted(board_counts.values(), key=lambda b: b["length_mm"], reverse=True)
    desc_parts = [f"{b['count']} st à {b['length_mm']/1000:.1f} m" for b in summary_list]
    board_summary_str = ", ".join(desc_parts)
    is_mixed = len(summary_list) > 1

    return {
        "bins": bins,
        "total_cost": total_cost,
        "total_bought_mm": total_bought_mm,
        "total_used_mm": total_used_mm,
        "waste_mm": waste_mm,
        "waste_pct": waste_pct,
        "total_lpm": total_bought_mm / 1000.0,
        "used_lpm": total_used_mm / 1000.0,
        "used_cost": used_cost,
        "waste_cost": waste_cost,
        "n_pieces": len(bins),
        "board_summary": summary_list,
        "board_summary_str": board_summary_str,
        "is_mixed": is_mixed,
        "article_name": f"Optimal mix ({board_summary_str})" if is_mixed else summary_list[0]["name"],
        "stock_length": 0 if is_mixed else summary_list[0]["length_mm"],
        "piece_price": 0.0 if is_mixed else summary_list[0]["piece_price"],
        "fits": True,
    }


def optimize_profile_cuts(
    items: List[Tuple[str, int]],
    profile: str,
    price_per_m_override: Optional[float] = None,
    preferred_length_mm: Optional[int] = None,
    saw_kerf: int = DEFAULT_SAW_KERF_MM,
) -> Dict[str, Any]:
    """
    Optimerar inköp för en uppsättning reglar av en specifik profil.
    Pusslar och optimerar fritt bland butikens handelslängder för att minimera totalkostnad och virkesspill.
    """
    catalog = STORE_CATALOG.get(profile, [
        {"name": f"Regel {profile} 3,0 m", "length_mm": 3000, "price": 90.0, "price_per_m": 30.0},
        {"name": f"Regel {profile} 3,6 m", "length_mm": 3600, "price": 110.0, "price_per_m": 30.0},
        {"name": f"Regel {profile} 4,2 m", "length_mm": 4200, "price": 130.0, "price_per_m": 30.0},
    ])

    if not items:
        return {
            "profile": profile,
            "article_name": "-",
            "stock_length": 0,
            "piece_price": 0.0,
            "n_pieces": 0,
            "total_cost": 0.0,
            "total_lpm": 0.0,
            "used_lpm": 0.0,
            "used_cost": 0.0,
            "waste_cost": 0.0,
            "waste_pct": 0.0,
            "waste_mm": 0,
            "bins": [],
            "board_summary": [],
            "board_summary_str": "-",
            "warning": None,
            "available_catalog": catalog,
            "comparison": [],
        }

    max_item_len = max(length for _, length in items)
    max_catalog_len = max(opt["length_mm"] for opt in catalog)
    warning = None

    if max_item_len > max_catalog_len:
        warning = (
            f"OBS: Längsta biten är {max_item_len} mm, vilket är längre än den "
            f"längsta tillgängliga regeln i butiken ({max_catalog_len} mm för {profile}). "
            f"Sarger behöver skarvas eller så måste bänklängden minskas."
        )

    # 1. Utvärdera alla enkellängds-alternativ i butiken (för jämförelsetabellen)
    valid_single_results: List[Dict[str, Any]] = []
    single_comparison: List[Dict[str, Any]] = []

    for opt in catalog:
        eval_res = evaluate_stock_option(items, opt, profile, price_per_m_override, saw_kerf=saw_kerf)
        if eval_res is not None:
            valid_single_results.append(eval_res)
            single_comparison.append({
                "Längd": f"{opt['length_mm']/1000:.1f} m ({opt['length_mm']} mm)",
                "Artikel": opt["name"],
                "Styckpris": eval_res["piece_price"],
                "Antal som krävs": eval_res["n_pieces"],
                "Totalkostnad": eval_res["total_cost"],
                "Spill": eval_res["waste_pct"],
                "Status": "Möjlig",
                "length_mm": opt["length_mm"],
                "res": eval_res,
            })
        else:
            single_comparison.append({
                "Längd": f"{opt['length_mm']/1000:.1f} m ({opt['length_mm']} mm)",
                "Artikel": opt["name"],
                "Styckpris": opt["price"],
                "Antal som krävs": None,
                "Totalkostnad": None,
                "Spill": None,
                "Status": f"För kort (max bit: {max_item_len} mm)",
                "length_mm": opt["length_mm"],
                "res": None,
            })

    # 2. Utvärdera optimal mix av blandade längder (VSBPP / Cutting Stock)
    multi_res = None
    if not preferred_length_mm:
        try:
            multi_res = _solve_vsbpp_milp(items, catalog, price_per_m_override, saw_kerf=saw_kerf)
        except Exception:
            multi_res = None

    # 3. Välj bästa alternativ
    chosen = None
    comparison_table: List[Dict[str, Any]] = []

    best_single = min(valid_single_results, key=lambda x: (x["total_cost"], x["waste_pct"])) if valid_single_results else None

    # Om optimal mix är blandad och ger minst lika bra kostnad/spill som bästa enkellängd
    if multi_res and multi_res.get("is_mixed") and (not best_single or multi_res["total_cost"] <= best_single["total_cost"] + 0.01):
        chosen = multi_res
        comparison_table.append({
            "Längd": "Optimal mix (blandade reglar)",
            "Artikel": f"👉 {multi_res['board_summary_str']}",
            "Styckpris": None,
            "Antal som krävs": multi_res["n_pieces"],
            "Totalkostnad": multi_res["total_cost"],
            "Spill": multi_res["waste_pct"],
            "Status": "Vald",
            "length_mm": 0,
        })
        for r in single_comparison:
            row_copy = dict(r)
            row_copy.pop("res", None)
            comparison_table.append(row_copy)
    elif preferred_length_mm:
        # Om användaren uttryckligen valt en längd
        for res in valid_single_results:
            if res["stock_length"] == preferred_length_mm:
                chosen = res
                break
        if not chosen and valid_single_results:
            chosen = best_single
        for r in single_comparison:
            row_copy = dict(r)
            res_obj = row_copy.pop("res", None)
            if res_obj and chosen and res_obj["stock_length"] == chosen.get("stock_length"):
                row_copy["Status"] = "Vald"
                row_copy["Artikel"] = f"👉 {row_copy['Artikel']}"
            comparison_table.append(row_copy)
    else:
        chosen = best_single or multi_res
        for r in single_comparison:
            row_copy = dict(r)
            res_obj = row_copy.pop("res", None)
            if res_obj and chosen and res_obj.get("stock_length") == chosen.get("stock_length"):
                row_copy["Status"] = "Vald"
                row_copy["Artikel"] = f"👉 {row_copy['Artikel']}"
            comparison_table.append(row_copy)

    if not chosen:
        # Fallback om ingen längd räckte till (t.ex. vid överlång bit)
        longest_opt = max(catalog, key=lambda x: x["length_mm"])
        fallback_bins = _first_fit_decreasing(items, longest_opt["length_mm"], saw_kerf=saw_kerf)
        n_p = len(fallback_bins)
        p_price = longest_opt["price"]
        chosen = {
            "name": longest_opt["name"],
            "stock_length": longest_opt["length_mm"],
            "piece_price": p_price,
            "n_pieces": n_p,
            "total_cost": n_p * p_price,
            "total_lpm": n_p * longest_opt["length_mm"] / 1000.0,
            "used_lpm": sum(length for _, length in items) / 1000.0,
            "used_cost": n_p * p_price,
            "waste_cost": 0.0,
            "waste_pct": 0.0,
            "waste_mm": 0,
            "bins": fallback_bins,
            "board_summary": [{
                "name": longest_opt["name"],
                "length_mm": longest_opt["length_mm"],
                "piece_price": p_price,
                "count": n_p,
                "total_cost": n_p * p_price,
            }],
            "board_summary_str": f"{n_p} st à {longest_opt['length_mm']/1000:.1f} m",
            "fits": False,
        }

    art_name = chosen.get("article_name", chosen.get("name", "Virke"))

    return {
        "profile": profile,
        "article_name": art_name,
        "stock_length": chosen.get("stock_length", 0),
        "piece_price": chosen.get("piece_price", 0.0),
        "n_pieces": chosen["n_pieces"],
        "total_cost": chosen["total_cost"],
        "total_lpm": chosen["total_lpm"],
        "used_lpm": chosen.get("used_lpm", chosen["total_lpm"]),
        "used_cost": chosen.get("used_cost", chosen["total_cost"]),
        "waste_cost": chosen.get("waste_cost", 0.0),
        "waste_pct": chosen["waste_pct"],
        "waste_mm": chosen["waste_mm"],
        "bins": chosen["bins"],
        "board_summary": chosen.get("board_summary", []),
        "board_summary_str": chosen.get("board_summary_str", ""),
        "warning": warning,
        "available_catalog": catalog,
        "comparison": comparison_table,
    }


def run_optimization(
    cuts,
    leg_price_per_m: float,
    frame_price_per_m: float,
    leg_profile: str = "45×95 mm",
    frame_profile: str = "45×95 mm",
    pref_leg_length_mm: Optional[int] = None,
    pref_frame_length_mm: Optional[int] = None,
    saw_kerf_mm: int = DEFAULT_SAW_KERF_MM,
) -> Dict[str, Any]:
    """
    Kör optimering mot bygghandelns sortiment.
    Om ben och sarger/tvärslåar har samma dimension optimeras de tillsammans
    på samma reglar för att minimera spill och totalkostnad.
    Om de har olika dimensioner optimeras de separat per profil.
    """
    same_profile = (leg_profile == frame_profile)

    if same_profile:
        timber_items: List[Tuple[str, int]] = []
        leg_items: List[Tuple[str, int]] = []
        frame_items: List[Tuple[str, int]] = []

        for cut in cuts:
            if cut.category == "Skiva":
                continue
            item_list = [(f"{cut.name} #{i+1}" if cut.quantity > 1 else cut.name, cut.length_mm) for i in range(cut.quantity)]
            timber_items.extend(item_list)
            if cut.category == "Ben":
                leg_items.extend(item_list)
            else:
                frame_items.extend(item_list)

        timber_res = optimize_profile_cuts(
            timber_items,
            profile=leg_profile,
            price_per_m_override=leg_price_per_m,
            preferred_length_mm=pref_leg_length_mm or pref_frame_length_mm,
            saw_kerf=saw_kerf_mm,
        )

        total_used_mm = sum(l for _, l in timber_items)
        leg_used_mm = sum(l for _, l in leg_items)
        frame_used_mm = sum(l for _, l in frame_items)

        leg_ratio = (leg_used_mm / total_used_mm) if total_used_mm > 0 else 0.5
        frame_ratio = (frame_used_mm / total_used_mm) if total_used_mm > 0 else 0.5

        leg_used_cost = timber_res["used_cost"] * leg_ratio
        frame_used_cost = timber_res["used_cost"] * frame_ratio
        leg_waste_cost = timber_res["waste_cost"] * leg_ratio
        frame_waste_cost = timber_res["waste_cost"] * frame_ratio
        leg_total_cost = timber_res["total_cost"] * leg_ratio
        frame_total_cost = timber_res["total_cost"] * frame_ratio

        return {
            "is_combined": True,
            "same_profile": True,

            # Gemensamt virke (används när ben och sarger har samma dimension)
            "timber_profile": leg_profile,
            "timber_article_name": timber_res["article_name"],
            "timber_stock_length": timber_res["stock_length"],
            "timber_piece_price": timber_res["piece_price"],
            "timber_n_pieces": timber_res["n_pieces"],
            "timber_bins": timber_res["bins"],
            "timber_waste_pct": timber_res["waste_pct"],
            "timber_waste_mm": timber_res["waste_mm"],
            "timber_total_lpm": timber_res["total_lpm"],
            "timber_total_cost": timber_res["total_cost"],
            "timber_used_lpm": timber_res["used_lpm"],
            "timber_used_cost": timber_res["used_cost"],
            "timber_waste_cost": timber_res["waste_cost"],
            "timber_warning": timber_res["warning"],
            "timber_comparison": timber_res["comparison"],
            "timber_catalog": timber_res["available_catalog"],
            "timber_board_summary": timber_res.get("board_summary", []),
            "timber_board_summary_str": timber_res.get("board_summary_str", ""),

            # Bakåtkompatibilitet för funktioner som läser leg_ och frame_
            "leg_profile": leg_profile,
            "leg_article_name": timber_res["article_name"],
            "leg_stock_length": timber_res["stock_length"],
            "leg_piece_price": timber_res["piece_price"],
            "leg_n_pieces": timber_res["n_pieces"],
            "leg_bins": timber_res["bins"],
            "leg_waste_pct": timber_res["waste_pct"],
            "leg_waste_mm": timber_res["waste_mm"],
            "leg_total_lpm": timber_res["total_lpm"],
            "leg_total_cost": leg_total_cost,
            "leg_used_lpm": timber_res["used_lpm"] * leg_ratio,
            "leg_used_cost": leg_used_cost,
            "leg_waste_cost": leg_waste_cost,
            "leg_warning": timber_res["warning"],
            "leg_comparison": timber_res["comparison"],
            "leg_catalog": timber_res["available_catalog"],
            "leg_board_summary": timber_res.get("board_summary", []),
            "leg_board_summary_str": timber_res.get("board_summary_str", ""),

            "frame_profile": frame_profile,
            "frame_article_name": timber_res["article_name"],
            "frame_stock_length": timber_res["stock_length"],
            "frame_piece_price": timber_res["piece_price"],
            "frame_n_pieces": timber_res["n_pieces"],
            "frame_bins": timber_res["bins"],
            "frame_waste_pct": timber_res["waste_pct"],
            "frame_waste_mm": timber_res["waste_mm"],
            "frame_total_lpm": timber_res["total_lpm"],
            "frame_total_cost": frame_total_cost,
            "frame_used_lpm": timber_res["used_lpm"] * frame_ratio,
            "frame_used_cost": frame_used_cost,
            "frame_waste_cost": frame_waste_cost,
            "frame_warning": timber_res["warning"],
            "frame_comparison": timber_res["comparison"],
            "frame_catalog": timber_res["available_catalog"],
            "frame_board_summary": timber_res.get("board_summary", []),
            "frame_board_summary_str": timber_res.get("board_summary_str", ""),

            # Totalt
            "total_lpm": timber_res["total_lpm"],
            "total_used_lpm": timber_res["used_lpm"],
            "timber_total_cost": timber_res["total_cost"],
            "timber_used_cost": timber_res["used_cost"],
            "timber_waste_cost": timber_res["waste_cost"],
            "avg_waste_pct": timber_res["waste_pct"],
            "total_waste_mm": timber_res["waste_mm"],
        }
    else:
        # Olika dimensioner -> optimera separat
        leg_items: List[Tuple[str, int]] = []
        frame_items: List[Tuple[str, int]] = []

        for cut in cuts:
            if cut.category == "Skiva":
                continue
            item_list = [(f"{cut.name} #{i+1}" if cut.quantity > 1 else cut.name, cut.length_mm) for i in range(cut.quantity)]
            if cut.category == "Ben":
                leg_items.extend(item_list)
            else:
                frame_items.extend(item_list)

        leg_res = optimize_profile_cuts(
            leg_items,
            profile=leg_profile,
            price_per_m_override=leg_price_per_m,
            preferred_length_mm=pref_leg_length_mm,
            saw_kerf=saw_kerf_mm,
        )

        frame_res = optimize_profile_cuts(
            frame_items,
            profile=frame_profile,
            price_per_m_override=frame_price_per_m,
            preferred_length_mm=pref_frame_length_mm,
            saw_kerf=saw_kerf_mm,
        )

        total_lpm = leg_res["total_lpm"] + frame_res["total_lpm"]
        total_used_lpm = leg_res["used_lpm"] + frame_res["used_lpm"]
        total_cost = leg_res["total_cost"] + frame_res["total_cost"]

        total_bought_mm = (leg_res["n_pieces"] * leg_res["stock_length"]) + (frame_res["n_pieces"] * frame_res["stock_length"])
        total_waste_mm = leg_res["waste_mm"] + frame_res["waste_mm"]
        avg_waste_pct = (total_waste_mm / total_bought_mm * 100.0) if total_bought_mm > 0 else 0.0

        return {
            "is_combined": False,
            "same_profile": False,

            # Ben
            "leg_profile": leg_profile,
            "leg_article_name": leg_res["article_name"],
            "leg_stock_length": leg_res["stock_length"],
            "leg_piece_price": leg_res["piece_price"],
            "leg_n_pieces": leg_res["n_pieces"],
            "leg_bins": leg_res["bins"],
            "leg_waste_pct": leg_res["waste_pct"],
            "leg_waste_mm": leg_res["waste_mm"],
            "leg_total_lpm": leg_res["total_lpm"],
            "leg_total_cost": leg_res["total_cost"],
            "leg_used_lpm": leg_res["used_lpm"],
            "leg_used_cost": leg_res["used_cost"],
            "leg_waste_cost": leg_res["waste_cost"],
            "leg_warning": leg_res["warning"],
            "leg_comparison": leg_res["comparison"],
            "leg_catalog": leg_res["available_catalog"],
            "leg_board_summary": leg_res.get("board_summary", []),
            "leg_board_summary_str": leg_res.get("board_summary_str", ""),

            # Sarger & tvärslåar
            "frame_profile": frame_profile,
            "frame_article_name": frame_res["article_name"],
            "frame_stock_length": frame_res["stock_length"],
            "frame_piece_price": frame_res["piece_price"],
            "frame_n_pieces": frame_res["n_pieces"],
            "frame_bins": frame_res["bins"],
            "frame_waste_pct": frame_res["waste_pct"],
            "frame_waste_mm": frame_res["waste_mm"],
            "frame_total_lpm": frame_res["total_lpm"],
            "frame_total_cost": frame_res["total_cost"],
            "frame_used_lpm": frame_res["used_lpm"],
            "frame_used_cost": frame_res["used_cost"],
            "frame_waste_cost": frame_res["waste_cost"],
            "frame_warning": frame_res["warning"],
            "frame_comparison": frame_res["comparison"],
            "frame_catalog": frame_res["available_catalog"],
            "frame_board_summary": frame_res.get("board_summary", []),
            "frame_board_summary_str": frame_res.get("board_summary_str", ""),

            # Totalt
            "total_lpm": total_lpm,
            "total_used_lpm": total_used_lpm,
            "timber_total_cost": total_cost,
            "timber_used_cost": leg_res["used_cost"] + frame_res["used_cost"],
            "timber_waste_cost": leg_res["waste_cost"] + frame_res["waste_cost"],
            "avg_waste_pct": avg_waste_pct,
            "total_waste_mm": total_waste_mm,
        }
