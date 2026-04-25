import os
import webbrowser

import chromadb


def generate_html_dashboard():
    print("Generating doctor database dashboard...")

    db_path = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_collection(name="malaysia_doctors")
    results = collection.get()

    if not results or not results["metadatas"]:
        print("No data found in the database.")
        return

    # Calculate stats
    total_doctors = len(results["metadatas"])
    hospitals = set(meta.get("hospital", "Unknown") for meta in results["metadatas"])
    total_hospitals = len(hospitals)
    
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Medical AI - Doctor Vector Database</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Inter:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: #6366f1;
            --primary-dark: #4f46e5;
            --secondary: #ec4899;
            --accent: #8b5cf6;
            --background: #0f172a;
            --card-bg: rgba(30, 41, 59, 0.7);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --border: rgba(255, 255, 255, 0.1);
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Inter', sans-serif;
            background-color: var(--background);
            background-image: 
                radial-gradient(circle at 0% 0%, rgba(99, 102, 241, 0.15) 0%, transparent 50%),
                radial-gradient(circle at 100% 100%, rgba(236, 72, 153, 0.1) 0%, transparent 50%);
            color: var(--text-main);
            min-height: 100vh;
            padding: 40px 20px;
            line-height: 1.6;
        }}

        h1, h2, h3 {{
            font-family: 'Outfit', sans-serif;
            font-weight: 700;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        .header {{
            text-align: center;
            margin-bottom: 50px;
            animation: fadeInDown 0.8s ease-out;
        }}

        .header h1 {{
            font-size: 3rem;
            background: linear-gradient(to right, #818cf8, #f472b6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }}

        .header p {{
            color: var(--text-muted);
            font-size: 1.1rem;
            max-width: 600px;
            margin: 0 auto;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
            animation: fadeIn 1s ease-out;
        }}

        .stat-card {{
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border);
            padding: 24px;
            border-radius: 20px;
            text-align: center;
            transition: transform 0.3s ease;
        }}

        .stat-card:hover {{
            transform: translateY(-5px);
            border-color: rgba(99, 102, 241, 0.4);
        }}

        .stat-value {{
            display: block;
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--primary);
            font-family: 'Outfit', sans-serif;
        }}

        .stat-label {{
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
            font-size: 0.8rem;
            font-weight: 600;
        }}

        .search-container {{
            margin-bottom: 30px;
            position: relative;
            max-width: 500px;
            margin-left: auto;
            margin-right: auto;
        }}

        .search-input {{
            width: 100%;
            padding: 16px 24px;
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 30px;
            color: white;
            font-size: 1rem;
            outline: none;
            transition: all 0.3s ease;
            backdrop-filter: blur(12px);
        }}

        .search-input:focus {{
            border-color: var(--primary);
            box-shadow: 0 0 20px rgba(99, 102, 241, 0.2);
        }}

        .table-container {{
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border);
            border-radius: 24px;
            overflow: hidden;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.3);
            animation: fadeInUp 1s ease-out;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th {{
            background: rgba(255, 255, 255, 0.03);
            text-align: left;
            padding: 20px;
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 1px;
            border-bottom: 1px solid var(--border);
        }}

        td {{
            padding: 20px;
            border-bottom: 1px solid var(--border);
            vertical-align: middle;
        }}

        tr:last-child td {{
            border-bottom: none;
        }}

        tr:hover td {{
            background: rgba(255, 255, 255, 0.02);
        }}

        .doctor-name {{
            font-weight: 600;
            color: var(--text-main);
            display: block;
        }}

        .specialty {{
            color: var(--text-muted);
            font-size: 0.9rem;
        }}

        .hosp-badge {{
            background: rgba(99, 102, 241, 0.1);
            color: #818cf8;
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 0.8rem;
            font-weight: 500;
            border: 1px solid rgba(99, 102, 241, 0.2);
        }}

        .tier-badge {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .tier-premium {{
            background: rgba(236, 72, 153, 0.1);
            color: #f472b6;
            border: 1px solid rgba(236, 72, 153, 0.2);
        }}

        .tier-gov {{
            background: rgba(16, 185, 129, 0.1);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.2);
        }}

        .tier-standard {{
            background: rgba(245, 158, 11, 0.1);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.2);
        }}

        .mmc-link {{
            color: var(--primary);
            text-decoration: none;
            font-size: 0.85rem;
            font-weight: 500;
            transition: color 0.2s;
            display: flex;
            align-items: center;
            gap: 5px;
        }}

        .mmc-link:hover {{
            color: var(--secondary);
        }}

        .reg-info {{
            font-size: 0.75rem;
            color: var(--text-muted);
            font-family: monospace;
        }}

        @keyframes fadeInDown {{
            from {{ opacity: 0; transform: translateY(-20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        @keyframes fadeInUp {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; }}
            to {{ opacity: 1; }}
        }}

        @media (max-width: 768px) {{
            .stats-grid {{ grid-template-columns: 1fr; }}
            th:nth-child(4), td:nth-child(4),
            th:nth-child(5), td:nth-child(5) {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <h1>🩺 Doctor Registry</h1>
            <p>Live Vector Database from MMC MeRITS. Powering Malaysia's Medical Tourism Matching Engine.</p>
        </header>

        <div class="stats-grid">
            <div class="stat-card">
                <span class="stat-value">{total_doctors}</span>
                <span class="stat-label">Verified Doctors</span>
            </div>
            <div class="stat-card">
                <span class="stat-value">{total_hospitals}</span>
                <span class="stat-label">Active Hospitals</span>
            </div>
            <div class="stat-card">
                <span class="stat-value">Live</span>
                <span class="stat-label">Vector Sync</span>
            </div>
        </div>

        <div class="search-container">
            <input type="text" class="search-input" id="doctorSearch" placeholder="Search by name, hospital, or specialty..." onkeyup="filterTable()">
        </div>

        <div class="table-container">
            <table id="doctorTable">
                <thead>
                    <tr>
                        <th>Doctor Detail</th>
                        <th>Hospital</th>
                        <th>Foreigner Tier</th>
                        <th>Registration</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
    """

    for i in range(len(results["metadatas"])):
        meta = results["metadatas"][i]
        tier = meta.get("tier", "Standard Private")
        tier_class = "tier-standard"
        if "Premium" in tier: tier_class = "tier-premium"
        elif "Government" in tier: tier_class = "tier-gov"

        provisional = meta.get("provisional_registration_number", "N/A") or "N/A"
        full_reg = meta.get("full_registration_number", "N/A") or "N/A"
        mmc_url = meta.get("mmc_url", "#")

        html_content += f"""
                    <tr>
                        <td>
                            <span class="doctor-name">{meta.get('name', 'Unknown Doctor')}</span>
                            <span class="specialty">{meta.get('specialty', 'General Practitioner')}</span>
                        </td>
                        <td>
                            <span class="hosp-badge">{meta.get('hospital', 'Unknown Hospital')}</span>
                        </td>
                        <td>
                            <span class="tier-badge {tier_class}">{tier}</span>
                        </td>
                        <td class="reg-info">
                            PRN: {provisional}<br>
                            FRN: {full_reg}
                        </td>
                        <td>
                            <a href="{mmc_url}" target="_blank" class="mmc-link">
                                View Profile ↗
                            </a>
                        </td>
                    </tr>
        """

    html_content += """
                </tbody>
            </table>
        </div>
    </div>

    <script>
        function filterTable() {
            var input, filter, table, tr, td, i, txtValue;
            input = document.getElementById("doctorSearch");
            filter = input.value.toUpperCase();
            table = document.getElementById("doctorTable");
            tr = table.getElementsByTagName("tr");

            for (i = 1; i < tr.length; i++) {
                var match = false;
                var cells = tr[i].getElementsByTagName("td");
                for(var j=0; j < cells.length - 1; j++) {
                    if (cells[j]) {
                        txtValue = cells[j].textContent || cells[j].innerText;
                        if (txtValue.toUpperCase().indexOf(filter) > -1) {
                            match = true;
                            break;
                        }
                    }
                }
                if (match) {
                    tr[i].style.display = "";
                } else {
                    tr[i].style.display = "none";
                }
            }
        }
    </script>
</body>
</html>
    """

    output_file = os.path.join(os.path.dirname(__file__), "..", "reports", "db_dashboard.html")
    with open(output_file, "w", encoding="utf-8") as file_obj:
        file_obj.write(html_content)

    print(f"Dashboard generated at: {os.path.abspath(output_file)}")

    try:
        # webbrowser.open("file://" + os.path.abspath(output_file))
        print("Dashboard generated successfully.")
    except Exception as exc:
        print(f"Could not open browser automatically: {exc}")


if __name__ == "__main__":
    generate_html_dashboard()
