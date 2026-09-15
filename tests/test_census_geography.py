import sys
import unittest
from pathlib import Path

import pandas as pd

# scripts/ is not a package, so put it on the path before importing
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import download_census as dc


class TestGeographyTags(unittest.TestCase):
    def test_msa_rows_join_on_their_own_code(self):
        df = pd.DataFrame({"NAME": ["Abilene, TX Metro Area"], dc.MSA_COL: ["10180"]})
        out = dc.tag_geography(df, "msa")
        self.assertEqual(out.geo_code.tolist(), ["10180"])
        self.assertEqual(out.geo_level.tolist(), ["msa"])
        self.assertEqual(out.parent_cbsa.tolist(), [""])

    def test_division_rows_join_on_the_division_code(self):
        df = pd.DataFrame({"NAME": ["Elgin, IL Metro Division"], dc.MSA_COL: ["16980"], dc.DIV_COL: ["20994"]})
        out = dc.tag_geography(df, "division")
        self.assertEqual(out.geo_code.tolist(), ["20994"])
        self.assertEqual(out.parent_cbsa.tolist(), ["16980"])

    # chicago's 2014 vintage code was 16974. fhfa uses 16984 for every year
    def test_crosswalk_maps_renamed_divisions(self):
        df = pd.DataFrame({dc.MSA_COL: ["16980", "16980"], dc.DIV_COL: ["16974", "20994"]})
        out = dc.tag_geography(df, "division")
        self.assertEqual(out.geo_code.tolist(), ["16984", "20994"])
        self.assertEqual(out[dc.DIV_COL].tolist(), ["16974", "20994"])  # the api column is untouched

    def test_input_frame_is_not_mutated(self):
        df = pd.DataFrame({dc.MSA_COL: ["16980"], dc.DIV_COL: ["16974"]})
        dc.tag_geography(df, "division")
        self.assertNotIn("geo_code", df.columns)

    # a parent with no divisions in an older vintage comes back as a header only
    def test_empty_frame(self):
        df = pd.DataFrame(columns=["NAME", dc.MSA_COL, dc.DIV_COL])
        out = dc.tag_geography(df, "division")
        self.assertEqual(len(out), 0)
        self.assertIn("geo_code", out.columns)

    def test_parents_and_crosswalk_are_well_formed(self):
        self.assertEqual(len(dc.DIVISION_PARENTS), 13)
        self.assertEqual(len(set(dc.DIVISION_PARENTS)), 13)
        codes = dc.DIVISION_PARENTS + list(dc.DIVISION_CROSSWALK) + list(dc.DIVISION_CROSSWALK.values())
        for code in codes:
            self.assertRegex(code, r"^\d{5}$")
        # an old code never maps to another old code
        self.assertFalse(set(dc.DIVISION_CROSSWALK) & set(dc.DIVISION_CROSSWALK.values()))


if __name__ == "__main__":
    unittest.main()
