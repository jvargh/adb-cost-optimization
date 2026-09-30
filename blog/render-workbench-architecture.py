"""Render the combined workbench architecture / evidence-flow blog figure.

Run from the repository root:
    python blog\\render-workbench-architecture.py

Uses the existing Pillow installation and Windows Segoe UI fonts. No network,
Graphviz, application runtime, or additional dependencies are required.
Output: blog\\assets\\workbench-architecture-flow.png (2200 x 1500).

Behavior checked against:
    ui\\docs\\architecture.md
    assessment\\docs\\architecture.md
    ui\\Start-AssessmentUi.ps1
    ui\\src\\api\\httpBackend.ts
    ui\\server\\assessment_server.py
    ui\\server\\permission_setup.py
    ui\\server\\capability_operations.py
    assessment\\Invoke-Assessment.ps1
    assessment\\Collect-CostOptimizationAssessment.ps1
    assessment\\pipeline\\run_assessment.py

Boxes describe responsibilities, not independently deployed services. External
arrows combine read requests and returned evidence. Readiness also makes live
reads; the main numbered flow describes an explicitly started full assessment.
"""

from __future__ import annotations

import math
import os
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH, HEIGHT, SCALE = 2200, 1500, 2
OUTPUT = Path(__file__).resolve().parent / "assets" / "workbench-architecture-flow.png"
FONT_DIR = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"

INK = "#20344A"
MUTED = "#4D6175"
LINE = "#506C87"
BORDER = "#C3CFDA"
LOCAL = "#F6F8FB"
BLUE = "#245F8F"
BLUE_FILL = "#EDF4FA"
TEAL = "#226C69"
TEAL_FILL = "#EDF7F4"
AMBER = "#845B22"
AMBER_FILL = "#FBF5EA"
WHITE = "#FFFFFF"

Box = tuple[float, float, float, float]
Point = tuple[float, float]


@lru_cache
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_DIR / ("seguisb.ttf" if bold else "segoeui.ttf")
    if not path.is_file():
        raise FileNotFoundError(f"Required Segoe UI font not found: {path}")
    return ImageFont.truetype(str(path), size * SCALE)


def scaled(values: tuple[float, ...]) -> tuple[int, ...]:
    return tuple(round(value * SCALE) for value in values)


class Figure:
    def __init__(self) -> None:
        self.image = Image.new("RGB", (WIDTH * SCALE, HEIGHT * SCALE), WHITE)
        self.draw = ImageDraw.Draw(self.image)
        self.text_boxes: list[tuple[str, Box]] = []
        self.segments: list[tuple[Point, Point]] = []

    def panel(self, box: Box, fill: str, outline: str = BORDER, radius: int = 18) -> None:
        self.draw.rounded_rectangle(
            scaled(box), radius=radius * SCALE, fill=fill, outline=outline, width=2 * SCALE
        )

    def text(
        self, x: float, y: float, value: str, size: int = 30,
        *, bold: bool = False, color: str = INK, center: bool = False,
        within: Box = (0, 0, WIDTH, HEIGHT),
    ) -> None:
        face = font(size, bold)
        bounds = self.draw.textbbox((0, 0), value, font=face, anchor="lt")
        width, height = (bounds[2] - bounds[0]) / SCALE, (bounds[3] - bounds[1]) / SCALE
        if center:
            x -= width / 2
        box = (x, y, x + width, y + height)
        if not (within[0] <= x and within[1] <= y
                and box[2] <= within[2] and box[3] <= within[3]):
            raise ValueError(f"Text exceeds its allocated area: {value!r}: {box}")
        self.text_boxes.append((value, box))
        self.draw.text(scaled((x, y)), value, font=face, fill=color, anchor="lt")

    def arrow(
        self, points: list[Point], *, color: str = LINE,
        dashed: bool = False, both: bool = False,
    ) -> None:
        for start, end in zip(points, points[1:]):
            if start[0] != end[0] and start[1] != end[1]:
                raise ValueError("Use orthogonal connectors to keep routing predictable.")
            self.segments.append((start, end))
            if dashed:
                distance = math.dist(start, end)
                for offset in range(0, math.ceil(distance), 20):
                    a, b = offset / distance, min(offset + 11, distance) / distance
                    p = tuple(start[i] + (end[i] - start[i]) * a for i in range(2))
                    q = tuple(start[i] + (end[i] - start[i]) * b for i in range(2))
                    self.draw.line([scaled(p), scaled(q)], fill=color, width=3 * SCALE)
            else:
                self.draw.line([scaled(start), scaled(end)], fill=color, width=3 * SCALE)

        def head(previous: Point, tip: Point) -> None:
            angle = math.atan2(tip[1] - previous[1], tip[0] - previous[0])
            back = (tip[0] - 13 * math.cos(angle), tip[1] - 13 * math.sin(angle))
            vertices = [
                tip,
                (back[0] + 6 * math.sin(angle), back[1] - 6 * math.cos(angle)),
                (back[0] - 6 * math.sin(angle), back[1] + 6 * math.cos(angle)),
            ]
            self.draw.polygon([scaled(p) for p in vertices], fill=color)

        head(points[-2], points[-1])
        if both:
            head(points[1], points[0])

    def stage(self, box: Box, number: str, title: str, lines: list[str], *, saved: bool = False) -> None:
        accent, fill = (TEAL, TEAL_FILL) if saved else (BLUE, WHITE)
        self.panel(box, fill)
        x, y, right, bottom = box
        inset = (x + 22, y + 16, right - 22, bottom - 16)
        self.text(x + 24, y + 19, number, 25, bold=True, color=accent, within=inset)
        self.text(x + 24, y + 58, title, 34, bold=True, within=inset)
        for index, line in enumerate(lines):
            self.text(x + 24, y + 105 + index * 39, line, 28, color=MUTED, within=inset)

    def validate(self) -> None:
        for index, (label, box) in enumerate(self.text_boxes):
            for other_label, other in self.text_boxes[index + 1:]:
                if box[0] < other[2] and other[0] < box[2] and box[1] < other[3] and other[1] < box[3]:
                    raise ValueError(f"Overlapping text: {label!r} / {other_label!r}")
            for start, end in self.segments:
                if start[0] == end[0]:
                    crosses = box[0] < start[0] < box[2] and max(box[1], min(start[1], end[1])) < min(box[3], max(start[1], end[1]))
                else:
                    crosses = box[1] < start[1] < box[3] and max(box[0], min(start[0], end[0])) < min(box[2], max(start[0], end[0]))
                if crosses:
                    raise ValueError(f"Connector crosses text: {label!r}")

    def save(self) -> None:
        self.validate()
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        image = self.image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        image.save(OUTPUT, optimize=True, dpi=(144, 144))
        print(f"Rendered {OUTPUT}")
        print(f"{WIDTH} x {HEIGHT}; {OUTPUT.stat().st_size:,} bytes")
        print(f"Layout checks passed: {len(self.text_boxes)} text labels; no overflow or connector/text overlap.")


def main() -> None:
    f = Figure()
    f.text(54, 36, "Azure Databricks Assessment & Optimization Workbench", 46, bold=True)
    f.text(56, 103, "Local application architecture and evidence collection", 30, color=MUTED)

    f.panel((44, 169, 1620, 1280), LOCAL)
    f.text(80, 196, "LOCAL MACHINE", 27, bold=True, color=BLUE)
    f.text(390, 197, "Browser, processes and saved run folders - not an Azure-hosted app", 27, color=MUTED)
    f.text(80, 241, "Readiness checks live access; full collection starts only when the user selects Run.", 28, color=MUTED)

    f.stage((88, 305, 500, 495), "1  CONFIGURE", "Browser UI", [
        "React + TypeScript",
        "Configure, review, export",
    ])
    f.stage((690, 305, 1100, 495), "2  ORCHESTRATE", "Python API", [
        "Loopback orchestrator",
        "Launch + track runs",
    ])
    f.stage((1200, 305, 1576, 495), "3  CHECK", "Scope + access", [
        "Readiness + approvals",
        "User starts Run",
    ])
    f.stage((1200, 635, 1576, 825), "4  COLLECT", "PowerShell", [
        "Read-only collectors",
        "Azure + Databricks",
    ])
    f.stage((1200, 940, 1576, 1170), "5  SAVE", "Raw evidence", [
        "JSON / NDJSON",
        "Source status + logs",
        "Saved config + manifest",
    ], saved=True)
    f.stage((690, 940, 1100, 1170), "6  ANALYZE", "Python analysis", [
        "Normalize + correlate",
        "Reconcile cost + quality",
        "Rules + reports",
    ])
    f.stage((88, 940, 500, 1170), "7  REVIEW / EXPORT", "Saved results", [
        "Findings + reports",
        "Human review decisions",
        "CSV / JSON / XLSX",
    ], saved=True)

    f.arrow([(500, 386), (690, 386)])
    f.text(595, 343, "Requests", 28, center=True)
    f.arrow([(690, 445), (500, 445)])
    f.text(595, 459, "Results", 28, center=True)
    f.text(595, 408, "local HTTP", 25, center=True, color=MUTED)
    f.arrow([(1100, 400), (1200, 400)])
    f.text(1150, 358, "Check", 27, center=True)
    f.arrow([(1388, 495), (1388, 635)])
    f.text(1268, 555, "Explicit Run", 28, center=True)
    f.arrow([(1388, 825), (1388, 940)])
    f.text(1448, 870, "Save", 28, center=True)
    f.arrow([(1200, 1060), (1100, 1060)])
    f.text(1150, 1018, "Read", 27, center=True)
    f.arrow([(690, 1060), (500, 1060)])
    f.text(595, 1018, "Save", 28, center=True)

    f.arrow([(294, 940), (294, 566), (895, 566), (895, 495)], color=TEAL)
    f.text(588, 584, "Load saved results via API", 28, center=True, color=TEAL)

    reuse = (402, 685, 1100, 872)
    f.panel(reuse, TEAL_FILL, "#B7D2CB")
    f.text(432, 711, "REUSE SAVED EVIDENCE", 25, bold=True, color=TEAL, within=reuse)
    f.text(432, 754, "Reopen snapshots without live collection.", 28, within=reuse)
    f.text(432, 793, "Offline re-analysis creates a new run.", 28, within=reuse)
    f.text(432, 832, "Original evidence and review stay unchanged.", 28, within=reuse)
    f.arrow([(1388, 1170), (1388, 1220), (895, 1220), (895, 1170)], color=TEAL, dashed=True)
    f.text(1140, 1235, "Re-analyze saved raw", 28, center=True, color=TEAL)

    sources = (1680, 169, 2156, 1280)
    f.panel(sources, BLUE_FILL, "#AAC3D8")
    f.text(1710, 197, "EXTERNAL SOURCES", 27, bold=True, color=BLUE, within=sources)
    f.text(1710, 244, "Selected Azure / Databricks scope", 26, color=MUTED, within=sources)

    azure = (1706, 325, 2130, 522)
    f.panel(azure, WHITE, "#B8CDDF")
    f.text(1732, 356, "Azure resource + cost", 32, bold=True, within=azure)
    f.text(1732, 415, "Resource Graph / ARM", 29, within=azure)
    f.text(1732, 458, "Cost Management", 29, within=azure)

    f.text(1918, 588, "HTTPS read requests", 28, center=True, color=BLUE, within=sources)
    f.text(1918, 628, "and returned evidence", 28, center=True, color=BLUE, within=sources)
    f.arrow([(1576, 735), (1680, 735)], both=True, color=BLUE)

    databricks = (1706, 745, 2130, 944)
    f.panel(databricks, WHITE, "#B8CDDF")
    f.text(1732, 776, "Databricks", 34, bold=True, within=databricks)
    f.text(1732, 835, "Workspace / account APIs", 28, within=databricks)
    f.text(1732, 878, "System tables via SQL", 29, within=databricks)

    charge = (1706, 1004, 2130, 1238)
    f.panel(charge, AMBER_FILL, "#D8C5A5")
    f.text(1732, 1033, "READ-ONLY CAN INCUR COST", 24, bold=True, color=AMBER, within=charge)
    f.text(1732, 1080, "SQL may start a warehouse", 28, within=charge)
    f.text(1732, 1122, "and incur compute charges.", 28, within=charge)
    f.text(1732, 1164, "Explicit approval required.", 28, within=charge)

    boundary = (44, 1312, 2156, 1464)
    f.panel(boundary, AMBER_FILL, "#D8C5A5")
    f.text(78, 1340, "ASSESSMENT BOUNDARY", 25, bold=True, color=AMBER, within=boundary)
    f.text(78, 1386, "Assessment does not remediate", 29, bold=True, within=boundary)
    f.text(78, 1427, "Recommendations require human review.", 27, within=boundary)
    f.text(810, 1340, "SEPARATE ACTIONS - EACH REQUIRES EXPLICIT CONFIRMATION", 25, bold=True, color=AMBER, within=boundary)
    f.text(810, 1386, "Permission setup: scoped read grants. Dashboard publication: coverage counts only.", 28, within=boundary)
    f.text(810, 1427, "These can write to Databricks; neither is part of assessment collection.", 27, within=boundary)
    f.save()


if __name__ == "__main__":
    main()
