"""
Builds the downloadable analysis report (proposal section 5.4): the answer,
supporting visuals, confidence, and the full execution trace, as one
self-contained HTML file. Images are embedded, so the file can be emailed
or archived on its own, and printed to PDF from any browser.
"""

import base64
import json
from html import escape

from backend.app.reporting.store import AnalysisRecord

_STYLE = """
body { font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
       color: #1a2230; max-width: 900px; margin: 32px auto; padding: 0 20px;
       line-height: 1.5; }
h1 { font-size: 22px; margin: 0 0 4px; color: #0b3d91; }
h2 { font-size: 15px; margin: 28px 0 8px; color: #0b3d91;
     border-bottom: 1px solid #d5dbe6; padding-bottom: 4px; }
.meta { color: #5b6677; font-size: 12px; }
.answer { background: #f3f6fb; border-left: 4px solid #0b3d91;
          padding: 12px 16px; font-size: 15px; }
table { border-collapse: collapse; width: 100%; font-size: 12px; }
th, td { border: 1px solid #d5dbe6; padding: 6px 8px; text-align: left;
         vertical-align: top; }
th { background: #eaf0fb; }
code { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 11px;
       word-break: break-word; }
img { max-width: 100%; border: 1px solid #d5dbe6; }
.note { color: #5b6677; font-size: 12px; }
.status-failed, .status-blocked { color: #b3261e; font-weight: 600; }
.status-warning, .status-stub { color: #9a6700; font-weight: 600; }
.status-complete { color: #1a7f37; }
"""


def _image_tag(data: bytes | None, alt: str) -> str:
    if not data:
        return ""

    encoded = base64.b64encode(data).decode("ascii")

    return f'<img alt="{escape(alt)}" src="data:image/png;base64,{encoded}">'


def _status_class(status: str) -> str:
    safe = "".join(ch for ch in status.lower() if ch.isalnum())

    return f"status-{safe}"


def build_report_html(
    record: AnalysisRecord,
    overlay_png: bytes | None = None,
    preview_png: bytes | None = None,
) -> str:
    response = record.response
    images = [name for name in (record.image_id, record.image_id_2) if name]

    parts = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        f"<title>SatQuery AI report {escape(record.analysis_id)}</title>",
        f"<style>{_STYLE}</style></head><body>",
        "<h1>SatQuery AI analysis report</h1>",
        '<div class="meta">',
        f"Analysis ID: <code>{escape(record.analysis_id)}</code><br>",
        f"Generated: {escape(record.created_at.strftime('%Y-%m-%d %H:%M UTC'))}<br>",
        f"Imagery: {escape(', '.join(images)) if images else 'none'}",
        "</div>",
        "<h2>Query</h2>",
        f"<p>{escape(response.query)}</p>",
        "<h2>Answer</h2>",
        f'<div class="answer">{escape(response.answer)}</div>',
        "<h2>Task and confidence</h2>",
        "<table>",
        f"<tr><th>Task</th><td>{escape(response.task.value)}</td></tr>",
        f"<tr><th>Confidence</th><td>{response.confidence:.0%}</td></tr>",
        "</table>",
        '<p class="note">Confidence values are model or heuristic scores. '
        "They have not been calibrated against ground truth.</p>",
    ]

    if overlay_png or preview_png:
        parts.append("<h2>Visual evidence</h2>")

        if overlay_png:
            parts.append(_image_tag(overlay_png, "Evidence overlay"))
        else:
            parts.append(_image_tag(preview_png, "Input image preview"))

    if response.evidence:
        parts.append("<h2>Evidence items</h2>")
        parts.append(
            "<table><tr><th>#</th><th>Kind</th><th>Label</th>"
            "<th>Box (x_min, y_min, x_max, y_max) px</th><th>Score</th></tr>"
        )

        for index, item in enumerate(response.evidence, start=1):
            box = (
                ", ".join(f"{value:.0f}" for value in item.bbox)
                if item.bbox
                else escape(item.mask_ref or "")
            )
            score = f"{item.score:.2f}" if item.score is not None else ""

            parts.append(
                f"<tr><td>{index}</td><td>{escape(item.kind)}</td>"
                f"<td>{escape(item.label or '')}</td><td>{box}</td>"
                f"<td>{score}</td></tr>"
            )

        parts.append("</table>")

    parts.append("<h2>Execution trace</h2>")
    parts.append(
        "<table><tr><th>#</th><th>Step</th><th>Status</th>"
        "<th>Tool</th><th>Parameters</th></tr>"
    )

    for index, step in enumerate(response.execution_trace, start=1):
        params = (
            f"<code>{escape(json.dumps(step.params, default=str))}</code>"
            if step.params
            else ""
        )

        parts.append(
            f"<tr><td>{index}</td><td>{escape(step.step)}</td>"
            f'<td class="{_status_class(step.status)}">{escape(step.status)}</td>'
            f"<td>{escape(step.tool or '')}</td><td>{params}</td></tr>"
        )

    parts.append("</table></body></html>")

    return "\n".join(parts)
