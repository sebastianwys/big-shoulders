import hashlib
import io
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from bot import build_map_data
from bot.collectors import irs

# autauga county is the real 2021 to 2022 header block. elmore is invented.
# the same state and different state rows, the foreign row, the non-migrant
# row and the flow rows must all be ignored
INFLOW_TEXT = (
    "y2_statefips,y2_countyfips,y1_statefips,y1_countyfips,y1_state,y1_countyname,n1,n2,agi\n"
    "1,1,96,0,AL,Autauga County Total Migration-US and Foreign,2105,4580,133082\n"
    "1,1,97,0,AL,Autauga County Total Migration-US,2076,4489,130188\n"
    "1,1,97,1,AL,Autauga County Total Migration-Same State,1315,2612,69328\n"
    "1,1,97,3,AL,Autauga County Total Migration-Different State,761,1877,60861\n"
    "1,1,98,0,AL,Autauga County Total Migration-Foreign,29,91,2894\n"
    "1,1,1,1,AL,Autauga County Non-migrants,19346,41562,1413939\n"
    "1,1,1,51,AL,Elmore County,475,935,23050\n"
    "1,1,58,0,SS,Other flows - Same State,224,409,12147\n"
    "1,51,97,0,AL,Elmore County Total Migration-US,3120,6400,201000\n"
    "1,51,1,1,AL,Autauga County,463,909,25789\n"
)

OUTFLOW_TEXT = (
    "y1_statefips,y1_countyfips,y2_statefips,y2_countyfips,y2_state,y2_countyname,n1,n2,agi\n"
    "1,1,96,0,AL,Autauga County Total Migration-US and Foreign,1945,4124,123796\n"
    "1,1,97,0,AL,Autauga County Total Migration-US,1923,4040,121248\n"
    "1,1,97,1,AL,Autauga County Total Migration-Same State,1241,2443,68239\n"
    "1,1,97,3,AL,Autauga County Total Migration-Different State,682,1597,53009\n"
    "1,1,98,0,AL,Autauga County Total Migration-Foreign,22,84,2547\n"
    "1,1,1,1,AL,Autauga County Non-migrants,19346,41562,1413939\n"
    "1,1,57,9,FR,Foreign - Other flows,-1,-1,-1\n"
    "1,51,97,0,AL,Elmore County Total Migration-US,2900,5900,180000\n"
)

# the older files zero pad every code and open with state totals (county 000)
PADDED_INFLOW_TEXT = (
    "y2_statefips,y2_countyfips,y1_statefips,y1_countyfips,y1_state,y1_countyname,n1,n2,agi\n"
    "01,000,96,000,AL,Total Migration-US and Foreign,80346,163579,3387101\n"
    "01,000,97,000,AL,Total Migration-US,79498,161479,3339022\n"
    "01,001,97,000,AL,Autauga County Total Migration-US,2076,4489,130188\n"
    "01,051,97,000,AL,Elmore County Total Migration-US,3120,6400,201000\n"
)

# hand computed from the fixtures
AUTAUGA_NET_RETURNS = 2076 - 1923
AUTAUGA_NET_EXEMPTIONS = 4489 - 4040
ELMORE_NET_RETURNS = 3120 - 2900
ELMORE_NET_EXEMPTIONS = 6400 - 5900

HEADER = ["CBSA Code", "Metropolitan Division Code", "CSA Code", "CBSA Title",
          "Metropolitan/Micropolitan Statistical Area", "Metropolitan Division Title", "CSA Title",
          "County/County Equivalent", "State Name", "FIPS State Code", "FIPS County Code",
          "Central/Outlying County"]


def totals(text, kind):
    return irs.parse_totals(text.encode(), kind)


# autauga and elmore share a cbsa, cook sits in a cbsa and a division
def crosswalk():
    return pd.DataFrame({
        "county_fips": ["01001", "01051", "17031", "17031", "48441"],
        "cbsa_code": ["33860", "33860", "16980", "16984", "10180"],
    })


# a workbook shaped like list1_2023.xlsx: two title rows, the header, county
# rows, then the note rows the census bureau appends
def workbook(rows):
    frame = pd.DataFrame(rows, columns=HEADER)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, startrow=2, sheet_name="List 1")
        writer.sheets["List 1"]["A1"] = "List 1. Core based statistical areas, July 2023"
    return buffer.getvalue()


def county_row(cbsa, division, county, state_fips, county_fips):
    return [cbsa, division, None, "Title", "Metropolitan Statistical Area", None, None,
            county, "State", state_fips, county_fips, "Central"]


class TestParseTotals(unittest.TestCase):
    def test_keeps_one_total_us_row_per_county(self):
        df = totals(INFLOW_TEXT, "inflow")
        self.assertEqual(list(df.columns), irs.TOTAL_COLUMNS)
        self.assertEqual(df.county_fips.tolist(), ["01001", "01051"])
        autauga = df[df.county_fips == "01001"].iloc[0]
        self.assertEqual((int(autauga.n1), int(autauga.n2)), (2076, 4489))

    def test_outflow_reads_the_origin_side(self):
        df = totals(OUTFLOW_TEXT, "outflow")
        self.assertEqual(df.county_fips.tolist(), ["01001", "01051"])
        self.assertEqual(int(df[df.county_fips == "01001"].n1.iloc[0]), 1923)

    def test_values_are_integer_dtype(self):
        df = totals(INFLOW_TEXT, "inflow")
        self.assertEqual(df.n1.dtype.kind, "i")
        self.assertEqual(df.n2.dtype.kind, "i")

    # 1415 through 1920 pad the codes, 2021 and 2122 do not
    def test_leading_zero_fips_matches_bare_fips(self):
        padded = totals(PADDED_INFLOW_TEXT, "inflow")
        bare = totals(INFLOW_TEXT, "inflow")
        self.assertEqual(padded.county_fips.tolist(), bare.county_fips.tolist())
        self.assertEqual(padded.n1.tolist(), bare.n1.tolist())

    def test_state_total_rows_are_excluded(self):
        df = totals(PADDED_INFLOW_TEXT, "inflow")
        self.assertNotIn("01000", df.county_fips.tolist())
        self.assertEqual(len(df), 2)

    def test_suppressed_total_is_dropped(self):
        text = INFLOW_TEXT.replace("Elmore County Total Migration-US,3120,6400,201000",
                                   "Elmore County Total Migration-US,-1,-1,-1")
        df = totals(text, "inflow")
        self.assertEqual(df.county_fips.tolist(), ["01001"])

    def test_repeated_total_row_counts_once(self):
        text = INFLOW_TEXT + "1,51,97,0,AL,Elmore County Total Migration-US,3120,6400,201000\n"
        df = totals(text, "inflow")
        self.assertEqual(df.county_fips.tolist(), ["01001", "01051"])

    def test_empty_file(self):
        for content in (b"", INFLOW_TEXT.split("\n", 1)[0].encode() + b"\n"):
            df = irs.parse_totals(content, "inflow")
            self.assertEqual(list(df.columns), irs.TOTAL_COLUMNS)
            self.assertEqual(len(df), 0)

    def test_utf8_bom_is_tolerated(self):
        df = irs.parse_totals(b"\xef\xbb\xbf" + INFLOW_TEXT.encode(), "inflow")
        self.assertEqual(len(df), 2)

    def test_wrong_columns_raise(self):
        with self.assertRaises(ValueError):
            irs.parse_totals(b"a,b,c\n1,2,3\n", "inflow")


class TestCountyNet(unittest.TestCase):
    def test_autauga_net_by_hand(self):
        net = irs.county_net(totals(INFLOW_TEXT, "inflow"), totals(OUTFLOW_TEXT, "outflow"))
        row = net[net.county_fips == "01001"].iloc[0]
        self.assertEqual(int(row.irs_net_returns), AUTAUGA_NET_RETURNS)
        self.assertEqual(int(row.irs_net_returns), 153)
        self.assertEqual(int(row.irs_net_exemptions), AUTAUGA_NET_EXEMPTIONS)
        self.assertEqual(int(row.irs_net_exemptions), 449)
        self.assertEqual(int(row.irs_inflow_returns), 2076)
        self.assertEqual(int(row.irs_outflow_returns), 1923)

    def test_columns(self):
        net = irs.county_net(totals(INFLOW_TEXT, "inflow"), totals(OUTFLOW_TEXT, "outflow"))
        self.assertEqual(list(net.columns), ["county_fips"] + irs.METRICS)

    # a county missing from one file cannot be netted, so it is dropped from
    # every metric rather than counted as zero on the missing side
    def test_inflow_without_outflow_is_dropped(self):
        outflow = OUTFLOW_TEXT.replace("1,51,97,0,AL,Elmore County Total Migration-US,2900,5900,180000\n", "")
        net = irs.county_net(totals(INFLOW_TEXT, "inflow"), totals(outflow, "outflow"))
        self.assertEqual(net.county_fips.tolist(), ["01001"])

    def test_both_sides_empty(self):
        net = irs.county_net(irs.parse_totals(b"", "inflow"), irs.parse_totals(b"", "outflow"))
        self.assertEqual(len(net), 0)
        self.assertEqual(list(net.columns), ["county_fips"] + irs.METRICS)


class TestAggregate(unittest.TestCase):
    def net(self, inflow=INFLOW_TEXT, outflow=OUTFLOW_TEXT):
        return irs.county_net(totals(inflow, "inflow"), totals(outflow, "outflow"))

    def value(self, out, code, metric):
        rows = out[(out.cbsa_code == code) & (out.metric == metric)]
        self.assertEqual(len(rows), 1)
        return int(rows.value.iloc[0])

    def test_two_county_cbsa_sums_by_hand(self):
        out = irs.aggregate(self.net(), crosswalk(), "2022")
        self.assertEqual(self.value(out, "33860", "irs_net_returns"),
                         AUTAUGA_NET_RETURNS + ELMORE_NET_RETURNS)
        self.assertEqual(self.value(out, "33860", "irs_net_returns"), 373)
        self.assertEqual(self.value(out, "33860", "irs_net_exemptions"),
                         AUTAUGA_NET_EXEMPTIONS + ELMORE_NET_EXEMPTIONS)
        self.assertEqual(self.value(out, "33860", "irs_net_exemptions"), 949)
        self.assertEqual(self.value(out, "33860", "irs_inflow_returns"), 2076 + 3120)
        self.assertEqual(self.value(out, "33860", "irs_outflow_returns"), 1923 + 2900)

    def test_net_equals_inflow_minus_outflow(self):
        out = irs.aggregate(self.net(), crosswalk(), "2022")
        self.assertEqual(self.value(out, "33860", "irs_net_returns"),
                         self.value(out, "33860", "irs_inflow_returns")
                         - self.value(out, "33860", "irs_outflow_returns"))

    def test_map_contract_columns_and_types(self):
        out = irs.aggregate(self.net(), crosswalk(), "2022")
        self.assertEqual(list(out.columns), irs.COLUMNS)
        self.assertEqual(set(out.period), {"2022"})
        self.assertEqual(out.value.dtype.kind, "i")
        self.assertEqual(set(out.metric), set(irs.METRICS))
        self.assertEqual(set(out.cbsa_code), {"33860"})

    def test_metric_names_are_not_reserved(self):
        self.assertFalse(set(irs.METRICS) & build_map_data.RESERVED)
        for metric in irs.METRICS:
            self.assertTrue(metric.startswith("irs_"))
            self.assertEqual(metric, metric.lower())

    def test_county_in_no_cbsa_is_ignored(self):
        inflow = INFLOW_TEXT + "48,301,97,0,TX,Loving County Total Migration-US,40,60,1000\n"
        outflow = OUTFLOW_TEXT + "48,301,97,0,TX,Loving County Total Migration-US,10,20,500\n"
        out = irs.aggregate(self.net(inflow, outflow), crosswalk(), "2022")
        self.assertEqual(set(out.cbsa_code), {"33860"})
        self.assertEqual(self.value(out, "33860", "irs_net_returns"), 373)

    def test_county_in_cbsa_and_division_feeds_both(self):
        inflow = INFLOW_TEXT + "17,31,97,0,IL,Cook County Total Migration-US,90000,150000,9000000\n"
        outflow = OUTFLOW_TEXT + "17,31,97,0,IL,Cook County Total Migration-US,120000,200000,12000000\n"
        out = irs.aggregate(self.net(inflow, outflow), crosswalk(), "2022")
        for code in ("16980", "16984"):
            self.assertEqual(self.value(out, code, "irs_net_returns"), -30000)
            self.assertEqual(self.value(out, code, "irs_net_exemptions"), -50000)
            self.assertEqual(self.value(out, code, "irs_inflow_returns"), 90000)

    # elmore alone in its cbsa and missing from the outflow file: no row at all
    def test_cbsa_with_no_usable_county_gets_no_row(self):
        outflow = OUTFLOW_TEXT.replace("1,51,97,0,AL,Elmore County Total Migration-US,2900,5900,180000\n", "")
        walk = pd.DataFrame({"county_fips": ["01001", "01051"], "cbsa_code": ["33860", "99999"]})
        out = irs.aggregate(self.net(outflow=outflow), walk, "2022")
        self.assertEqual(set(out.cbsa_code), {"33860"})
        self.assertEqual(self.value(out, "33860", "irs_net_returns"), AUTAUGA_NET_RETURNS)

    def test_empty_input_gives_empty_frame_with_columns(self):
        empty = irs.county_net(irs.parse_totals(b"", "inflow"), irs.parse_totals(b"", "outflow"))
        out = irs.aggregate(empty, crosswalk(), "2015")
        self.assertEqual(list(out.columns), irs.COLUMNS)
        self.assertEqual(len(out), 0)

    def test_output_loads_through_the_builder(self):
        out = irs.aggregate(self.net(), crosswalk(), "2022")
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "irs"
            folder.mkdir()
            out.to_csv(folder / "metrics.csv", index=False)
            loaded = build_map_data.load_enrichment(folder / "metrics.csv")
        self.assertEqual(loaded["name"], "irs")
        self.assertEqual(loaded["metrics"], sorted(irs.METRICS))
        annual, latest = build_map_data.enrich_values(loaded["groups"]["33860"])
        self.assertEqual(annual[("irs_net_returns", 2022)], 373.0)
        self.assertEqual(latest["irs_net_returns"], ("2022", 373.0))


class TestCrosswalk(unittest.TestCase):
    def rows(self):
        return [
            county_row("10180", None, "Callahan County", "48", "059"),
            county_row("16980", "16984", "Cook County", "17", "031"),
            county_row("33860", None, "Autauga County", "1", "1"),
            ["Note: OMB standards are at a url", None, None, None, None, None, None, None, None, None, None, None],
            ["Source: File prepared by U.S. Census Bureau", None, None, None, None, None, None, None, None, None, None, None],
        ]

    def test_every_county_maps_to_its_cbsa_and_divisions_add_a_row(self):
        walk = irs.parse_crosswalk(workbook(self.rows()))
        self.assertEqual(list(walk.columns), ["county_fips", "cbsa_code"])
        pairs = set(zip(walk.county_fips, walk.cbsa_code))
        self.assertEqual(pairs, {("48059", "10180"), ("17031", "16980"), ("17031", "16984"), ("01001", "33860")})
        self.assertEqual(len(walk), 4)

    def test_bare_fips_are_zero_padded(self):
        walk = irs.parse_crosswalk(workbook(self.rows()))
        self.assertIn("01001", walk.county_fips.tolist())

    def test_note_rows_are_dropped(self):
        walk = irs.parse_crosswalk(workbook(self.rows()))
        self.assertFalse(walk.cbsa_code.str.startswith("Note").any())
        self.assertFalse(walk.cbsa_code.str.startswith("Source").any())


class TestHelpers(unittest.TestCase):
    def test_pair_label_and_period(self):
        self.assertEqual(irs.pair_label(2014), "1415")
        self.assertEqual(irs.pair_label(2022), "2223")
        self.assertEqual(irs.pair_label(2099), "9900")
        self.assertEqual(irs.period_of(2014), "2015")
        self.assertEqual(irs.period_of(2022), "2023")

    def test_file_note_hashes_and_counts_rows(self):
        content = b"h1,h2\n1,2\n3,4\n"
        note = irs.file_note("countyinflow1415.csv", "https://example.test/x.csv", content)
        self.assertEqual(note["sha256"], hashlib.sha256(content).hexdigest())
        self.assertEqual(note["row_count"], 2)
        self.assertEqual(note["size_kb"], round(len(content) / 1024, 1))
        self.assertEqual(note["filename"], "countyinflow1415.csv")

    def test_file_note_without_trailing_newline_and_empty(self):
        self.assertEqual(irs.file_note("f", "u", b"h1,h2\n1,2")["row_count"], 1)
        self.assertEqual(irs.file_note("f", "u", b"")["row_count"], 0)


if __name__ == "__main__":
    unittest.main()
