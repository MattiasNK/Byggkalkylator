"""
visualization.py – Interaktiv Plotly 3D-visualisering av arbetsbänk.

Koordinatsystem:
  X = längsriktning  (0 → L)
  Y = djupriktning   (0 → B)
  Z = höjdriktning   (0 → H)

Profil-konvention (45×95 mm) → (w=45, h=95):
  Ben   (orient Z): dx=w=45, dy=h=95, dz=leg_length   (45mm i X, 95mm i Y)
  Sarg  (orient X): dx=length, dy=w=45, dz=h=95       (smal i Y, hög i Z)
  Tvärs (orient Y): dx=w=45, dy=length, dz=h=95       (smal i X, hög i Z)
  Skiva (orient X): dx=L, dy=B, dz=t_top              (flat platta)
"""
from __future__ import annotations
from typing import List, Optional, Tuple, Any
import plotly.graph_objects as go

CATEGORY_COLORS = {
    "Ben":     "#C88A38",
    "Sarg":    "#72A852",
    "Tvärslå": "#5090BB",
    "Skiva":   "#C8A46A",
}
HIGHLIGHT_COLOR = "#FF3333"


def _solid_box(x0: float, y0: float, z0: float,
               dx: float, dy: float, dz: float,
               color: str, name: str, hover_text: str,
               opacity: float = 1.0) -> go.Mesh3d:
    """
    Skapar ett solid 3D-rätblock med Plotly Mesh3d.
    Använder alphahull=0 (konvex hölje) – garanterat korrekt för rätblock.
    """
    x1, y1, z1 = x0 + dx, y0 + dy, z0 + dz

    vx = [x0, x1, x1, x0, x0, x1, x1, x0]
    vy = [y0, y0, y1, y1, y0, y0, y1, y1]
    vz = [z0, z0, z0, z0, z1, z1, z1, z1]

    return go.Mesh3d(
        x=vx, y=vy, z=vz,
        alphahull=0,
        color=color,
        opacity=opacity,
        name=name,
        hovertext=hover_text,
        hoverinfo="text",
        flatshading=True,
        lighting=dict(
            ambient=0.55,
            diffuse=0.88,
            specular=0.12,
            roughness=0.85,
        ),
        lightposition=dict(x=2000, y=-1500, z=5000),
        showlegend=True,
    )


def _get_box_edges(x0: float, y0: float, z0: float,
                   dx: float, dy: float, dz: float) -> Tuple[List[Any], List[Any], List[Any]]:
    """
    Genererar koordinaterna för ett 3D-rätblocks 12 kanter.
    Returnerar (xs, ys, zs) med None som separator mellan linjesegment.
    """
    x1, y1, z1 = x0 + dx, y0 + dy, z0 + dz

    # 12 kanter: botten (4), topp (4), vertikala pelare (4)
    xs = [
        x0, x1, x1, x0, x0, None,  # botten
        x0, x1, x1, x0, x0, None,  # topp
        x0, x0, None,              # pelare fram-vänster
        x1, x1, None,              # pelare fram-höger
        x1, x1, None,              # pelare bak-höger
        x0, x0, None,              # pelare bak-vänster
    ]
    ys = [
        y0, y0, y1, y1, y0, None,
        y0, y0, y1, y1, y0, None,
        y0, y0, None,
        y0, y0, None,
        y1, y1, None,
        y1, y1, None,
    ]
    zs = [
        z0, z0, z0, z0, z0, None,
        z1, z1, z1, z1, z1, None,
        z0, z1, None,
        z0, z1, None,
        z0, z1, None,
        z0, z1, None,
    ]
    return xs, ys, zs


def _piece_to_traces(
    cut,
    highlight_names: Optional[set],
    show_tabletop: bool
) -> Tuple[List[go.Mesh3d], List[Tuple[float, float, float, float, float, float, bool]]]:
    """Omvandlar ett CutPiece till Plotly-traces och returnerar boxgeometrier för konturer."""
    traces = []
    boxes = []
    if cut.category == "Skiva" and not show_tabletop:
        return traces, boxes

    base_color = CATEGORY_COLORS.get(cut.category, "#AAAAAA")

    for idx, (pos, orient) in enumerate(zip(cut.positions, cut.orientations)):
        x0 = float(pos[0])
        y0 = float(pos[1])
        z0 = float(pos[2])
        length = float(cut.length_mm)
        w = float(cut.width_mm)    # 45mm (Y-led för sarg/tvärs, X-led för ben)
        h = float(cut.height_mm)   # 95mm (Z-led) eller t_top för skiva

        # Dimensionsmappning per orientering
        if orient == "X":
            dx, dy, dz = length, w, h
        elif orient == "Y":
            dx, dy, dz = w, length, h
        else:  # "Z" – ben
            dx, dy, dz = w, h, length

        instance_name = (cut.name if cut.quantity == 1
                         else f"{cut.name} #{idx + 1}")
        is_highlighted = bool(highlight_names and instance_name in highlight_names)

        color   = HIGHLIGHT_COLOR if is_highlighted else base_color
        opacity = 0.82 if cut.category == "Skiva" else 1.0

        if cut.category == "Skiva":
            hover = (
                f"<b>{instance_name}</b><br>"
                f"Material: {cut.profile}<br>"
                f"Mått: {int(dx)} × {int(dy)} mm<br>"
                f"Tjocklek: {int(dz)} mm<br>"
                f"Placering: X={int(x0)}–{int(x0+dx)} mm, Y={int(y0)}–{int(y0+dy)} mm"
            )
        else:
            hover = (
                f"<b>{instance_name}</b><br>"
                f"Kategori: {cut.category}<br>"
                f"Profil: {cut.profile}<br>"
                f"Kaplängd: <b>{cut.length_mm} mm</b><br>"
                f"Mått: {int(dx)} × {int(dy)} × {int(dz)} mm"
            )

        traces.append(_solid_box(
            x0, y0, z0, dx, dy, dz,
            color=color,
            name=instance_name,
            hover_text=hover,
            opacity=opacity,
        ))

        boxes.append((x0, y0, z0, dx, dy, dz, is_highlighted))

    return traces, boxes


# ---------------------------------------------------------------------------
# Vektor-typsnitt i 3D för måttangivelser på golvet
# Varje tecken ritas som 3D-linjesegment i (X, Y)-planet på golvet.
# Detta gör att texten alltid är 100% parallell med måttlinjen (längs X-axeln)
# oavsett hur 3D-kameran vrids eller roteras, och slipper 2D-billboard-artefakter.
# ---------------------------------------------------------------------------

_VECTOR_GLYPHS = {
    '0': [(0.2, 0), (0.8, 0), (1.0, 0.2), (1.0, 0.8), (0.8, 1.0), (0.2, 1.0), (0, 0.8), (0, 0.2), (0.2, 0)],
    '1': [(0.25, 0.72), (0.6, 1.0), (0.6, 0)],
    '2': [(0, 0.78), (0.2, 1.0), (0.8, 1.0), (1.0, 0.78), (1.0, 0.55), (0, 0), (1.0, 0)],
    '3': [(0, 0.82), (0.2, 1.0), (0.8, 1.0), (1.0, 0.78), (0.8, 0.52), (0.35, 0.52), None, (0.8, 0.52), (1.0, 0.26), (0.8, 0), (0.2, 0), (0, 0.18)],
    '4': [(0.75, 1.0), (0, 0.32), (1.0, 0.32), None, (0.75, 1.0), (0.75, 0)],
    '5': [(1.0, 1.0), (0, 1.0), (0, 0.55), (0.82, 0.55), (1.0, 0.38), (1.0, 0.15), (0.82, 0), (0, 0)],
    '6': [(0.8, 1.0), (0.2, 1.0), (0, 0.7), (0, 0.2), (0.2, 0), (0.8, 0), (1.0, 0.2), (1.0, 0.45), (0.8, 0.55), (0, 0.55)],
    '7': [(0, 1.0), (1.0, 1.0), (0.42, 0), None, (0.22, 0.52), (0.72, 0.52)],
    '8': [(0.2, 0.5), (0, 0.75), (0.2, 1.0), (0.8, 1.0), (1.0, 0.75), (0.8, 0.5), (0.2, 0.5), (0, 0.25), (0.2, 0), (0.8, 0), (1.0, 0.25), (0.8, 0.5)],
    '9': [(1.0, 0.5), (0.2, 0.5), (0, 0.7), (0.2, 1.0), (0.8, 1.0), (1.0, 0.8), (1.0, 0.2), (0.8, 0), (0.2, 0)],
    'm': [(0, 0), (0, 0.7), (0.15, 0.75), (0.35, 0.75), (0.5, 0.65), (0.5, 0), None, (0.5, 0.65), (0.65, 0.75), (0.85, 0.75), (1.0, 0.65), (1.0, 0)],
    ' ': [],
}


def _render_vector_text(
    text: str,
    x_center: float,
    y_center: float,
    z: float,
    char_h: float = 34.0,
) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]], float]:
    """Ritar text som 3D-vektorlinjer liggande i (X, Y)-planet på golvet, centrerat vid (x_center, y_center)."""
    widths = {'m': 1.15, ' ': 0.45, '1': 0.55}
    gap = 0.20 * char_h

    char_dims = []
    total_w = 0.0
    for ch in text:
        w_factor = widths.get(ch, 0.65)
        cw = w_factor * char_h
        char_dims.append((ch, cw))
        total_w += cw + gap
    if char_dims:
        total_w -= gap

    cur_x = x_center - total_w / 2.0
    y_base = y_center - char_h / 2.0

    xs: List[Optional[float]] = []
    ys: List[Optional[float]] = []
    zs: List[Optional[float]] = []

    for ch, cw in char_dims:
        pts = _VECTOR_GLYPHS.get(ch, [])
        for pt in pts:
            if pt is None:
                xs.append(None)
                ys.append(None)
                zs.append(None)
            else:
                u, v = pt
                xs.append(cur_x + u * cw)
                ys.append(y_base + v * char_h)
                zs.append(z)
        if pts:
            xs.append(None)
            ys.append(None)
            zs.append(None)
        cur_x += cw + gap

    return xs, ys, zs, total_w


def build_figure(
    geometry,
    highlighted_name: Optional[str] = None,
    show_tabletop: bool = True,
    show_rails: bool = True,
    dark_theme: bool = True,
    show_edges: bool = True,
    show_seams: bool = True,
    show_legend: bool = False,
    show_dimensions: bool = True,
) -> go.Figure:
    """Bygger komplett Plotly Figure för 3D-vyn av arbetsbänken med skarpa konturlinjer och skarvmarkeringar."""
    highlight_set = {highlighted_name} if highlighted_name else set()
    mesh_traces: List[go.Mesh3d] = []
    all_boxes: List[Tuple[float, float, float, float, float, float, bool]] = []

    for cut in geometry.cuts:
        if not show_rails and cut.category in ("Sarg", "Tvärslå"):
            continue
        traces, boxes = _piece_to_traces(cut, highlight_set, show_tabletop)
        mesh_traces.extend(traces)
        all_boxes.extend(boxes)

    margin = 180
    L, B, H = geometry.L, geometry.B, geometry.H

    # Färgtema för 3D-vyn
    if dark_theme:
        paper_bg = "#0e1117"        # Matchar Streamlits mörka tema
        scene_bg = "#161d2b"        # Mörk rymd för 3D-scenen
        grid_color = "#2d3748"      # Tydliga men diskreta rutnätslinjer
        text_color = "#e2e8f0"      # Ljus, lättläst text
        title_color = "#f8fafc"
        legend_bg = "rgba(22, 29, 43, 0.90)"
        legend_border = "#334155"
        edge_color = "#0a0e17"      # Skarp mörk kantlinje
        seam_color = "#FF4444"      # Röd/orange skarp skarvlinje
    else:
        paper_bg = "#fafaf8"
        scene_bg = "#f0f0ec"
        grid_color = "#d0d0d0"
        text_color = "#1e293b"
        title_color = "#0f172a"
        legend_bg = "rgba(255, 255, 255, 0.90)"
        legend_border = "#cccccc"
        edge_color = "#1e293b"      # Tydlig kantlinje i ljust läge
        seam_color = "#D32F2F"      # Tydlig röd skarvlinje

    figure_data: List[Any] = list(mesh_traces)

    # Lägg till skarpa konturlinjer (outlines) runt varje träbit
    if show_edges and all_boxes:
        std_xs, std_ys, std_zs = [], [], []
        hl_xs, hl_ys, hl_zs = [], [], []

        for x0, y0, z0, dx, dy, dz, is_hl in all_boxes:
            b_xs, b_ys, b_zs = _get_box_edges(x0, y0, z0, dx, dy, dz)
            if is_hl:
                hl_xs.extend(b_xs)
                hl_ys.extend(b_ys)
                hl_zs.extend(b_zs)
            else:
                std_xs.extend(b_xs)
                std_ys.extend(b_ys)
                std_zs.extend(b_zs)

        if std_xs:
            figure_data.append(go.Scatter3d(
                x=std_xs, y=std_ys, z=std_zs,
                mode="lines",
                line=dict(color=edge_color, width=3.5),
                hoverinfo="skip",
                showlegend=False,
                name="Konturer",
            ))

        if hl_xs:
            figure_data.append(go.Scatter3d(
                x=hl_xs, y=hl_ys, z=hl_zs,
                mode="lines",
                line=dict(color="#FF1111", width=5.5),
                hoverinfo="skip",
                showlegend=False,
                name="Markerad kontur",
            ))

    # Tydlig markering av bänkskivans skarvar i 3D
    top_L = getattr(geometry, "tabletop_L", geometry.L)
    top_B = getattr(geometry, "tabletop_B", geometry.B)
    max_x = max(geometry.L, top_L)
    max_y = max(geometry.B, top_B)

    if show_tabletop and show_seams and getattr(geometry, "tabletop_seams", None):
        t_top = getattr(geometry, "tabletop_thickness_mm", 16) or 16
        z_top = float(H) + 1.2
        z_bot = float(H) - float(t_top)

        seam_xs, seam_ys, seam_zs = [], [], []
        marker_xs, marker_ys, marker_zs, marker_hovers = [], [], [], []

        for seam in geometry.tabletop_seams:
            if seam["type"] == "X":
                x = float(seam["pos"])
                # Linje tvärs över ovanytan samt ner längs fram- och bakkant
                seam_xs.extend([x, x, None, x, x, None, x, x, None])
                seam_ys.extend([0, top_B, None, 0, 0, None, top_B, top_B, None])
                seam_zs.extend([z_top, z_top, None, z_bot, z_top, None, z_bot, z_top, None])

                marker_xs.append(x)
                marker_ys.append(top_B / 2.0)
                marker_zs.append(z_top + 2.0)
                marker_hovers.append(f"<b>⚠️ Skarv i bänkskivan</b><br>{seam['desc']}<br>Placering: X = {int(x)} mm")
            elif seam["type"] == "Y":
                y = float(seam["pos"])
                # Linje längs med ovanytan samt ner längs gavlarna
                seam_xs.extend([0, top_L, None, 0, 0, None, top_L, top_L, None])
                seam_ys.extend([y, y, None, y, y, None, y, y, None])
                seam_zs.extend([z_top, z_top, None, z_bot, z_top, None, z_bot, z_top, None])

                marker_xs.append(top_L / 2.0)
                marker_ys.append(y)
                marker_zs.append(z_top + 2.0)
                marker_hovers.append(f"<b>⚠️ Skarv i bänkskivan</b><br>{seam['desc']}<br>Placering: Y = {int(y)} mm")

        if seam_xs:
            figure_data.append(go.Scatter3d(
                x=seam_xs, y=seam_ys, z=seam_zs,
                mode="lines",
                line=dict(color=seam_color, width=6.0),
                hoverinfo="skip",
                showlegend=True,
                name="Skarv i bänkskiva",
            ))
            figure_data.append(go.Scatter3d(
                x=marker_xs, y=marker_ys, z=marker_zs,
                mode="markers",
                marker=dict(size=6, color=seam_color, symbol="diamond"),
                text=marker_hovers,
                hoverinfo="text",
                showlegend=False,
                name="Skarvmarkör",
            ))

    # Måttlinjer och text på golvet som visar avstånd mellan benen
    if show_dimensions and getattr(geometry, "leg_spans", None):
        dim_color = "#38bdf8" if dark_theme else "#0284c7"  # CAD-blå
        dim_line_xs: List[Optional[float]] = []
        dim_line_ys: List[Optional[float]] = []
        dim_line_zs: List[Optional[float]] = []

        guide_xs: List[Optional[float]] = []
        guide_ys: List[Optional[float]] = []
        guide_zs: List[Optional[float]] = []

        hover_xs: List[float] = []
        hover_ys: List[float] = []
        hover_zs: List[float] = []
        hover_texts: List[str] = []

        z_floor = 3.0  # 3 mm över golvet för att synas skarpt
        frame_y0 = getattr(geometry, "frame_y0", 0.0)
        leg_y0 = getattr(geometry, "front_leg_y", frame_y0 + 45.0)
        y_dim = min(frame_y0, leg_y0) - 75.0  # 75 mm framför bänkens framkant på golvet

        arrow_len = 22.0
        arrow_w = 6.0
        tick_h = 18.0
        gap_pad = 16.0

        for span in geometry.leg_spans:
            x0 = float(span["x_start"])
            x1 = float(span["x_end"])
            x_mid = float(span["x_mid"])
            free_mm = span["span_free_mm"]
            cc_mm = span["span_cc_mm"]
            bay = span["bay"]

            span_len = x1 - x0
            char_h = max(22.0, min(34.0, span_len * 0.05))
            text = f"{free_mm} mm"

            # 1. Rendera texten som 3D-vektorlinjer på golvet (100% parallell med måttlinjen)
            txs, tys, tzs, total_w = _render_vector_text(text, x_mid, y_dim, z_floor, char_h=char_h)
            dim_line_xs.extend(txs)
            dim_line_ys.extend(tys)
            dim_line_zs.extend(tzs)

            # 2. Ändtickar i Y (±18 mm)
            dim_line_xs.extend([x0, x0, None, x1, x1, None])
            dim_line_ys.extend([y_dim - tick_h, y_dim + tick_h, None, y_dim - tick_h, y_dim + tick_h, None])
            dim_line_zs.extend([z_floor, z_floor, None, z_floor, z_floor, None])

            # 3. Pilar vid ändarna som pekar in i öppningen
            dim_line_xs.extend([x0 + arrow_len, x0, x0 + arrow_len, None])
            dim_line_ys.extend([y_dim + arrow_w, y_dim, y_dim - arrow_w, None])
            dim_line_zs.extend([z_floor, z_floor, z_floor, None])

            dim_line_xs.extend([x1 - arrow_len, x1, x1 - arrow_len, None])
            dim_line_ys.extend([y_dim + arrow_w, y_dim, y_dim - arrow_w, None])
            dim_line_zs.extend([z_floor, z_floor, z_floor, None])

            # 4. Huvudmåttlinje med avbrott (gap) så linjen ALDRIG skär igenom texten
            x_gap0 = x_mid - total_w / 2.0 - gap_pad
            x_gap1 = x_mid + total_w / 2.0 + gap_pad

            if x_gap0 > x0 + arrow_len + 5 and x_gap1 < x1 - arrow_len - 5:
                dim_line_xs.extend([x0, x_gap0, None, x_gap1, x1, None])
                dim_line_ys.extend([y_dim, y_dim, None, y_dim, y_dim, None])
                dim_line_zs.extend([z_floor, z_floor, None, z_floor, z_floor, None])
            else:
                dim_line_xs.extend([x0, x1, None])
                dim_line_ys.extend([y_dim, y_dim, None])
                dim_line_zs.extend([z_floor, z_floor, None])

            # 5. Diskreta hjälplinjer från benens framkant ut till måttlinjen
            guide_xs.extend([x0, x0, None, x1, x1, None])
            guide_ys.extend([leg_y0, y_dim + tick_h, None, leg_y0, y_dim + tick_h, None])
            guide_zs.extend([z_floor, z_floor, None, z_floor, z_floor, None])

            # 6. Hovringsmål för detaljerad information
            htext = (
                f"<b>📏 Benavstånd (Fack {bay})</b><br>"
                f"Fritt avstånd (öppning): <b>{free_mm} mm</b><br>"
                f"Centrum–centrum (c/c): <b>{cc_mm} mm</b><br>"
                f"<i>(Benpar {bay} till {bay + 1})</i>"
            )
            for hx in [x_mid - total_w * 0.3, x_mid, x_mid + total_w * 0.3]:
                hover_xs.append(hx)
                hover_ys.append(y_dim)
                hover_zs.append(z_floor)
                hover_texts.append(htext)

        if dim_line_xs:
            # Huvudmåttlinjer + pilar + tickar + vektoriserad text
            figure_data.append(go.Scatter3d(
                x=dim_line_xs, y=dim_line_ys, z=dim_line_zs,
                mode="lines",
                line=dict(color=dim_color, width=3.8),
                hoverinfo="skip",
                showlegend=True,
                name="Benavstånd (golv)",
            ))

            # Hjälplinjer från benen
            figure_data.append(go.Scatter3d(
                x=guide_xs, y=guide_ys, z=guide_zs,
                mode="lines",
                line=dict(color=dim_color, width=1.5, dash="dot"),
                hoverinfo="skip",
                showlegend=False,
                name="Måtthjälplinjer",
            ))

            # Hovringsyta över texten för rik tooltip
            if hover_xs:
                figure_data.append(go.Scatter3d(
                    x=hover_xs, y=hover_ys, z=hover_zs,
                    mode="markers",
                    marker=dict(size=14, color="rgba(0,0,0,0.01)", opacity=0.01),
                    hovertext=hover_texts,
                    hoverinfo="text",
                    showlegend=False,
                    name="Benavstånd detaljer",
                ))

    fig = go.Figure(data=figure_data)
    fig.update_layout(
        uirevision="bench_3d_state",
        scene=dict(
            uirevision="bench_3d_state",
            xaxis=dict(
                range=[-margin, max_x + margin],
                title=dict(text="Längd (mm)", font=dict(color=text_color, size=12)),
                tickfont=dict(color=text_color, size=10),
                showgrid=True,
                gridcolor=grid_color,
                showbackground=True,
                backgroundcolor=scene_bg,
            ),
            yaxis=dict(
                range=[-margin, max_y + margin],
                title=dict(text="Djup (mm)", font=dict(color=text_color, size=12)),
                tickfont=dict(color=text_color, size=10),
                showgrid=True,
                gridcolor=grid_color,
                showbackground=True,
                backgroundcolor=scene_bg,
            ),
            zaxis=dict(
                range=[-50, H + margin],
                title=dict(text="Höjd (mm)", font=dict(color=text_color, size=12)),
                tickfont=dict(color=text_color, size=10),
                showgrid=True,
                gridcolor=grid_color,
                showbackground=True,
                backgroundcolor=scene_bg,
            ),
            aspectmode="data",
            camera=dict(
                eye=dict(x=1.7, y=-1.7, z=1.1),
                up=dict(x=0, y=0, z=1),
            ),
        ),
        showlegend=show_legend,
        legend=dict(
            title=dict(text="Delar – klicka för att växla", font=dict(color=text_color, size=11)),
            bgcolor=legend_bg,
            bordercolor=legend_border,
            borderwidth=1,
            font=dict(size=11, color=text_color),
        ) if show_legend else dict(visible=False),
        hoverlabel=dict(
            namelength=0,
            bgcolor="rgba(22, 29, 43, 0.95)" if dark_theme else "rgba(255, 255, 255, 0.95)",
            font=dict(
                family="Inter, system-ui, sans-serif",
                size=12,
                color="#f8fafc" if dark_theme else "#0f172a",
            ),
            bordercolor=legend_border,
        ),
        margin=dict(l=0, r=0, t=44, b=0),
        height=640,
        paper_bgcolor=paper_bg,
        font=dict(family="Inter, system-ui, sans-serif", size=12, color=text_color),
        title=dict(
            text="🔨 Interaktiv 3D-modell – Arbetsbänk",
            font=dict(size=15, color=title_color),
            x=0.5,
        ),
    )
    return fig
