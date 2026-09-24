import os
import re
import markdown
from typing import List
from base64 import b64encode
from datetime import datetime


class PDFExporter:
    """
    Generates styled PDF reports from markdown content + images.
    Uses wkhtmltopdf. Design aligned with DataWise frontend.
    Styles are kept simple for reliable wkhtmltopdf rendering
    (no CSS gradients, minimal flex/grid).
    """

    WKHTMLTOPDF_PATH = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"

    # DataWise brand (matches frontend primary ~ indigo)
    PRIMARY = "#4F46E5"
    PRIMARY_DARK = "#312E81"
    PRIMARY_SOFT = "#EEF2FF"
    PRIMARY_BORDER = "#C7D2FE"
    FG = "#1E1B4B"
    MUTED = "#64748B"
    BORDER = "#E2E8F0"
    BG_SOFT = "#F8FAFC"

    @staticmethod
    def _find_wkhtmltopdf() -> str:
        possible_paths = [
            r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
            r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
            "/usr/local/bin/wkhtmltopdf",
            "/usr/bin/wkhtmltopdf",
            "/opt/homebrew/bin/wkhtmltopdf",
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return "wkhtmltopdf"

    @staticmethod
    def _escape_markdown_for_pdf(md_content: str) -> str:
        lines = md_content.split("\n")
        result_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("|") and stripped.endswith("|"):
                result_lines.append(line)
                continue
            if re.match(r"^\|[-:\s|]+\|$", stripped):
                result_lines.append(line)
                continue
            if "<" in line and ">" in line and re.search(r"<[^>]+>", line):
                result_lines.append(line)
                continue
            if re.match(r"^\s*>", line):
                line = re.sub(r"^(\s*)>", r"\1&amp;gt;", line)
            result_lines.append(line)
        return "\n".join(result_lines)

    @staticmethod
    def _build_styles() -> str:
        P = PDFExporter.PRIMARY
        PD = PDFExporter.PRIMARY_DARK
        PS = PDFExporter.PRIMARY_SOFT
        FG = PDFExporter.FG
        MU = PDFExporter.MUTED
        BD = PDFExporter.BORDER
        BG = PDFExporter.BG_SOFT
        return f"""
        @page {{
            size: A4;
            margin: 14mm 12mm 16mm 12mm;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            font-family: "Segoe UI", Arial, Helvetica, sans-serif;
            margin: 0;
            padding: 0;
            line-height: 1.45;
            color: {FG};
            font-size: 9.5pt;
            background: #ffffff;
        }}

        /* Header: solid color only (wkhtmltopdf does not render linear-gradient reliably) */
        .report-header {{
            background-color: {P};
            color: #ffffff;
            padding: 18px 20px 16px 20px;
            margin: 0 0 18px 0;
            border-radius: 8px;
        }}
        .report-header .brand {{
            font-size: 9px;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            font-weight: 600;
            opacity: 0.9;
            margin: 0 0 6px 0;
            color: #ffffff;
        }}
        .report-header h1 {{
            margin: 0 0 6px 0;
            padding: 0;
            border: none;
            font-size: 16pt;
            font-weight: 700;
            color: #ffffff;
            line-height: 1.25;
        }}
        .report-header .meta {{
            font-size: 9pt;
            color: #ffffff;
            opacity: 0.92;
            margin: 4px 0 0 0;
        }}
        .report-header .badge {{
            display: inline-block;
            margin-top: 10px;
            padding: 3px 10px;
            font-size: 8pt;
            font-weight: 600;
            color: #ffffff;
            border: 1px solid rgba(255,255,255,0.45);
            border-radius: 999px;
            background-color: rgba(255,255,255,0.12);
        }}

        h1 {{
            color: {PD};
            border-bottom: 2px solid {P};
            padding-bottom: 6px;
            font-size: 14pt;
            margin: 0 0 10px 0;
            font-weight: 700;
        }}
        h2 {{
            color: {PD};
            margin: 16px 0 6px 0;
            padding: 0 0 0 10px;
            border-left: 3px solid {P};
            font-size: 11.5pt;
            font-weight: 700;
            page-break-after: avoid;
        }}
        h3 {{
            color: {FG};
            margin: 12px 0 4px 0;
            font-size: 10pt;
            font-weight: 650;
            page-break-after: avoid;
        }}
        h4 {{
            color: {MU};
            margin: 8px 0 3px 0;
            font-size: 9pt;
            font-weight: 600;
        }}
        p {{ margin: 0 0 6px 0; }}
        ul, ol {{
            margin: 4px 0 8px 0;
            padding-left: 18px;
        }}
        li {{ margin-bottom: 2px; }}
        strong {{
            font-weight: 650;
            color: {FG};
        }}

        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 6px 0 12px 0;
            font-size: 8.5pt;
            border: 1px solid {BD};
            page-break-inside: auto;
        }}
        thead {{ display: table-header-group; }}
        th, td {{
            padding: 5px 8px;
            text-align: left;
            border-bottom: 1px solid {BD};
            vertical-align: top;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }}
        th {{
            background-color: {PS};
            color: {PD};
            font-weight: 650;
            font-size: 8pt;
        }}
        tr:nth-child(even) td {{
            background-color: {BG};
        }}
        tr:last-child td {{
            border-bottom: none;
        }}
        td {{ color: {FG}; }}
        td:last-child {{ max-width: 420px; }}

        hr {{
            border: none;
            border-top: 1px solid {BD};
            margin: 14px 0;
        }}
        img {{
            max-width: 100%;
            height: auto;
            margin: 8px 0;
            border: 1px solid {BD};
            border-radius: 6px;
            page-break-inside: avoid;
        }}
        code {{
            background-color: {BG};
            border: 1px solid {BD};
            padding: 1px 4px;
            border-radius: 3px;
            font-family: Consolas, "Courier New", monospace;
            font-size: 8pt;
            color: {PD};
        }}
        pre {{
            background-color: {BG};
            border: 1px solid {BD};
            padding: 8px 10px;
            border-radius: 6px;
            overflow-x: auto;
            font-size: 8pt;
            line-height: 1.4;
            margin: 6px 0;
        }}
        blockquote {{
            margin: 8px 0;
            padding: 6px 12px;
            border-left: 3px solid {P};
            background-color: {PS};
            color: {FG};
        }}
        h2 + *, h3 + * {{
            page-break-before: avoid;
        }}
        """

    @staticmethod
    def generate_report(
        output_path: str,
        content: str,
        image_paths: List[str],
        title: str = "Data Analysis Report",
    ) -> dict:
        """
        Generate PDF report from markdown content and image paths.

        Returns:
            dict: {"success": True, "path": str} or {"error": str}
        """
        try:
            import pdfkit
        except ImportError:
            return {
                "error": "pdfkit not installed. Run: pip install pdfkit",
                "fallback": "Save as HTML instead",
            }

        generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        md_content = ""
        if not content or not content.strip():
            md_content += "*No report content available.*\n"
        else:
            md_content += content + "\n"

        if image_paths:
            md_content += "\n---\n\n## Visualizations\n\n"
            for img_path in image_paths:
                if img_path and os.path.exists(img_path):
                    try:
                        with open(img_path, "rb") as f:
                            b64 = b64encode(f.read()).decode()
                        ext = os.path.splitext(img_path)[1].lower().replace(".", "")
                        if ext not in ("png", "jpg", "jpeg", "gif", "svg"):
                            ext = "png"
                        md_content += (
                            f'<img src="data:image/{ext};base64,{b64}" '
                            f'style="max-width:100%;margin:8px 0;border-radius:6px;" />\n\n'
                        )
                    except Exception:
                        md_content += f"*Image load failed: {img_path}*\n\n"

        md_content = PDFExporter._escape_markdown_for_pdf(md_content)

        html_body = markdown.markdown(
            md_content,
            extensions=["extra", "nl2br", "tables", "fenced_code"],
        )
        html_body = re.sub(r"\bNaN\b", "N/A", html_body)
        html_body = re.sub(r"\bInf\b|\b-Inf\b", "∞", html_body)

        styles = PDFExporter._build_styles()
        safe_title = (
            str(title)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

        # Solid background header (no gradient). Footer only via pdfkit options.
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{safe_title}</title>
    <style>
{styles}
    </style>
</head>
<body>
    <div class="report-header">
        <div class="brand">DataWise &middot; AI Analysis</div>
        <h1>{safe_title}</h1>
        <div class="meta">Generated {generated_at}</div>
        <div class="badge">Automated data analysis report</div>
    </div>
    {html_body}
</body>
</html>"""

        wk_path = PDFExporter._find_wkhtmltopdf()
        try:
            config = pdfkit.configuration(wkhtmltopdf=wk_path)
        except Exception:
            config = None

        options = {
            "page-size": "A4",
            "margin-top": "10mm",
            "margin-right": "10mm",
            "margin-bottom": "14mm",
            "margin-left": "10mm",
            "encoding": "UTF-8",
            "enable-local-file-access": "",
            "quiet": "",
            "print-media-type": "",
            "footer-right": "[page] / [topage]",
            "footer-left": "DataWise",
            "footer-font-size": "8",
            "footer-font-name": "Segoe UI",
            "footer-spacing": "5",
            "background": "",
            "no-stop-slow-scripts": "",
        }

        try:
            pdfkit.from_string(
                html,
                output_path,
                configuration=config,
                options=options,
            )
            return {
                "success": True,
                "path": output_path,
                "size_kb": (
                    round(os.path.getsize(output_path) / 1024, 2)
                    if os.path.exists(output_path)
                    else None
                ),
            }
        except Exception as e:
            html_path = output_path.replace(".pdf", ".html")
            try:
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html)
                return {
                    "error": f"PDF generation failed: {str(e)}",
                    "fallback_html": html_path,
                    "wkhtmltopdf_path": wk_path,
                }
            except Exception as e2:
                return {
                    "error": f"PDF and HTML generation both failed: {str(e2)}"
                }