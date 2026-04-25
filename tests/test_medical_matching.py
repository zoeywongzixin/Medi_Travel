import unittest

from agents.medical_agent import rank_doctor_matches
from pipeline.ingest_doctors import build_doctor_profile


MMC_DETAIL_HTML = """
<fieldset class="scheduler-border">
    <div id="div-full-name" class="form-group row">
        <label class="col-sm-4 bold" for="LIM CHIN CHYE">Full Name</label>
        <div class="col-sm-6">LIM CHIN CHYE</div>
    </div>
    <div id="div-qualification" class="form-group row">
        <label class="col-sm-4 bold" for="MBBS">Qualification</label>
        <div class="col-sm-6">BACHELOR OF MEDICINE AND BACHELOR OF SURGERY</div>
    </div>
    <div id="div-graduated-of" class="form-group row">
        <label class="col-sm-4 bold" for="UNIVERSITI MALAYA">Graduated of</label>
        <div class="col-sm-6">UNIVERSITI MALAYA</div>
    </div>
    <div id="div-provisional-registration-number" class="form-group row">
        <label class="col-sm-4 bold" for="14883">Provisional Registration Number</label>
        <div class="col-sm-6">14883</div>
    </div>
    <div id="div-full-registration-number" class="form-group row">
        <label class="col-sm-4 bold" for="25605">Full Registration Number</label>
        <div class="col-sm-6">25605</div>
    </div>
    <table>
        <tbody>
            <tr>
                <td>1</td>
                <td>2020</td>
                <td>20008</td>
                <td>JABATAN RADIOTERAPI &amp; ONKOLOGI, INSTITUT KANSER NEGARA<br/>PUTRAJAYA</td>
                <td>SEMUA FASILITI DI BAWAH KEMENTERIAN KESIHATAN MALAYSIA</td>
            </tr>
        </tbody>
    </table>
</fieldset>
"""


class MedicalMatchingTests(unittest.TestCase):
    def test_build_doctor_profile_extracts_name_and_registration_numbers(self):
        profile = build_doctor_profile(
            {
                "name": "LIM CHIN CHYE",
                "graduated_from": "UNIVERSITI MALAYA",
                "detail_url": "https://merits.mmc.gov.my/viewDoctor/17721/search",
                "matched_query": "ONKOLOGI",
            },
            MMC_DETAIL_HTML,
        )

        self.assertEqual(profile["name"], "LIM CHIN CHYE")
        self.assertEqual(profile["provisional_registration_number"], "14883")
        self.assertEqual(profile["full_registration_number"], "25605")
        self.assertEqual(profile["hospital"], "INSTITUT KANSER NEGARA")
        self.assertEqual(profile["specialty"], "Radiation Oncology")

    def test_lung_cancer_ranking_filters_out_cardiology_match(self):
        medical_data = {
            "condition": "Lung Cancer",
            "sub_specialty_inference": "Medical Oncology",
            "severity": "High",
            "is_cardio_oncology": False,
        }
        candidates = [
            {
                "name": "Cardio Doctor",
                "hospital": "Heart Centre",
                "specialty": "Cardiology",
                "specialty_tags": "Cardiology",
                "rag_summary": "Doctor Name: Cardio Doctor\nSub-Specialty: Cardiology\nAffiliated Hospital: Heart Centre",
                "provisional_registration_number": "11111",
                "full_registration_number": "22222",
                "mmc_url": "https://merits.mmc.gov.my/viewDoctor/1/search",
                "primary_practice": "JABATAN KARDIOLOGI, HEART CENTRE",
            },
            {
                "name": "Oncology Doctor",
                "hospital": "Institut Kanser Negara",
                "specialty": "Medical Oncology",
                "specialty_tags": "Medical Oncology, Radiation Oncology",
                "rag_summary": "Doctor Name: Oncology Doctor\nSub-Specialty: Medical Oncology\nAffiliated Hospital: Institut Kanser Negara",
                "provisional_registration_number": "33333",
                "full_registration_number": "44444",
                "mmc_url": "https://merits.mmc.gov.my/viewDoctor/2/search",
                "primary_practice": "JABATAN RADIOTERAPI & ONKOLOGI, INSTITUT KANSER NEGARA",
            },
        ]

        ranked = rank_doctor_matches(medical_data, candidates, limit=2)

        self.assertEqual(ranked[0]["name"], "Oncology Doctor")
        self.assertGreater(ranked[0]["match_score"], ranked[1]["match_score"])


if __name__ == "__main__":
    unittest.main()
