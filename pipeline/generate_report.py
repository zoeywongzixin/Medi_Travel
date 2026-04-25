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

    html_content = """
    <html>
    <head>
        <title>Medical AI - Doctor Database</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; padding: 20px; }
            h1 { color: #2c3e50; text-align: center; }
            .subtitle { text-align: center; color: #7f8c8d; margin-bottom: 30px; }
            table { width: 100%; border-collapse: collapse; background-color: white; box-shadow: 0 1px 3px rgba(0,0,0,0.2); }
            th, td { padding: 15px; text-align: left; border-bottom: 1px solid #ddd; vertical-align: top; }
            th { background-color: #1f4e79; color: white; }
            tr:hover { background-color: #f5f5f5; }
            .hosp-badge { background-color: #2980b9; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; display: inline-block; }
            .tier-badge { background-color: #16a085; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; display: inline-block; }
            .reg-badge { background-color: #34495e; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; display: inline-block; margin-bottom: 6px; }
        </style>
    </head>
    <body>
        <h1>MMC Doctor Vector Database (ChromaDB)</h1>
        <div class="subtitle">Doctor names, registration numbers, and specialty-focused matching</div>
        <table>
            <tr>
                <th>Doctor Name</th>
                <th>Sub-Specialty</th>
                <th>Hospital Affiliation</th>
                <th>Registration</th>
                <th>Foreigner Tier</th>
                <th>MMC Profile</th>
            </tr>
    """

    for i in range(len(results["metadatas"])):
        meta = results["metadatas"][i]
        provisional = meta.get("provisional_registration_number", "N/A") or "N/A"
        full_reg = meta.get("full_registration_number", "N/A") or "N/A"
        mmc_url = meta.get("mmc_url", "")

        html_content += f"""
            <tr>
                <td><strong>{meta.get('name', 'N/A')}</strong></td>
                <td>{meta.get('specialty', 'N/A')}</td>
                <td><span class="hosp-badge">{meta.get('hospital', 'N/A')}</span></td>
                <td>
                    <div class="reg-badge">PRN: {provisional}</div><br>
                    <div class="reg-badge">FRN: {full_reg}</div>
                </td>
                <td><span class="tier-badge">{meta.get('tier', 'N/A')}</span></td>
                <td><a href="{mmc_url}" target="_blank">Open MMC profile</a></td>
            </tr>
        """

    html_content += """
        </table>
    </body>
    </html>
    """

    output_file = os.path.join(os.path.dirname(__file__), "..", "reports", "db_dashboard.html")
    with open(output_file, "w", encoding="utf-8") as file_obj:
        file_obj.write(html_content)

    print(f"Dashboard generated at: {os.path.abspath(output_file)}")

    try:
        webbrowser.open("file://" + os.path.abspath(output_file))
        print("Opening in your web browser...")
    except Exception as exc:
        print(f"Could not open browser automatically: {exc}")


if __name__ == "__main__":
    generate_html_dashboard()
