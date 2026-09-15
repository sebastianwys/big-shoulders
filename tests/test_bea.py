import io
import json
import os
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest import mock

import pandas as pd
import requests

from bot import build_map_data as bm
from bot.collectors import bea

# every payload in this file is synthetic. it copies the documented shape of a
# BEAAPI response (Results.Data rows carrying GeoFips, GeoName, TimePeriod,
# DataValue with commas, CL_UNIT and UNIT_MULT) with invented numbers. nothing
# here was fetched from the api, and no test opens the network
FAKE_KEY = "0000AAAA-1111-2222-3333-444455556666"
UNITS = {"1": ("Thousands of dollars", "3"), "3": ("Dollars", "0")}
ABILENE = "Abilene, TX (Metropolitan Statistical Area)"
CHICAGO = "Chicago-Naperville-Elgin, IL-IN-WI (Metropolitan Statistical Area)"


def row(fips, period, value, line="1", name=ABILENE):
    unit, mult = UNITS[line]
    return {"Code": f"CAINC1-{line}", "GeoFips": fips, "GeoName": name, "TimePeriod": period,
            "CL_UNIT": unit, "UNIT_MULT": mult, "DataValue": value}


def payload(rows, line="1", key=FAKE_KEY):
    return {"BEAAPI": {
        "Request": {"RequestParam": [
            {"ParameterName": "USERID", "ParameterValue": key},
            {"ParameterName": "METHOD", "ParameterValue": "GETDATA"},
            {"ParameterName": "TABLENAME", "ParameterValue": "CAINC1"},
            {"ParameterName": "LINECODE", "ParameterValue": line},
        ]},
        "Results": {
            "Statistic": "Personal income" if line == "1" else "Per capita personal income",
            "UnitOfMeasure": UNITS[line][0],
            "PublicTable": "CAINC1 Personal Income Summary: Personal Income, Population, Per Capita Personal Income",
            "UTCProductionTime": "2026-01-01T00:00:00.000",
            "Dimensions": [
                {"Name": "GeoFips", "DataType": "string", "IsValue": "0"},
                {"Name": "TimePeriod", "DataType": "string", "IsValue": "0"},
                {"Name": "DataValue", "DataType": "numeric", "IsValue": "1"},
            ],
            "Data": rows,
            "Notes": [{"NoteRef": "1", "NoteText": "synthetic fixture"}],
        },
    }}


def line_codes(descs=None):
    descs = descs or {
        "1": "[CAINC1] Personal income (thousands of dollars)",
        "2": "[CAINC1] Population (persons) 1/",
        "3": "[CAINC1] Per capita personal income (dollars) 2/",
    }
    return {"BEAAPI": {
        "Request": {"RequestParam": [{"ParameterName": "USERID", "ParameterValue": FAKE_KEY}]},
        "Results": {"ParamValue": [{"Key": k, "Desc": v} for k, v in descs.items()]},
    }}


INCOME_ROWS = [
    row("10180", "2013", "6,900,000"),
    row("10180", "2014", "7,116,829"),
    row("10180", "2019", "8,412,003"),
    row("10180", "2024", "10,250,441"),
    row("16980", "2014", "512,345,678", name=CHICAGO),
    row("16980", "2024", "701,234,567", name=CHICAGO),
    row("00998", "2024", "19,000,000,000", name="United States (Metropolitan Portion)"),
]
PER_CAPITA_ROWS = [
    row("10180", "2014", "42,573", line="3"),
    row("10180", "2024", "57,120", line="3"),
    row("16980", "2024", "74,905", line="3", name=CHICAGO),
]


class FakeResponse:
    def __init__(self, body, status=200, json_ok=True):
        self.status_code = status
        self.ok = status < 400
        self._body = body
        self._json_ok = json_ok

    def json(self):
        if not self._json_ok:
            raise ValueError("not json")
        return self._body


# routes a request to a canned response by method, or by line code for GetData
def fake_fetch(responses, calls):
    def fetch(url, params=None, **kwargs):
        calls.append(dict(params))
        which = params["LineCode"] if params["method"] == "GetData" else params["method"]
        item = responses[which]
        if isinstance(item, Exception):
            raise item
        return item
    return fetch


def good_responses():
    return {
        "GetParameterValues": FakeResponse(line_codes()),
        "1": FakeResponse(payload(INCOME_ROWS, "1")),
        "3": FakeResponse(payload(PER_CAPITA_ROWS, "3")),
    }


class TestBeaParse(unittest.TestCase):
    def test_documented_columns_and_exact_values(self):
        df = bea.parse_data(INCOME_ROWS, "bea_personal_income")
        self.assertEqual(list(df.columns), ["cbsa_code", "metric", "period", "value"])
        abilene = df[(df.cbsa_code == "10180") & (df.period == "2014")].iloc[0]
        self.assertEqual(abilene.value, 7116829.0)
        self.assertEqual(abilene.metric, "bea_personal_income")
        self.assertEqual(dict(zip(df[df.cbsa_code == "16980"].period, df[df.cbsa_code == "16980"].value)),
                         {"2014": 512345678.0, "2024": 701234567.0})

    def test_per_capita_values(self):
        df = bea.parse_data(PER_CAPITA_ROWS, "bea_income_per_capita")
        self.assertEqual(len(df), 3)
        self.assertEqual(df[(df.cbsa_code == "10180") & (df.period == "2024")].value.iloc[0], 57120.0)
        self.assertEqual(set(df.metric), {"bea_income_per_capita"})

    # 2013 is before the study window and 00998 is the national metro portion
    def test_old_years_and_national_portions_are_dropped(self):
        df = bea.parse_data(INCOME_ROWS, "bea_personal_income")
        self.assertEqual(len(df), 5)
        self.assertNotIn("2013", df.period.tolist())
        self.assertNotIn("00998", df.cbsa_code.tolist())

    def test_first_year_is_a_parameter(self):
        df = bea.parse_data(INCOME_ROWS, "bea_personal_income", first_year=2020)
        self.assertEqual(df.period.tolist(), ["2024", "2024"])

    def test_values_are_numeric_and_periods_are_strings(self):
        df = bea.parse_data(INCOME_ROWS, "bea_personal_income")
        self.assertEqual(df.value.dtype.kind, "f")
        self.assertTrue(all(isinstance(p, str) and len(p) == 4 for p in df.period))

    def test_rows_sorted_by_code_then_period(self):
        df = bea.parse_data(list(reversed(INCOME_ROWS)), "bea_personal_income")
        self.assertEqual(list(zip(df.cbsa_code, df.period)),
                         [("10180", "2014"), ("10180", "2019"), ("10180", "2024"), ("16980", "2014"), ("16980", "2024")])

    # bea flags suppressed or unavailable cells in parentheses
    def test_missing_values_are_skipped(self):
        df = bea.parse_data([
            row("10180", "2014", "(NA)"), row("10180", "2015", "(D)"), row("10180", "2016", ""),
            row("10180", "2017", None), row("10180", "2018", "5"),
        ], "bea_personal_income")
        self.assertEqual(list(zip(df.period, df.value)), [("2018", 5.0)])

    def test_empty_data_yields_the_documented_columns(self):
        df = bea.parse_data([], "bea_personal_income")
        self.assertEqual(list(df.columns), ["cbsa_code", "metric", "period", "value"])
        self.assertEqual(len(df), 0)
        self.assertEqual(bea.data_rows({"Data": []}), [])
        self.assertEqual(bea.data_rows({}), [])

    def test_single_row_object_is_treated_as_a_list(self):
        rows = bea.data_rows({"Data": row("10180", "2024", "1")})
        self.assertEqual(len(rows), 1)
        self.assertEqual(bea.parse_data(rows, "m").cbsa_code.tolist(), ["10180"])

    def test_a_year_with_no_data_is_simply_absent(self):
        df = bea.parse_data([row("10180", "2019", "1"), row("10180", "2024", "2")], "m")
        self.assertEqual(df.period.tolist(), ["2019", "2024"])

    def test_duplicates_keep_the_first_value(self):
        df = bea.parse_data([row("10180", "2024", "1"), row("10180", "2024", "2"), row("10180", "2024", "(NA)")], "m")
        self.assertEqual(list(zip(df.period, df.value)), [("2024", 1.0)])

    def test_leading_zero_code_is_kept(self):
        df = bea.parse_data([row("01234", "2024", "1")], "m")
        self.assertEqual(df.cbsa_code.tolist(), ["01234"])

    def test_suffixed_and_padded_geofips_normalize(self):
        for fips in ("10180", "10180M", " 10180 ", "10180-1", "101800"):
            self.assertEqual(bea.cbsa_code(fips), "10180", fips)

    def test_bad_geofips_yield_none(self):
        for fips in (None, "", "abc", "1018", "00998", "00999", "00000", "MSA"):
            self.assertIsNone(bea.cbsa_code(fips), repr(fips))

    def test_malformed_rows_are_skipped(self):
        rows = [
            {"GeoName": ABILENE, "TimePeriod": "2024", "DataValue": "1"},
            {"GeoFips": "10180", "DataValue": "1"},
            row("10180", "2024Q1", "1"),
            row("10180", "24", "1"),
            row("10180", "2024", "n/a"),
            row("abc", "2024", "1"),
            "not a row",
            None,
            row("10180", "2024", "9"),
        ]
        df = bea.parse_data(rows, "m")
        self.assertEqual(list(zip(df.cbsa_code, df.period, df.value)), [("10180", "2024", 9.0)])

    def test_parse_value(self):
        self.assertEqual(bea.parse_value("7,116,829"), 7116829.0)
        self.assertEqual(bea.parse_value("45,123"), 45123.0)
        self.assertEqual(bea.parse_value(" 1.5 "), 1.5)
        self.assertEqual(bea.parse_value(12), 12.0)
        for text in ("(NA)", "(D)", "(L)", "", "   ", None, "n/a", "nan", "inf"):
            self.assertIsNone(bea.parse_value(text), repr(text))

    def test_period_year(self):
        self.assertEqual(bea.period_year("2024"), 2024)
        self.assertEqual(bea.period_year(" 2019 "), 2019)
        for text in ("2024Q1", "24", "", None, "2024-01"):
            self.assertIsNone(bea.period_year(text), repr(text))


class TestBeaResults(unittest.TestCase):
    def test_results_block_is_returned(self):
        block = bea.results(payload(INCOME_ROWS))
        self.assertEqual(len(block["Data"]), len(INCOME_ROWS))

    def test_top_level_error_raises(self):
        body = {"BEAAPI": {"Request": {}, "Error": {"APIErrorCode": "3", "APIErrorDescription": "invalid user id"}}}
        with self.assertRaises(RuntimeError) as ctx:
            bea.results(body)
        self.assertIn("invalid user id", str(ctx.exception))

    def test_error_inside_results_raises(self):
        body = {"BEAAPI": {"Results": {"Error": {"APIErrorCode": "40", "APIErrorDescription": "bad table"}}}}
        with self.assertRaises(RuntimeError):
            bea.results(body)

    def test_results_list_is_unwrapped(self):
        body = {"BEAAPI": {"Results": [{"Data": [row("10180", "2024", "1")]}]}}
        self.assertEqual(len(bea.results(body)["Data"]), 1)

    def test_missing_beaapi_raises(self):
        for body in ({}, {"other": 1}, "text", None, {"BEAAPI": "oops"}):
            with self.assertRaises(RuntimeError):
                bea.results(body)


class TestBeaLineCodes(unittest.TestCase):
    def test_documented_line_codes_pass(self):
        descs = bea.verify_line_codes(bea.results(line_codes())["ParamValue"])
        self.assertEqual(set(descs), {"1", "3"})
        self.assertIn("Per capita", descs["3"])

    # line 1 must be the total, not the per capita figure, and the other way round
    def test_swapped_descriptions_raise(self):
        swapped = {"1": "[CAINC1] Per capita personal income (dollars)", "3": "[CAINC1] Personal income (thousands of dollars)"}
        with self.assertRaises(RuntimeError) as ctx:
            bea.verify_line_codes(bea.results(line_codes(swapped))["ParamValue"])
        self.assertIn("line 1", str(ctx.exception))
        self.assertIn("line 3", str(ctx.exception))

    def test_missing_line_raises(self):
        with self.assertRaises(RuntimeError) as ctx:
            bea.verify_line_codes([{"Key": "1", "Desc": "[CAINC1] Personal income (thousands of dollars)"}])
        self.assertIn("line 3", str(ctx.exception))

    def test_empty_list_raises(self):
        with self.assertRaises(RuntimeError):
            bea.verify_line_codes([])

    # the regional dataset lists every table's lines with the same keys, so a
    # foreign table's line 1 must neither pass nor fail the check
    def test_other_tables_lines_are_ignored(self):
        values = [
            {"Key": "1", "Desc": "[CAGDP2] All industry total"},
            {"Key": "3", "Desc": "[SAINC1] Per capita personal income (dollars)"},
            {"Key": "1", "Desc": "[CAINC1] Personal income (thousands of dollars)"},
            {"Key": "3", "Desc": "[CAINC1] Per capita personal income (dollars) 2/"},
            {"Key": "1", "Desc": "[CAINC4] Personal income (thousands of dollars)"},
        ]
        descs = bea.verify_line_codes(values)
        self.assertEqual(descs["1"], "[CAINC1] Personal income (thousands of dollars)")
        self.assertEqual(descs["3"], "[CAINC1] Per capita personal income (dollars) 2/")

    def test_only_other_tables_present_raises(self):
        with self.assertRaises(RuntimeError):
            bea.verify_line_codes([{"Key": "1", "Desc": "[CAINC4] Personal income (thousands of dollars)"}])

    def test_untagged_descriptions_still_count(self):
        descs = bea.verify_line_codes([
            {"Key": "1", "Desc": "Personal income (thousands of dollars)"},
            {"Key": "3", "Desc": "Per capita personal income (dollars)"},
        ])
        self.assertEqual(set(descs), {"1", "3"})

    def test_single_param_object_is_accepted(self):
        with self.assertRaises(RuntimeError) as ctx:
            bea.verify_line_codes({"Key": "3", "Desc": "[CAINC1] Per capita personal income (dollars)"})
        self.assertIn("line 1", str(ctx.exception))
        self.assertNotIn("line 3", str(ctx.exception))


class TestBeaUnits(unittest.TestCase):
    def test_expected_multipliers_pass(self):
        bea.check_units(INCOME_ROWS, "1")
        bea.check_units(PER_CAPITA_ROWS, "3")

    def test_changed_multiplier_raises(self):
        rows = [dict(row("10180", "2024", "7"), UNIT_MULT="6")]
        with self.assertRaises(RuntimeError) as ctx:
            bea.check_units(rows, "1")
        self.assertIn("UNIT_MULT", str(ctx.exception))

    def test_missing_multiplier_is_tolerated(self):
        bea.check_units([{"GeoFips": "10180", "TimePeriod": "2024", "DataValue": "7"}], "1")
        bea.check_units([], "3")


class TestBeaFiles(unittest.TestCase):
    def test_redact_removes_the_key_in_any_case(self):
        text = f"url: /api/data?UserID={FAKE_KEY.lower()}&x=1 and {FAKE_KEY}"
        out = bea.redact(text, FAKE_KEY)
        self.assertNotIn(FAKE_KEY.lower(), out.lower())
        self.assertEqual(out.count("REDACTED"), 2)

    def test_redact_with_no_key_leaves_text_alone(self):
        self.assertEqual(bea.redact("plain", ""), "plain")
        self.assertEqual(bea.redact(RuntimeError("boom"), None), "boom")

    def test_trim_payload_drops_old_rows_and_keeps_metadata(self):
        original = payload(INCOME_ROWS)
        trimmed = bea.trim_payload(original)
        self.assertEqual(len(trimmed["BEAAPI"]["Results"]["Data"]), 6)
        self.assertEqual(trimmed["BEAAPI"]["Results"]["Notes"], original["BEAAPI"]["Results"]["Notes"])
        self.assertEqual(len(original["BEAAPI"]["Results"]["Data"]), len(INCOME_ROWS))

    def test_write_metrics_whole_numbers_and_leading_zeros_survive(self):
        df = pd.DataFrame({"cbsa_code": ["01234", "10180"], "metric": ["m", "m"],
                           "period": ["2024", "2024"], "value": [7116829.0, 1.5]})
        with tempfile.TemporaryDirectory() as tmp:
            path = bea.write_metrics(df, Path(tmp) / "metrics.csv")
            text = path.read_text()
            back = pd.read_csv(path, dtype={"cbsa_code": str})
        self.assertEqual(text.splitlines()[0], "cbsa_code,metric,period,value")
        self.assertIn("01234,m,2024,7116829", text)
        self.assertNotIn("7116829.0", text)
        self.assertEqual(back.cbsa_code.tolist(), ["01234", "10180"])
        self.assertEqual(back.value.tolist(), [7116829.0, 1.5])


class TestBeaCollect(unittest.TestCase):
    def run_collect(self, responses, key=FAKE_KEY):
        calls = []
        with ExitStack() as stack:
            tmp = Path(stack.enter_context(tempfile.TemporaryDirectory()))
            out_dir = tmp / "bea"
            stack.enter_context(mock.patch.dict(os.environ, {"BEA_API_KEY": key}))
            stack.enter_context(mock.patch.object(bea, "OUT_DIR", out_dir))
            stack.enter_context(mock.patch.object(bea, "PAUSE_SECONDS", 0))
            stack.enter_context(mock.patch.object(bea, "fetch", fake_fetch(responses, calls)))
            output = io.StringIO()
            with redirect_stdout(output):
                result = bea.collect()
            files = {p.name: p.read_text() for p in out_dir.glob("*")} if out_dir.exists() else {}
        return result, calls, output.getvalue(), files

    def test_no_key_skips_without_touching_the_network(self):
        def never(*args, **kwargs):
            raise AssertionError("fetch must not run without a key")
        result, calls, text, files = self.run_collect({"GetParameterValues": never}, key="")
        self.assertIsNone(result)
        self.assertIn("skipping", text)
        self.assertEqual(text.count("\n"), 1)
        self.assertEqual(calls, [])
        self.assertEqual(files, {})

    def test_whitespace_key_counts_as_unset(self):
        result, calls, text, files = self.run_collect(good_responses(), key="   ")
        self.assertIsNone(result)
        self.assertEqual(calls, [])

    def test_collect_writes_metrics_manifest_and_redacted_raw(self):
        result, calls, text, files = self.run_collect(good_responses())
        self.assertEqual(result.name, "metrics.csv")
        self.assertEqual(set(files), {"metrics.csv", "download_manifest.json", "linecodes.json",
                                      "cainc1_line1.json", "cainc1_line3.json"})

        metrics = pd.read_csv(io.StringIO(files["metrics.csv"]), dtype={"cbsa_code": str, "period": str})
        self.assertEqual(list(metrics.columns), ["cbsa_code", "metric", "period", "value"])
        self.assertEqual(len(metrics), 8)
        abi = metrics[metrics.cbsa_code == "10180"].set_index(["metric", "period"]).value
        self.assertEqual(abi[("bea_personal_income", "2014")], 7116829.0)
        self.assertEqual(abi[("bea_income_per_capita", "2024")], 57120.0)
        self.assertIn("10180,bea_personal_income,2014,7116829\n", files["metrics.csv"])

        manifest = json.loads(files["download_manifest.json"])
        self.assertEqual(manifest[0]["filename"], "metrics.csv")
        self.assertEqual(manifest[0]["version"], "CAINC1 2014 through 2024")
        self.assertEqual(manifest[0]["integrity"]["row_count"], 8)
        self.assertEqual(manifest[0]["notes"]["cbsa_codes"], 2)
        self.assertEqual(manifest[0]["notes"]["metrics"]["bea_personal_income"]["unit"], "Thousands of dollars")
        self.assertEqual([m["filename"] for m in manifest[1:]], ["linecodes.json", "cainc1_line1.json", "cainc1_line3.json"])

        raw = json.loads(files["cainc1_line1.json"])
        self.assertEqual(len(raw["BEAAPI"]["Results"]["Data"]), 6)
        for name, body in files.items():
            self.assertNotIn(FAKE_KEY.lower(), body.lower(), name)
        self.assertIn("REDACTED", files["linecodes.json"])
        self.assertNotIn(FAKE_KEY.lower(), text.lower())

    def test_requests_carry_the_key_and_the_documented_parameters(self):
        _, calls, _, _ = self.run_collect(good_responses())
        self.assertEqual([c["method"] for c in calls], ["GetParameterValues", "GetData", "GetData"])
        for call in calls:
            self.assertEqual((call["UserID"], call["datasetname"], call["ResultFormat"]), (FAKE_KEY, "Regional", "json"))
        self.assertEqual((calls[0]["ParameterName"], calls[0]["TableName"]), ("LineCode", "CAINC1"))
        for call, line in zip(calls[1:], ["1", "3"]):
            self.assertEqual((call["TableName"], call["LineCode"], call["GeoFips"], call["Year"]),
                             ("CAINC1", line, "MSA", "ALL"))

    def test_one_line_is_printed_per_fetched_file(self):
        _, _, text, _ = self.run_collect(good_responses())
        lines = [l for l in text.splitlines() if l.startswith("[bea]")]
        self.assertTrue(any("linecodes.json" in l for l in lines))
        self.assertTrue(any("cainc1_line1.json" in l for l in lines))
        self.assertTrue(any("cainc1_line3.json" in l for l in lines))
        self.assertTrue(lines[-1].endswith("metrics.csv"))

    # a requests error carries the full url, key included, in its message
    def test_connection_error_never_carries_the_key(self):
        responses = good_responses()
        responses["1"] = requests.ConnectionError(f"Max retries exceeded with url: /api/data?UserID={FAKE_KEY}&method=GetData")
        with self.assertRaises(RuntimeError) as ctx:
            self.run_collect(responses)
        self.assertNotIn(FAKE_KEY.lower(), str(ctx.exception).lower())
        self.assertIn("REDACTED", str(ctx.exception))
        self.assertIsNone(ctx.exception.__cause__)

    def test_api_error_stops_the_run_without_the_key(self):
        responses = good_responses()
        responses["GetParameterValues"] = FakeResponse({"BEAAPI": {"Error": {
            "APIErrorCode": "3", "APIErrorDescription": f"The BEA API UserID provided is not valid: {FAKE_KEY}"}}})
        with self.assertRaises(RuntimeError) as ctx:
            self.run_collect(responses)
        self.assertIn("not valid", str(ctx.exception))
        self.assertNotIn(FAKE_KEY.lower(), str(ctx.exception).lower())

    def test_http_error_status_raises(self):
        responses = good_responses()
        responses["3"] = FakeResponse({}, status=429)
        with self.assertRaises(RuntimeError) as ctx:
            self.run_collect(responses)
        self.assertIn("429", str(ctx.exception))

    def test_non_json_body_raises(self):
        responses = good_responses()
        responses["1"] = FakeResponse(None, json_ok=False)
        with self.assertRaises(RuntimeError) as ctx:
            self.run_collect(responses)
        self.assertIn("json", str(ctx.exception))

    def test_changed_line_codes_stop_before_any_data_fetch(self):
        responses = good_responses()
        responses["GetParameterValues"] = FakeResponse(line_codes({"1": "[CAINC1] Something else", "3": "[CAINC1] Per capita personal income"}))
        with self.assertRaises(RuntimeError):
            self.run_collect(responses)

    def test_no_rows_in_the_window_raises(self):
        responses = good_responses()
        responses["1"] = FakeResponse(payload([row("10180", "2010", "1")], "1"))
        responses["3"] = FakeResponse(payload([], "3"))
        with self.assertRaises(RuntimeError) as ctx:
            self.run_collect(responses)
        self.assertIn("no CAINC1", str(ctx.exception))

    def test_changed_unit_multiplier_raises(self):
        responses = good_responses()
        responses["3"] = FakeResponse(payload([dict(row("10180", "2024", "57", line="3"), UNIT_MULT="3")], "3"))
        with self.assertRaises(RuntimeError) as ctx:
            self.run_collect(responses)
        self.assertIn("UNIT_MULT", str(ctx.exception))


class TestBeaFeedsTheBuilder(unittest.TestCase):
    def frames(self):
        merged = pd.DataFrame({
            "cbsa_code": ["16984", "10180"],
            "place_name": ["Chicago-Naperville-Schaumburg, IL (MSAD)", "Abilene, TX"],
            "year": [2024, 2024], "avg_index_nsa": [260.0, 335.5],
            "geo_level": ["division", "msa"], "parent_cbsa": ["16980", None],
        })
        centroids = pd.DataFrame({
            "cbsa_code": ["16980", "16984", "10180"],
            "name": ["Chicago-Naperville-Elgin, IL-IN Metro Area", "Chicago-Naperville-Schaumburg, IL Metro Division", "Abilene, TX Metro Area"],
            "lat": [41.8, 41.85, 32.45], "lon": [-87.9, -87.95, -99.7],
        }).set_index("cbsa_code")
        return merged, centroids

    # the metrics.csv the collector writes lands in the year panels and latest,
    # and the chicago division inherits the metro's values
    def test_metrics_reach_abilene_and_the_division_inherits(self):
        merged, centroids = self.frames()
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "bea"
            with ExitStack() as stack:
                stack.enter_context(mock.patch.dict(os.environ, {"BEA_API_KEY": FAKE_KEY}))
                stack.enter_context(mock.patch.object(bea, "OUT_DIR", out_dir))
                stack.enter_context(mock.patch.object(bea, "PAUSE_SECONDS", 0))
                stack.enter_context(mock.patch.object(bea, "fetch", fake_fetch(good_responses(), [])))
                with redirect_stdout(io.StringIO()):
                    bea.collect()
            enrichments = bm.discover_enrichments(tmp)
            self.assertEqual(enrichments[0]["metrics"], ["bea_income_per_capita", "bea_personal_income"])
            metros, _, _ = bm.build_metros(merged, centroids, enrichments=enrichments)
            self.assertEqual(bm.enrichment_version(out_dir), "CAINC1 2014 through 2024")
        abi = next(m for m in metros if m["cbsa"] == "10180")
        self.assertEqual(abi["years"]["2014"]["bea_personal_income"], 7116829.0)
        self.assertEqual(abi["years"]["2019"]["bea_personal_income"], 8412003.0)
        self.assertEqual(abi["years"]["2024"]["bea_income_per_capita"], 57120.0)
        self.assertIsNone(abi["years"]["2019"]["bea_income_per_capita"])
        self.assertEqual((abi["latest"]["bea_personal_income"], abi["latest"]["bea_personal_income_date"]), (10250441.0, "2024"))
        self.assertEqual(abi["parent_metrics"], [])
        chi = next(m for m in metros if m["cbsa"] == "16984")
        self.assertEqual(chi["years"]["2024"]["bea_personal_income"], 701234567.0)
        self.assertEqual(chi["parent_metrics"], ["bea_income_per_capita", "bea_personal_income"])


if __name__ == "__main__":
    unittest.main()
