"""
Charity Fund Dashboard Generator
=================================
Generates a rich HTML dashboard from the ChromaDB 'charities' RAG collection.
Data is read once from local ChromaDB — no network calls made here.

Usage:
    python pipeline/generate_charity_dashboard.py
"""

import os
import sys
from pathlib import Path
from collections import Counter

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from agents.charity_agent import get_all_charities, collection_count


def generate_charity_dashboard():
    print("Generating charity fund dashboard...")

    charities = get_all_charities()
    if not charities:
        print("No charity data in ChromaDB. Run: python pipeline/ingest_charities.py")
        return

    # ── Stats ──────────────────────────────────────────────────────────────
    total = len(charities)
    sources = Counter(c.get("source", "Unknown") for c in charities)
    all_countries = []
    for c in charities:
        all_countries.extend(c.get("target_countries", []))
    country_counts = Counter(all_countries)
    unique_countries = len(country_counts)
    orgs = len({c.get("organization", "") for c in charities})
    laos_count = sum(1 for c in charities if "Laos" in c.get("target_countries", []))

    source_pills = "".join(
        f'<span class="src-pill src-{s.lower().split("/")[0].strip().replace(" ", "-")}">'
        f'{s}: {n}</span>'
        for s, n in sorted(sources.items(), key=lambda x: -x[1])
    )

    # ── Build table rows ────────────────────────────────────────────────────
    rows_html = ""
    for c in charities:
        name = c.get("name", "Unknown")
        org = c.get("organization", "Unknown Org")
        source = c.get("source", "")
        origin = c.get("origin_country", "—")
        targets = c.get("target_countries", [])
        conditions = c.get("conditions_covered", [])
        coverage = c.get("max_coverage_usd", 0)
        url = c.get("url", "")

        # Source badge colour
        src_class = "src-globalgiving" if "GlobalGiving" in source and "IATI" not in source else \
                    "src-iati" if "IATI" in source else "src-seed"

        # Country tags (limit to 4 shown)
        shown = targets[:4]
        more = len(targets) - 4
        country_tags = "".join(f'<span class="tag tag-country">{t}</span>' for t in shown)
        if more > 0:
            country_tags += f'<span class="tag tag-more">+{more}</span>'

        # Condition tags (limit to 3)
        cond_shown = conditions[:3]
        cond_tags = "".join(f'<span class="tag tag-cond">{cond}</span>' for cond in cond_shown)
        if len(conditions) > 3:
            cond_tags += f'<span class="tag tag-more">+{len(conditions)-3}</span>'

        link_html = f'<a href="{url}" target="_blank" class="ext-link">Apply &#x2197;</a>' if url else "—"

        rows_html += f"""
            <tr>
                <td>
                    <span class="fund-name">{name}</span>
                    <span class="fund-org">{org}</span>
                </td>
                <td><span class="src-badge {src_class}">{source}</span></td>
                <td class="origin-cell">{origin}</td>
                <td>{country_tags}</td>
                <td>{cond_tags}</td>
                <td class="coverage-cell">USD {coverage:,}</td>
                <td>{link_html}</td>
            </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ASEAN Charity Fund Registry | Medical Matching</title>
    <meta name="description" content="Live charity and fund database for ASEAN medical tourism matching — powered by GlobalGiving and IATI.">
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg:          #0a0f1e;
            --surface:     #111827;
            --card:        rgba(17,24,39,0.8);
            --border:      rgba(255,255,255,0.08);
            --purple:      #8b5cf6;
            --purple-glow: rgba(139,92,246,0.25);
            --teal:        #14b8a6;
            --rose:        #f43f5e;
            --amber:       #f59e0b;
            --text:        #f1f5f9;
            --muted:       #94a3b8;
        }}
        *, *::before, *::after {{ margin:0; padding:0; box-sizing:border-box; }}

        body {{
            font-family: 'Inter', sans-serif;
            background: var(--bg);
            background-image:
                radial-gradient(ellipse 80% 40% at 20% 0%, rgba(139,92,246,0.12) 0%, transparent 60%),
                radial-gradient(ellipse 60% 30% at 80% 100%, rgba(20,184,166,0.08) 0%, transparent 60%);
            color: var(--text);
            min-height: 100vh;
            padding: 40px 24px 80px;
        }}

        h1, h2, h3 {{ font-family: 'Outfit', sans-serif; }}

        /* ── Header ─────────────────────────────────────── */
        .header {{
            text-align: center;
            margin-bottom: 48px;
            animation: fadeDown .7s ease-out;
        }}
        .header h1 {{
            font-size: 2.8rem;
            font-weight: 800;
            background: linear-gradient(135deg, #a78bfa, #38bdf8, #34d399);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }}
        .header p {{ color: var(--muted); font-size: 1rem; }}
        .header .source-pills {{ margin-top: 14px; display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; }}

        /* ── Stat cards ─────────────────────────────────── */
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            gap: 16px;
            max-width: 1300px;
            margin: 0 auto 40px;
            animation: fadeUp .8s ease-out;
        }}
        .stat {{
            background: var(--card);
            backdrop-filter: blur(10px);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 24px 20px;
            text-align: center;
            transition: transform .25s, border-color .25s;
        }}
        .stat:hover {{ transform: translateY(-4px); border-color: var(--purple); }}
        .stat-value {{
            display: block;
            font-family: 'Outfit', sans-serif;
            font-size: 2.2rem;
            font-weight: 700;
            background: linear-gradient(135deg, #a78bfa, #38bdf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .stat-label {{
            color: var(--muted);
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
            margin-top: 4px;
            display: block;
        }}
        .stat-laos .stat-value {{
            background: linear-gradient(135deg, #f59e0b, #ef4444);
            -webkit-background-clip: text;
        }}

        /* ── Toolbar ────────────────────────────────────── */
        .toolbar {{
            max-width: 1300px;
            margin: 0 auto 20px;
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            align-items: center;
        }}
        .search-wrap {{ flex: 1; min-width: 220px; position: relative; }}
        .search-wrap svg {{
            position: absolute; left: 14px; top: 50%; transform: translateY(-50%);
            width: 16px; height: 16px; color: var(--muted);
        }}
        #fundSearch {{
            width: 100%;
            padding: 12px 16px 12px 40px;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 30px;
            color: var(--text);
            font-size: .95rem;
            outline: none;
            transition: border-color .2s, box-shadow .2s;
        }}
        #fundSearch:focus {{ border-color: var(--purple); box-shadow: 0 0 0 3px var(--purple-glow); }}

        select.filter {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 30px;
            color: var(--text);
            padding: 12px 20px;
            font-size: .9rem;
            outline: none;
            cursor: pointer;
            transition: border-color .2s;
        }}
        select.filter:focus {{ border-color: var(--purple); }}

        .toolbar-count {{
            color: var(--muted);
            font-size: .85rem;
            white-space: nowrap;
        }}

        /* ── Table ──────────────────────────────────────── */
        .table-wrap {{
            max-width: 1300px;
            margin: 0 auto;
            background: var(--card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border);
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 24px 60px rgba(0,0,0,.4);
            animation: fadeUp .9s ease-out;
        }}
        table {{ width: 100%; border-collapse: collapse; }}
        thead th {{
            padding: 16px 18px;
            background: rgba(255,255,255,.03);
            color: var(--muted);
            font-size: .72rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
            border-bottom: 1px solid var(--border);
            text-align: left;
            white-space: nowrap;
        }}
        tbody tr {{
            transition: background .15s;
            border-bottom: 1px solid var(--border);
        }}
        tbody tr:last-child {{ border-bottom: none; }}
        tbody tr:hover {{ background: rgba(139,92,246,.05); }}
        tbody td {{ padding: 14px 18px; vertical-align: middle; }}

        .fund-name {{
            display: block;
            font-weight: 600;
            font-size: .92rem;
            color: var(--text);
            line-height: 1.4;
        }}
        .fund-org {{
            display: block;
            font-size: .78rem;
            color: var(--muted);
            margin-top: 2px;
        }}

        /* Source badges */
        .src-badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: .72rem;
            font-weight: 600;
            white-space: nowrap;
        }}
        .src-globalgiving {{
            background: rgba(139,92,246,.15);
            color: #a78bfa;
            border: 1px solid rgba(139,92,246,.25);
        }}
        .src-iati {{
            background: rgba(20,184,166,.12);
            color: #2dd4bf;
            border: 1px solid rgba(20,184,166,.25);
        }}
        .src-seed {{
            background: rgba(245,158,11,.12);
            color: #fbbf24;
            border: 1px solid rgba(245,158,11,.25);
        }}

        /* Source pills in header */
        .src-pill {{
            padding: 5px 14px;
            border-radius: 20px;
            font-size: .8rem;
            font-weight: 600;
        }}
        .src-pill.src-globalgiving {{ background: rgba(139,92,246,.2); color: #a78bfa; }}
        .src-pill.src-iati {{ background: rgba(20,184,166,.2); color: #2dd4bf; }}
        .src-pill.src-iati---globalgiving {{ background: rgba(20,184,166,.2); color: #2dd4bf; }}
        .src-pill.src-seed {{ background: rgba(245,158,11,.2); color: #fbbf24; }}

        .origin-cell {{
            font-size: .85rem;
            color: var(--muted);
            white-space: nowrap;
        }}

        /* Tags */
        .tag {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 5px;
            font-size: .72rem;
            font-weight: 500;
            margin: 2px 2px 2px 0;
        }}
        .tag-country {{
            background: rgba(56,189,248,.1);
            color: #38bdf8;
            border: 1px solid rgba(56,189,248,.2);
        }}
        .tag-cond {{
            background: rgba(244,63,94,.1);
            color: #fb7185;
            border: 1px solid rgba(244,63,94,.2);
        }}
        .tag-more {{
            background: rgba(255,255,255,.06);
            color: var(--muted);
        }}

        .coverage-cell {{
            font-family: 'Outfit', monospace;
            font-weight: 600;
            font-size: .88rem;
            color: #34d399;
            white-space: nowrap;
        }}

        .ext-link {{
            color: var(--purple);
            text-decoration: none;
            font-size: .83rem;
            font-weight: 500;
            transition: color .2s;
            white-space: nowrap;
        }}
        .ext-link:hover {{ color: #38bdf8; }}

        /* Empty state */
        #emptyState {{
            display: none;
            padding: 60px 20px;
            text-align: center;
            color: var(--muted);
        }}
        #emptyState svg {{ width: 48px; height: 48px; opacity: .3; margin-bottom: 12px; }}

        /* Animations */
        @keyframes fadeDown {{ from {{ opacity:0; transform:translateY(-16px); }} to {{ opacity:1; transform:none; }} }}
        @keyframes fadeUp   {{ from {{ opacity:0; transform:translateY(16px);  }} to {{ opacity:1; transform:none; }} }}

        /* Responsive */
        @media (max-width: 900px) {{
            thead th:nth-child(4), tbody td:nth-child(4),
            thead th:nth-child(5), tbody td:nth-child(5) {{ display: none; }}
        }}
        @media (max-width: 600px) {{
            .header h1 {{ font-size: 2rem; }}
            thead th:nth-child(3), tbody td:nth-child(3) {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>&#127973; ASEAN Charity Fund Registry</h1>
        <p>Persistent RAG database powering the Medical Tourism Matching Engine &mdash; no re-scraping at query time.</p>
        <div class="source-pills">{source_pills}</div>
    </div>

    <div class="stats">
        <div class="stat">
            <span class="stat-value">{total:,}</span>
            <span class="stat-label">Total Funds</span>
        </div>
        <div class="stat">
            <span class="stat-value">{orgs:,}</span>
            <span class="stat-label">Organizations</span>
        </div>
        <div class="stat">
            <span class="stat-value">{unique_countries}</span>
            <span class="stat-label">ASEAN Countries</span>
        </div>
        <div class="stat stat-laos">
            <span class="stat-value">{laos_count}</span>
            <span class="stat-label">Laos-Specific Funds</span>
        </div>
        <div class="stat">
            <span class="stat-value">RAG</span>
            <span class="stat-label">Query Mode</span>
        </div>
    </div>

    <div class="toolbar">
        <div class="search-wrap">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input type="text" id="fundSearch" placeholder="Search fund, org, country, condition..." oninput="filterTable()">
        </div>
        <select class="filter" id="countryFilter" onchange="filterTable()">
            <option value="">All Countries</option>
            {chr(10).join(f'            <option value="{c}">{c} ({n})</option>' for c, n in sorted(country_counts.items(), key=lambda x: -x[1]) if n > 0)}
        </select>
        <select class="filter" id="sourceFilter" onchange="filterTable()">
            <option value="">All Sources</option>
            {chr(10).join(f'            <option value="{s}">{s}</option>' for s in sorted(sources.keys()))}
        </select>
        <span class="toolbar-count" id="rowCount">{total:,} funds</span>
    </div>

    <div class="table-wrap">
        <table id="charityTable">
            <thead>
                <tr>
                    <th>Fund / Organization</th>
                    <th>Source</th>
                    <th>Origin</th>
                    <th>Beneficiary Countries</th>
                    <th>Conditions Covered</th>
                    <th>Max Coverage</th>
                    <th>Link</th>
                </tr>
            </thead>
            <tbody id="tableBody">
                {rows_html}
            </tbody>
        </table>
        <div id="emptyState">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <p>No funds match your filters.</p>
        </div>
    </div>

    <script>
        const rows = Array.from(document.querySelectorAll('#tableBody tr'));
        const rowCount = document.getElementById('rowCount');
        const emptyState = document.getElementById('emptyState');

        function filterTable() {{
            const search = document.getElementById('fundSearch').value.toLowerCase();
            const country = document.getElementById('countryFilter').value.toLowerCase();
            const source = document.getElementById('sourceFilter').value.toLowerCase();

            let visible = 0;
            rows.forEach(row => {{
                const text = row.textContent.toLowerCase();
                const matchSearch = !search || text.includes(search);
                const matchCountry = !country || text.includes(country);
                const matchSource = !source || text.includes(source);
                const show = matchSearch && matchCountry && matchSource;
                row.style.display = show ? '' : 'none';
                if (show) visible++;
            }});

            rowCount.textContent = visible.toLocaleString() + ' funds';
            emptyState.style.display = visible === 0 ? 'block' : 'none';
        }}

        // Animate rows on load
        rows.forEach((row, i) => {{
            row.style.opacity = '0';
            row.style.transform = 'translateY(8px)';
            setTimeout(() => {{
                row.style.transition = 'opacity .3s ease, transform .3s ease';
                row.style.opacity = '1';
                row.style.transform = 'none';
            }}, i * 6);
        }});
    </script>
</body>
</html>"""

    reports_dir = ROOT_DIR / "reports"
    reports_dir.mkdir(exist_ok=True)
    output = reports_dir / "charity_dashboard.html"
    output.write_text(html, encoding="utf-8")
    print(f"Dashboard saved: {output.resolve()}")
    print(f"Records shown  : {total}")


if __name__ == "__main__":
    generate_charity_dashboard()
