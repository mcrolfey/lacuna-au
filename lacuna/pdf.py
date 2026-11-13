"""Render findings as a PDF report."""
from datetime import date
from html import escape
from pathlib import Path

from fpdf import FPDF

# (regular, bold, italic) font files to try, Windows first.
FONT_CANDIDATES = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/ariali.ttf"),
    ("C:/Windows/Fonts/calibri.ttf", "C:/Windows/Fonts/calibrib.ttf", "C:/Windows/Fonts/calibrii.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf", "/Library/Fonts/Arial Italic.ttf"),
]
SEVERITY_COLOUR = {"high": "#B42318", "medium": "#B54708", "low": "#475467"}


class _Report(FPDF):
    title_text = ""

    def footer(self):
        self.set_y(-12)
        self.set_font(self.font_family, size=8)
        self.set_text_color(120)
        self.cell(0, 8, f"{self.title_text}  |  page {self.page_no()}/{{nb}}", align="C")


def _setup_font(pdf: FPDF) -> bool:
    """Register a Unicode TTF font. Returns False if only the built-in font is available."""
    for regular, bold, italic in FONT_CANDIDATES:
        if Path(regular).exists() and Path(bold).exists():
            pdf.add_font("body", "", regular)
            pdf.add_font("body", "B", bold)
            pdf.add_font("body", "I", italic if Path(italic).exists() else regular)
            pdf.add_font("body", "BI", bold)
            return True
    return False


def _latin1(text: str) -> str:
    swaps = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
             "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u00a7": "s "}
    for a, b in swaps.items():
        text = text.replace(a, b)
    return text.encode("latin-1", "replace").decode("latin-1")


def write_pdf(path: Path, topic: str, kept: list[dict], rejected: int, sections: dict) -> Path:
    title = topic.replace("_", " ").title()
    pdf = _Report(format="A4")
    pdf.title_text = f"Lacuna AU: {title}"
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(True, margin=18)
    unicode_ok = _setup_font(pdf)
    family = "body" if unicode_ok else "helvetica"
    pdf.set_font(family, size=10)
    pdf.add_page()

    h = [f"<h1>{escape(title)}: findings</h1>",
         f"<p><i>Generated {date.today()} by local models. Not legal advice; every item "
         "needs checking by a person against the current law.</i></p>",
         f"<p><b>{len(kept)}</b> findings kept, <b>{rejected}</b> rejected by the verifier.</p>"]
    for agent, heading in sections.items():
        group = [f for f in kept if f["agent"] == agent]
        h.append(f"<h2>{escape(heading)} ({len(group)})</h2>")
        if not group:
            h.append("<p><i>No findings.</i></p>")
        for f in group:
            sev = str(f.get("severity", ""))
            colour = SEVERITY_COLOUR.get(sev, "#475467")
            h.append(f"<h3>{escape(str(f['title']))}</h3>")
            h.append(f'<p><font color="{colour}"><b>Severity: {escape(sev)}</b></font>'
                     f" | Confidence: {escape(str(f.get('confidence') or 'n/a'))}"
                     f" | Verifier: {escape(str(f['verdict']))}</p>")
            h.append(f"<p>{escape(str(f.get('summary', '')))}</p>")
            if f.get("provisions"):
                h.append("<p><b>Provisions:</b> "
                         + escape("; ".join(map(str, f["provisions"]))) + "</p>")
            if f.get("sources"):
                h.append("<ul>" + "".join(
                    f'<li><a href="{escape(s["url"])}">{escape(str(s["citation"]))}</a>'
                    f" ({escape(str(s['jurisdiction']))})</li>" for s in f["sources"]) + "</ul>")
            h.append(f"<p><i>Verifier: {escape(str(f['verdict_reason']))}</i></p>")
            if f.get("question"):
                h.append(f"<p><i>Question: {escape(str(f['question']))}</i></p>")
            h.append("<br>")

    html = "\n".join(h)
    pdf.write_html(html if unicode_ok else _latin1(html), font_family=family)
    pdf.output(str(path))
    return path
