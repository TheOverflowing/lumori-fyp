"""Compact, original vector diagrams for the formal Lumori manuscript.

The diagrams are authored from the documented control/data-flow specifications,
not edits of earlier image-generated assets. PDF is the editable vector master;
PNG is a high-resolution, lossless embedding companion.
"""
from pathlib import Path
import hashlib
import json
import math
import os
import subprocess
import sys

from reportlab.lib.colors import HexColor
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/thesis/figures/v0.5"
POP = Path(sys.executable).parents[2] / "bin/override/pdftoppm"
os.environ["FONTCONFIG_FILE"] = str(ROOT / "tmp/thesis/fonts.conf")
INK = "#243444"
MUTED = "#536577"
LINE = "#7F94A6"
ACCENT = "#365D7C"
FILL = "#EDF3F7"
SOFT = "#F8FAFC"
MANIFEST = []


class Diagram:
    width = 720

    def __init__(self, name, height, sources):
        self.name, self.height, self.sources = name, height, sources
        self.c = canvas.Canvas(str(OUT / f"{name}.pdf"), pagesize=(self.width, height))
        self.c.setTitle(name.replace("-", " "))
        self.c.setAuthor("Lumori project")
        self.c.setSubject("Original schematic; deterministic vector rendering")
        self.c.setFillColor(HexColor("#FFFFFF"))
        self.c.rect(0, 0, self.width, height, fill=1, stroke=0)

    def text(self, x, y, value, size=12, bold=False, color=INK, align="center"):
        c = self.c
        c.setFillColor(HexColor(color))
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        fn = c.drawCentredString if align == "center" else c.drawString
        for i, s in enumerate(value.split("\n")):
            fn(x, self.height - y - i * (size + 3), s)

    def box(self, x, y, w, h, title, body="", active=False, dashed=False):
        c = self.c
        c.setLineWidth(.85)
        c.setStrokeColor(HexColor(ACCENT if active else LINE))
        c.setFillColor(HexColor(FILL if active else SOFT))
        c.setDash([4, 3] if dashed else [])
        c.roundRect(x, self.height - y - h, w, h, 5, fill=1, stroke=1)
        c.setDash([])
        lines = title.split("\n")
        bodylines = body.split("\n") if body else []
        total = len(lines) * 17 + (len(bodylines) * 14.5 + 5 if bodylines else 0)
        top = y + (h - total) / 2 + 14
        for s in lines:
            assert stringWidth(s, "Helvetica-Bold", 14) < w - 12, (self.name, s, w)
        self.text(x + w / 2, top, title, 14, True)
        if body:
            for s in bodylines:
                assert stringWidth(s, "Helvetica", 11.5) < w - 12, (self.name, s, w)
            self.text(x + w / 2, top + len(lines) * 17 + 3, body, 11.5, color=MUTED)

    def decision(self, x, y, w, h, value):
        c = self.c
        c.setStrokeColor(HexColor(ACCENT)); c.setFillColor(HexColor(FILL)); c.setLineWidth(.9)
        p = c.beginPath()
        p.moveTo(x + w / 2, self.height - y)
        for px, py in [(x + w, y + h / 2), (x + w / 2, y + h), (x, y + h / 2)]:
            p.lineTo(px, self.height - py)
        p.close(); c.drawPath(p, fill=1, stroke=1)
        lines = value.split("\n")
        self.text(x + w / 2, y + h / 2 - (len(lines) - 1) * 7 + 4, value, 11.7, True)

    def group(self, x, y, w, h, label, dashed=False):
        c = self.c
        c.setStrokeColor(HexColor("#CDD7DF")); c.setLineWidth(.7)
        c.setFillColor(HexColor("#FFFFFF")); c.setDash([4, 3] if dashed else [])
        c.roundRect(x, self.height - y - h, w, h, 7, stroke=1, fill=1); c.setDash([])
        self.text(x + 12, y + 16, label, 9.5, True, MUTED, "left")

    def arrow(self, pts, label="", lx=None, ly=None, dashed=False):
        c = self.c
        c.setStrokeColor(HexColor(ACCENT)); c.setFillColor(HexColor(ACCENT)); c.setLineWidth(1.1)
        c.setDash([4, 3] if dashed else [])
        p = c.beginPath(); p.moveTo(pts[0][0], self.height - pts[0][1])
        for x, y in pts[1:]: p.lineTo(x, self.height - y)
        c.drawPath(p); c.setDash([])
        (x0, y0), (x1, y1) = pts[-2:]
        angle = math.atan2(y1 - y0, x1 - x0)
        p = c.beginPath(); p.moveTo(x1, self.height - y1)
        for a in [angle - .45, angle + .45]:
            p.lineTo(x1 - 6 * math.cos(a), self.height - (y1 - 6 * math.sin(a)))
        p.close(); c.drawPath(p, fill=1, stroke=0)
        if label:
            assert lx is not None and ly is not None
            vals = label.split("\n"); size = 10
            wid = max(stringWidth(s, "Helvetica", size) for s in vals) + 7
            c.setFillColor(HexColor("#FFFFFF"))
            c.rect(lx - wid / 2, self.height - ly - (len(vals) - 1) * 13 - 3, wid, len(vals) * 13, fill=1, stroke=0)
            self.text(lx, ly, label, size, color=MUTED)

    def note(self, value, y):
        self.text(360, y, value, 10.8, color=MUTED)

    def save(self):
        self.c.showPage(); self.c.save()
        subprocess.run([str(POP), "-png", "-scale-to", "2400", "-singlefile", str(OUT / f"{self.name}.pdf"), str(OUT / self.name)], check=True, stdout=subprocess.DEVNULL)
        MANIFEST.append({"name": self.name, "width_pt": self.width, "height_pt": self.height,
                         "height_at_6_3_in_width": round(self.height / self.width * 6.3, 3),
                         "source_specifications": self.sources,
                         "files": {ext: {"path": f"docs/thesis/figures/v0.5/{self.name}.{ext}",
                                         "sha256": hashlib.sha256((OUT / f"{self.name}.{ext}").read_bytes()).hexdigest()}
                                   for ext in ("pdf", "png")}})


def architecture():
    d = Diagram("architecture", 303, ["docs/thesis/versions/v0.4/build_thesis_report.py:architecture", "docs/thesis/Manuscript.md:3.2"])
    d.group(8, 8, 704, 95, "APPLICATION AND PERSISTENCE")
    d.box(22, 34, 172, 54, "Browser", "Owned course workspace")
    d.box(254, 34, 196, 54, "FastAPI coordinator", "Identity · jobs · validation", active=True)
    d.box(510, 34, 184, 54, "Evidence store", "SQLite + source files")
    d.arrow([(194, 61), (254, 61)])
    d.arrow([(450, 61), (510, 61)])
    d.group(8, 132, 704, 95, "CORE TEXT WORKFLOW")
    for x, title, body in [(22, "Ingest", "Native text / MinerU"), (202, "Retrieve / rerank", "Dense + lexical"), (382, "Generate", "Grounded text model"), (562, "Validate", "Structure + demand")]:
        d.box(x, 158, 132, 54, title, body)
    for x in [154, 334, 514]: d.arrow([(x, 185), (x + 48, 185)])
    d.arrow([(108, 88), (108, 119), (16, 119), (16, 185), (22, 185)])
    d.arrow([(352, 88), (352, 119), (268, 119), (268, 158)])
    d.arrow([(628, 158), (628, 88)])
    d.box(144, 247, 432, 46, "Provider adapters", "Text generation · embeddings · reranking")
    d.save()


def ingestion():
    d = Diagram("ingestion-flow", 271, ["scripts/build_thesis_figures.py:ingestion-flow"])
    d.box(20, 20, 175, 65, "Source document", "Text · PDF · image")
    d.box(270, 20, 185, 65, "Parse text", "Native parser / MinerU\nStandard or Advanced", active=True)
    d.box(530, 20, 170, 65, "Recursive chunks", "Budgeted source slices")
    d.arrow([(195, 52), (270, 52)])
    d.arrow([(455, 52), (530, 52)])
    d.box(20, 163, 175, 68, "Optional figures", "Docling crop\nModel description", dashed=True)
    d.box(270, 163, 185, 68, "Source metadata", "Document · page · heading\nOriginal image association")
    d.box(530, 163, 170, 68, "Compatible vectors", "Title context + chunk\nOwner + course scope", active=True)
    d.arrow([(107, 85), (107, 163)], "opt in", 130, 124, dashed=True)
    d.arrow([(195, 197), (270, 197)], dashed=True)
    d.arrow([(362, 85), (362, 163)], "preserve", 390, 124)
    d.arrow([(455, 183), (490, 183), (490, 110), (575, 110), (575, 85)], "attach", 514, 103)
    d.arrow([(655, 85), (655, 163)])
    d.note("Input enrichment remains distinct from future multimodal output generation.", 257)
    d.save()


def account():
    d = Diagram("account-scope", 258, ["scripts/build_thesis_visuals_v04.py:account-scope"])
    d.box(16, 22, 130, 60, "Register / log in", "Opaque session")
    d.decision(190, 14, 110, 76, "Valid\nsession?")
    d.decision(356, 14, 110, 76, "Owned\nresource?")
    d.box(548, 22, 154, 60, "Scoped objects", "Sources · jobs · versions", active=True)
    d.arrow([(146, 52), (190, 52)])
    d.arrow([(300, 52), (356, 52)], "yes", 327, 44)
    d.arrow([(466, 52), (548, 52)], "owned read", 506, 43)
    d.box(260, 167, 190, 59, "Reject request", "Unauthenticated / denied")
    d.decision(538, 153, 135, 84, "Valid CSRF\ntoken?")
    d.arrow([(507, 52), (507, 195), (538, 195)], "mutation", 480, 124)
    d.arrow([(673, 195), (708, 195), (708, 105), (625, 105), (625, 82)], "yes", 694, 126)
    d.arrow([(245, 90), (245, 195), (260, 195)], "no", 228, 133)
    d.arrow([(411, 90), (411, 167)], "no", 426, 133)
    d.arrow([(605, 237), (605, 246), (355, 246), (355, 226)], "invalid token", 479, 242)
    d.save()


def chunk():
    d = Diagram("chunk-provenance", 270, ["scripts/build_thesis_visuals_v04.py:chunk-provenance"])
    d.box(18, 22, 158, 61, "Parsed pages", "Preserve source text")
    d.box(245, 22, 210, 61, "Structural units", "Headings · paragraphs\nProtected blocks", active=True)
    d.decision(534, 16, 155, 73, "Within\nbudget?")
    d.arrow([(176, 52), (245, 52)])
    d.arrow([(455, 52), (534, 52)])
    d.box(523, 154, 177, 62, "Finer boundaries", "Sentence / line / word\nFallback if required")
    d.arrow([(612, 89), (612, 154)], "no", 626, 122)
    d.arrow([(700, 185), (710, 185), (710, 52), (689, 52)], dashed=True)
    d.text(664, 133, "recheck", 10, color=MUTED)
    d.box(245, 154, 210, 62, "Traceable chunks", "Page + heading path\nCharacter bounds + hash", active=True)
    d.arrow([(573, 71), (490, 115), (350, 115), (350, 154)], "yes", 439, 108)
    d.box(18, 154, 158, 62, "Embed", "Title context + body\nCompatible model")
    d.arrow([(245, 185), (176, 185)])
    d.note("Chunk text remains an exact source slice; retrieval context is added separately.", 253)
    d.save()


def retrieval():
    d = Diagram("retrieval-generated", 321, ["scripts/build_thesis_visuals_v04.py:retrieval-reference"])
    d.box(18, 30, 143, 60, "Original query", "Always retained", active=True)
    d.box(229, 30, 173, 60, "Hybrid retrieval", "Original wording")
    d.box(229, 194, 173, 60, "Hybrid retrieval", "Rewritten wording", dashed=True)
    d.box(18, 194, 143, 60, "Query rewrite", "Model proposal", dashed=True)
    d.box(473, 194, 119, 60, "RRF60", "Rank fusion", dashed=True)
    d.box(473, 30, 119, 60, "Rerank", "Bounded top-k", active=True)
    d.box(632, 30, 74, 60, "Evidence")
    d.arrow([(161, 60), (229, 60)])
    d.arrow([(402, 60), (473, 60)], "direct", 438, 51)
    d.arrow([(592, 60), (632, 60)])
    d.arrow([(89, 90), (89, 194)], "fusion on", 117, 142, dashed=True)
    d.arrow([(161, 224), (229, 224)], dashed=True)
    d.arrow([(402, 224), (473, 224)], dashed=True)
    d.arrow([(402, 76), (437, 110), (437, 181), (503, 181), (503, 194)], dashed=True)
    d.arrow([(561, 194), (561, 90)], "fused", 581, 144, dashed=True)
    d.box(233, 113, 164, 51, "Owned course index", "Dense + lexical candidates")
    d.arrow([(315, 113), (315, 90)])
    d.arrow([(315, 164), (315, 194)], dashed=True)
    d.note("Direct route: fusion off or fallback. Dashed route: optional query fusion.", 294)
    d.save()


def question():
    d = Diagram("question-agent", 330, ["scripts/build_thesis_figures.py:question-agent"])
    d.box(20, 18, 185, 66, "Freeze plan", "Slots + difficulty counts\nFixed source snapshot", active=True)
    d.box(270, 18, 180, 66, "Author one question", "Answer + explanation\nCitations")
    d.box(515, 18, 185, 66, "Blind solver", "Answer and target hidden")
    d.arrow([(205, 51), (270, 51)])
    d.arrow([(450, 51), (515, 51)])
    d.box(515, 125, 185, 60, "Review", "Answer + source support")
    d.box(270, 125, 180, 60, "Policy decision", "Strict / adjusted / repair", active=True)
    d.arrow([(607, 84), (607, 125)])
    d.arrow([(515, 155), (450, 155)])
    d.arrow([(305, 125), (305, 105), (360, 105), (360, 84)], "repair", 333, 112)
    d.box(20, 125, 185, 60, "Stop when required", "No eligible candidate\nProvider or quota failure")
    d.arrow([(270, 155), (205, 155)])
    d.box(270, 242, 180, 58, "Accepted checkpoint", "Checks + attempts + sources")
    d.box(515, 242, 185, 58, "Assemble draft", "Complete accepted set only")
    d.arrow([(360, 185), (360, 242)], "accepted", 388, 215)
    d.arrow([(450, 271), (515, 271)], "all slots", 482, 261)
    d.arrow([(270, 271), (239, 271), (239, 108), (270, 108), (270, 69)], "next slot", 201, 229, dashed=True)
    d.save()


def supervisor():
    d = Diagram("supervisor-generated", 443, ["scripts/build_thesis_visuals_v04.py:supervisor-reference", "docs/thesis/Manuscript.md:4.7.1"])
    d.group(8, 8, 694, 171, "HOST CONTROLLER  /  OPTIONAL SUPERVISOR")
    d.box(22, 38, 139, 56, "Main agent", "Plan question briefs", active=True)
    d.decision(192, 32, 115, 68, "Valid\nplan?")
    d.box(344, 38, 144, 56, "Freeze + dispatch", "One slot at a time", active=True)
    d.decision(538, 32, 120, 68, "All slots\naccepted?")
    d.box(192, 122, 115, 42, "Stop + record")
    d.box(526, 122, 164, 42, "Assemble draft", "Deterministic; no rewrite")
    d.arrow([(161, 66), (192, 66)])
    d.arrow([(307, 66), (344, 66)], "yes", 324, 58)
    d.arrow([(249, 100), (249, 122)], "no", 265, 114)
    d.arrow([(538, 66), (488, 66)], "no", 513, 58)
    d.arrow([(598, 100), (598, 122)], "yes", 615, 114)
    d.group(8, 216, 694, 215, "ISOLATED QUESTION WORKER q_i  /  FRESH ROLE CONTEXTS")
    d.box(24, 248, 125, 52, "Author")
    d.box(193, 248, 125, 52, "Blind solver")
    d.box(362, 248, 125, 52, "Reviewer")
    d.decision(542, 241, 116, 66, "Accept?")
    d.arrow([(149, 274), (193, 274)])
    d.arrow([(318, 274), (362, 274)])
    d.arrow([(487, 274), (542, 274)])
    d.box(532, 354, 158, 50, "Save checkpoint", "Accepted slot + evidence")
    d.decision(361, 346, 128, 66, "Repair\nbudget?")
    d.box(187, 354, 142, 50, "Retain failure")
    d.arrow([(600, 307), (600, 354)], "yes", 617, 333)
    d.arrow([(561, 288), (524, 324), (425, 324), (425, 346)], "no", 478, 317)
    d.arrow([(361, 379), (329, 379)], "no", 345, 368)
    d.arrow([(425, 412), (425, 421), (86, 421), (86, 300)], "yes: repair feedback", 220, 415)
    d.arrow([(416, 94), (416, 202), (503, 202), (503, 240), (86, 240), (86, 248)], "frozen brief + source IDs", 327, 194)
    d.arrow([(690, 379), (711, 379), (711, 111), (669, 111), (669, 66), (658, 66)], "accepted", 670, 200)
    d.save()


def difficulty():
    d = Diagram("difficulty-decision", 337, ["scripts/build_thesis_figures.py:difficulty-decision", "docs/thesis/Manuscript.md:4.8"])
    d.box(18, 19, 175, 60, "Eligible candidate", "Other quality checks pass")
    d.decision(260, 12, 157, 75, "Demand\nmatches target?")
    d.box(511, 19, 191, 60, "Strict acceptance", "strict_passed = true", active=True)
    d.arrow([(193, 49), (260, 49)])
    d.arrow([(417, 49), (511, 49)], "yes", 464, 41)
    d.decision(260, 123, 157, 76, "Rounds\nremaining?")
    d.arrow([(338, 87), (338, 123)], "no", 354, 106)
    d.box(18, 131, 175, 60, "Repair candidate", "Normal limit: 3 rounds")
    d.arrow([(260, 161), (193, 161)], "yes", 224, 152)
    d.arrow([(105, 131), (105, 79)])
    d.box(243, 248, 191, 64, "Closest eligible result", "Adjacent level first\nThen any level")
    d.arrow([(338, 199), (338, 248)], "exhausted", 375, 224)
    d.box(511, 248, 191, 64, "Adjusted draft", "Keep requested target\nstrict_passed = false", active=True)
    d.arrow([(434, 279), (511, 279)], "found", 472, 270)
    d.box(18, 248, 175, 64, "Stop + retain record", "No eligible candidate")
    d.arrow([(243, 279), (193, 279)], "none", 218, 270)
    d.save()


def exploration():
    d = Diagram("exploration-flow", 321, ["scripts/build_thesis_figures.py:exploration-flow"])
    d.box(18, 22, 178, 65, "Identify gaps", "Missing concepts + scope")
    d.box(269, 22, 181, 65, "Discover + fetch", "Curated source catalog\nOptional search provider")
    d.box(524, 22, 178, 65, "Task-private index", "Parse → chunk → embed", active=True)
    d.arrow([(196, 54), (269, 54)])
    d.arrow([(450, 54), (524, 54)])
    d.box(524, 164, 178, 65, "Gap-focused retrieval", "Bounded evidence\nSelective nearby context")
    d.decision(285, 162, 150, 69, "Enough\nevidence?")
    d.box(18, 164, 178, 65, "Promote sources", "Owned course + provenance\nReuse compatible vectors", active=True)
    d.arrow([(613, 87), (613, 164)])
    d.arrow([(524, 196), (435, 196)])
    d.arrow([(285, 196), (196, 196)], "yes", 240, 188)
    d.arrow([(360, 162), (360, 87)], "no + budget", 397, 127, dashed=True)
    d.box(267, 268, 185, 41, "Stop with gap record")
    d.arrow([(360, 231), (360, 268)], "budget exhausted", 424, 252)
    d.save()


def lifecycle():
    d = Diagram("job-lifecycle", 292, ["scripts/build_thesis_figures.py:job-lifecycle"])
    d.box(18, 22, 170, 64, "Persist request", "Owner + inputs + settings")
    d.box(269, 22, 184, 64, "Running job", "Durable stage events\nElapsed time", active=True)
    d.box(529, 22, 173, 64, "Complete draft", "Versioned; review pending")
    d.arrow([(188, 54), (269, 54)])
    d.arrow([(453, 54), (529, 54)])
    d.box(269, 162, 184, 65, "Interrupted / rejected", "Keep accepted slots\nRetain failure details")
    d.arrow([(361, 86), (361, 162)])
    d.box(18, 162, 170, 65, "Resume or edit", "Compatible checkpoint\nOr restore request inputs")
    d.arrow([(269, 195), (188, 195)])
    d.arrow([(103, 162), (103, 121), (243, 121), (243, 66), (269, 66)], "user initiated", 172, 113, dashed=True)
    d.box(529, 162, 173, 65, "Open result", "Review · rate · export")
    d.arrow([(615, 86), (615, 162)])
    d.note("Continuation requires compatible checkpoints and available task / account quotas.", 270)
    d.save()


def review_export():
    d = Diagram("review-export-generated", 307, ["scripts/build_thesis_visuals_v04.py:review-export-reference"])
    d.box(18, 23, 151, 59, "Saved version", "Stable content identity", active=True)
    d.box(239, 23, 175, 59, "Review + evidence", "Inspect linked sources")
    d.box(527, 23, 175, 59, "Approve text")
    d.arrow([(169, 52), (239, 52)])
    d.arrow([(414, 52), (527, 52)])
    d.box(239, 129, 175, 59, "Edit → new version", "Reopen for review")
    d.arrow([(326, 82), (326, 129)])
    d.arrow([(414, 158), (463, 158), (463, 99), (385, 99), (385, 82)])
    d.box(18, 129, 151, 59, "Version rating", "Insert or update")
    d.arrow([(94, 82), (94, 129)])
    d.box(18, 237, 396, 58, "Export saved text", "PDF / Word / Markdown · source-level references", active=True)
    d.arrow([(18, 52), (8, 52), (8, 266), (18, 266)])
    d.box(527, 237, 175, 58, "Future media", "Version-bound artifacts", dashed=True)
    d.arrow([(615, 82), (615, 237)], "future extension", 663, 163, dashed=True)
    d.save()


def evaluation():
    d = Diagram("evaluation-protocol", 292, ["scripts/build_thesis_visuals_v04.py:evaluation-protocol"])
    d.box(18, 23, 178, 61, "Freeze corpus + policy", "Versioned test conditions")
    d.box(270, 23, 180, 61, "Group related needs", "Development / test split")
    d.box(524, 23, 178, 61, "Paired retrieval arms", "Same inputs per strategy", active=True)
    d.arrow([(196, 53), (270, 53)])
    d.arrow([(450, 53), (524, 53)])
    d.box(18, 159, 178, 59, "Retrieval metrics", "Hit@k / MRR@k")
    d.box(270, 159, 180, 59, "Semantic audit", "Intent / answer leakage")
    d.box(524, 159, 178, 59, "Provider ledger", "Calls / failures / costs")
    d.arrow([(613, 84), (613, 118), (107, 118), (107, 159)])
    d.arrow([(360, 118), (360, 159)])
    d.arrow([(613, 118), (613, 159)])
    d.box(197, 251, 326, 34, "Bounded conclusions · retain negative results", active=True)
    d.arrow([(107, 218), (107, 268), (197, 268)])
    d.arrow([(360, 218), (360, 251)])
    d.arrow([(613, 218), (613, 268), (523, 268)])
    d.save()


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    for fn in [architecture, ingestion, account, chunk, retrieval, question, supervisor, difficulty, exploration, lifecycle, review_export, evaluation]:
        fn()
    (OUT / "vector_provenance.json").write_text(json.dumps({
        "method": "New deterministic vector schematics authored from existing source specifications; no raster editing or model calls",
        "style_basis": "apple-design: purposeful hierarchy, typography, grouping, alignment, restraint; adapted to static academic figures",
        "scope": "Project diagrams only; actual screenshots, licensed literature figure and numerical experiment plots remain separate",
        "builder": "scripts/build_thesis_visuals_v05.py",
        "figures": MANIFEST,
    }, indent=2) + "\n")
    print(f"Built {len(MANIFEST)} PDF + PNG diagram pairs in {OUT}")


if __name__ == "__main__":
    build()
