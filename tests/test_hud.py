import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import requests

from bot import build_map_data as bm
from bot.collectors import hud
from bot.common import USER_AGENT

# every fixture in this file is synthetic, built from the response shapes in
# the hud user api documentation rather than captured from the live api

TOKEN = "synthetic-token-1234"

LISTING = {"data": [
    {"cbsa_code": "METRO10180M10180", "area_name": "Abilene, TX MSA", "category": "MetroArea"},
    {"cbsa_code": "METRO29180N22001", "area_name": "Acadia Parish, LA HUD Metro FMR Area", "category": "MetroArea"},
    {"cbsa_code": "METRO16980M16980", "area_name": "Chicago-Joliet-Naperville, IL HUD Metro FMR Area", "category": "MetroArea"},
    {"cbsa_code": "METRO16980MM1600", "area_name": "Chicago subarea", "category": "MetroArea"},
    {"cbsa_code": "METRO10180M10180", "area_name": "Abilene, TX MSA repeated", "category": "MetroArea"},
    {"area_name": "row without a code", "category": "MetroArea"},
    {"cbsa_code": "METRO01234M01234", "area_name": "Leading zero, ZZ MSA", "category": "MetroArea"},
    "not a row",
]}


def fmr_plain(year, rent, name="Abilene, TX MSA"):
    return {"data": {
        "county_name": "", "counties_msa": "Callahan County, TX; Jones County, TX; Taylor County, TX",
        "town_name": "", "metro_status": "1", "metro_name": name, "area_name": name,
        "smallarea_status": "0", "year": str(year),
        "basicdata": {"Efficiency": "700.0", "One-Bedroom": "750.0", "Two-Bedroom": f"{rent}.0",
                      "Three-Bedroom": "1000.0", "Four-Bedroom": "1200.0", "year": str(year)},
    }}


def fmr_small_area(year, rent, name="Chicago-Joliet-Naperville, IL HUD Metro FMR Area"):
    return {"data": {
        "county_name": "", "counties_msa": "Cook County, IL; DuPage County, IL", "town_name": "",
        "metro_status": "1", "metro_name": name, "area_name": name, "smallarea_status": "1", "year": str(year),
        "basicdata": [
            {"zip_code": "60601", "Efficiency": 1900, "One-Bedroom": 2000, "Two-Bedroom": rent + 900,
             "Three-Bedroom": 2900, "Four-Bedroom": 3400},
            {"zip_code": "MSA level", "Efficiency": 1100, "One-Bedroom": 1200, "Two-Bedroom": rent,
             "Three-Bedroom": 1800, "Four-Bedroom": 2100},
            {"zip_code": "60602", "Efficiency": 1500, "One-Bedroom": 1600, "Two-Bedroom": rent + 300,
             "Three-Bedroom": 2300, "Four-Bedroom": 2700},
        ],
    }}


def il_payload(year, income, name="Abilene, TX MSA"):
    return {"data": {
        "county_name": "", "counties_msa": "Taylor County, TX", "town_name": "", "metro_status": "1",
        "metro_name": name, "area_name": name, "year": str(year), "median_income": income,
        "very_low": {"il50_p1": 21000}, "extremely_low": {"il30_p1": 12600}, "low": {"il80_p1": 33600},
    }}


def response(status, payload=None, bad_json=False):
    r = Mock(status_code=status)
    r.json = Mock(side_effect=ValueError("bad json")) if bad_json else Mock(return_value=payload)
    return r


class TestMetroList(unittest.TestCase):
    def test_documented_example_keeps_only_whole_metro_ids(self):
        ids = hud.parse_metro_list(LISTING)
        self.assertEqual(ids["10180"], "METRO10180M10180")
        self.assertEqual(ids["16980"], "METRO16980M16980")
        self.assertNotIn("29180", ids)

    def test_subarea_repeat_and_malformed_rows_are_dropped(self):
        ids = hud.parse_metro_list(LISTING)
        self.assertEqual(sorted(ids), ["01234", "10180", "16980"])
        self.assertEqual(len(hud.list_entries(LISTING)) - len(ids), 5)

    def test_leading_zero_code_survives_as_a_string(self):
        self.assertEqual(hud.parse_metro_list(LISTING)["01234"], "METRO01234M01234")

    def test_bare_list_and_wrapped_list_agree(self):
        self.assertEqual(hud.parse_metro_list(LISTING["data"]), hud.parse_metro_list(LISTING))

    def test_empty_responses_give_no_ids(self):
        for payload in ({}, [], {"data": []}, {"data": None}, None, {"error": "Unauthenticated"}):
            self.assertEqual(hud.parse_metro_list(payload), {})

    # a subarea id with the wrong letter or mismatched codes is never a metro
    def test_ids_with_mismatched_codes_or_odd_shapes_are_skipped(self):
        listing = [{"cbsa_code": c} for c in (
            "METRO16980M16984", "metro10180m10180", "METRO1018M10180", "METRO10180M10180 ", "CNTY10180M10180",
        )]
        self.assertEqual(hud.parse_metro_list(listing), {"10180": "METRO10180M10180"})


class TestParsers(unittest.TestCase):
    def test_plain_fmr_string_value(self):
        self.assertEqual(hud.parse_fmr(fmr_plain(2019, 801)), 801.0)

    def test_small_area_fmr_takes_the_msa_level_row(self):
        self.assertEqual(hud.parse_fmr(fmr_small_area(2024, 1428)), 1428.0)

    def test_small_area_without_an_msa_level_row_is_missing(self):
        payload = fmr_small_area(2024, 1428)
        payload["data"]["basicdata"] = [r for r in payload["data"]["basicdata"] if r["zip_code"] != "MSA level"]
        self.assertIsNone(hud.parse_fmr(payload))

    def test_msa_level_flag_is_matched_loosely(self):
        payload = fmr_small_area(2024, 1428)
        payload["data"]["basicdata"][1]["zip_code"] = " msa-Level "
        self.assertEqual(hud.parse_fmr(payload), 1428.0)

    def test_missing_two_bedroom_is_missing(self):
        payload = fmr_plain(2019, 801)
        del payload["data"]["basicdata"]["Two-Bedroom"]
        self.assertIsNone(hud.parse_fmr(payload))

    def test_malformed_values_are_missing(self):
        for bad in ("", "n/a", None, "0", 0, -5, "nan", "inf", [], {}):
            payload = fmr_plain(2019, 801)
            payload["data"]["basicdata"]["Two-Bedroom"] = bad
            self.assertIsNone(hud.parse_fmr(payload), repr(bad))

    def test_empty_and_error_payloads_are_missing(self):
        for payload in ({}, None, [], {"data": {}}, {"data": []}, {"error": "No data found using 'x'"}):
            self.assertIsNone(hud.parse_fmr(payload))
            self.assertIsNone(hud.parse_income_limits(payload))

    def test_income_limits_median_income(self):
        self.assertEqual(hud.parse_income_limits(il_payload(2019, 65900)), 65900.0)
        self.assertEqual(hud.parse_income_limits(il_payload(2019, "65,900")), 65900.0)

    def test_income_limits_missing_median_income(self):
        payload = il_payload(2019, 65900)
        del payload["data"]["median_income"]
        self.assertIsNone(hud.parse_income_limits(payload))
        self.assertIsNone(hud.parse_income_limits(il_payload(2019, "")))

    def test_payload_year_from_data_or_basicdata(self):
        self.assertEqual(hud.payload_year(fmr_plain(2017, 948)), 2017)
        self.assertEqual(hud.payload_year(fmr_small_area(2024, 2045)), 2024)
        self.assertEqual(hud.payload_year(il_payload(2019, 65900)), 2019)
        only_basic = {"data": {"basicdata": {"Two-Bedroom": "948.0", "year": "2017"}}}
        self.assertEqual(hud.payload_year(only_basic), 2017)

    def test_payload_year_missing_or_odd(self):
        self.assertIsNone(hud.payload_year({}))
        self.assertIsNone(hud.payload_year({"data": {"basicdata": {"Two-Bedroom": "1"}}}))
        self.assertIsNone(hud.payload_year({"data": {"year": "latest"}}))

    def test_to_number_accepts_strings_and_numbers(self):
        self.assertEqual(hud.to_number("948.0"), 948.0)
        self.assertEqual(hud.to_number(2045), 2045.0)
        self.assertEqual(hud.to_number(" 1,394 "), 1394.0)


class TestRows(unittest.TestCase):
    RECORDS = [
        ("16980", "fmr_2br", 2024, 1428.0),
        ("10180", "fmr_2br", 2024, 1048.0),
        ("10180", "fmr_2br", 2019, 801.0),
        ("10180", "median_family_income", 2024, 78700.0),
        ("01234", "fmr_2br", 2024, 500.0),
    ]

    def test_exact_frame(self):
        df = hud.build_rows(self.RECORDS)
        self.assertEqual(list(df.columns), ["cbsa_code", "metric", "period", "value"])
        self.assertEqual(df.values.tolist(), [
            ["01234", "fmr_2br", "2024", 500.0],
            ["10180", "fmr_2br", "2019", 801.0],
            ["10180", "fmr_2br", "2024", 1048.0],
            ["16980", "fmr_2br", "2024", 1428.0],
            ["10180", "median_family_income", "2024", 78700.0],
        ])

    def test_missing_values_are_dropped(self):
        df = hud.build_rows(self.RECORDS + [("10180", "fmr_2br", 2014, None)])
        self.assertEqual(len(df), 5)
        self.assertNotIn("2014", df.period.tolist())

    def test_duplicate_key_keeps_the_last_value(self):
        df = hud.build_rows(self.RECORDS + [("10180", "fmr_2br", 2024, 1050.0)])
        row = df[(df.cbsa_code == "10180") & (df.metric == "fmr_2br") & (df.period == "2024")]
        self.assertEqual(len(row), 1)
        self.assertEqual(row.value.iloc[0], 1050.0)

    def test_empty_records_keep_the_columns(self):
        df = hud.build_rows([])
        self.assertEqual(list(df.columns), ["cbsa_code", "metric", "period", "value"])
        self.assertEqual(len(df), 0)

    def test_period_is_a_four_digit_string_and_survives_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metrics.csv"
            hud.build_rows(self.RECORDS).to_csv(path, index=False)
            back = pd.read_csv(path, dtype={"cbsa_code": str, "period": str})
        self.assertEqual(back.cbsa_code.tolist()[0], "01234")
        self.assertTrue(all(len(p) == 4 for p in back.period))

    # the builder's own loader accepts the frame and the metric names are free
    def test_map_contract(self):
        metrics = {metric for _, metric, _ in hud.DATASETS.values()}
        self.assertEqual(metrics, {"fmr_2br", "median_family_income"})
        self.assertFalse(metrics & bm.RESERVED)
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "hud"
            src.mkdir()
            hud.build_rows(self.RECORDS).to_csv(src / "metrics.csv", index=False)
            loaded = bm.load_enrichment(src / "metrics.csv")
        self.assertEqual(loaded["metrics"], ["fmr_2br", "median_family_income"])
        annual, latest = bm.enrich_values(loaded["groups"]["10180"])
        self.assertEqual(annual[("fmr_2br", 2019)], 801.0)
        self.assertEqual(latest["fmr_2br"], ("2024", 1048.0))


@patch("bot.collectors.hud.time.sleep")
@patch("bot.collectors.hud.requests.get")
class TestClient(unittest.TestCase):
    def test_bearer_header_user_agent_and_timeout(self, get, sleep):
        get.return_value = response(200, {})
        hud.Client(TOKEN).get("https://x", params={"year": 2024})
        kwargs = get.call_args.kwargs
        self.assertEqual(kwargs["headers"], {"User-Agent": USER_AGENT, "Authorization": f"Bearer {TOKEN}"})
        self.assertEqual(kwargs["timeout"], hud.TIMEOUT)
        self.assertEqual(kwargs["params"], {"year": 2024})

    def test_second_request_is_paced(self, get, sleep):
        get.return_value = response(200, {})
        client = hud.Client(TOKEN)
        client.get("https://x")
        client.get("https://x")
        waits = [c.args[0] for c in sleep.call_args_list]
        self.assertEqual(len(waits), 1)
        self.assertTrue(0 < waits[0] <= hud.MIN_INTERVAL)

    # a 5xx backs off exponentially, a 429 waits out the minute instead
    def test_5xx_and_429_are_retried(self, get, sleep):
        get.side_effect = [response(503), response(429), response(200, {"data": []})]
        self.assertEqual(hud.Client(TOKEN).get("https://x").status_code, 200)
        self.assertEqual(get.call_count, 3)
        waits = [c.args[0] for c in sleep.call_args_list]
        self.assertIn(1, waits)  # the 503 backoff
        self.assertIn(61.0, waits)  # the 429 window wait
        self.assertNotIn(2, waits)  # the 429 did not consume an exponential step

    def test_connection_error_text_never_carries_the_token(self, get, sleep):
        get.side_effect = requests.ConnectionError(f"boom {TOKEN} boom")
        with self.assertRaises(RuntimeError) as ctx:
            hud.Client(TOKEN).get("https://x")
        self.assertNotIn(TOKEN, str(ctx.exception))
        self.assertIn("<token>", str(ctx.exception))

    def test_get_json_shapes(self, get, sleep):
        client = hud.Client(TOKEN)
        get.return_value = response(200, {"data": {"year": "2024"}})
        self.assertEqual(client.get_json("https://x"), (200, {"data": {"year": "2024"}}))
        get.return_value = response(404, {"error": "No data found using 'x'"})
        self.assertEqual(client.get_json("https://x"), (404, None))
        get.return_value = response(200, bad_json=True)
        self.assertEqual(client.get_json("https://x"), ("malformed", None))

    def test_401_and_403_raise_without_the_token(self, get, sleep):
        for status in (401, 403):
            get.return_value = response(status, {"error": "Unauthenticated"})
            with self.assertRaises(RuntimeError) as ctx:
                hud.Client(TOKEN).get_json("https://x")
            self.assertIn(str(status), str(ctx.exception))
            self.assertNotIn(TOKEN, str(ctx.exception))


# a fake hud: two study metros with values, 2014 missing everywhere, a blank
# income in one year, a small area response for chicago in 2024, and newer
# years for fmr than for income limits
FMR = {
    ("METRO10180M10180", 2019): 801, ("METRO10180M10180", 2024): 1048, ("METRO10180M10180", 2026): 1190,
    ("METRO16980M16980", 2019): 1180, ("METRO16980M16980", 2024): 1428, ("METRO16980M16980", 2026): 1600,
}
IL = {
    ("METRO10180M10180", 2019): 60800, ("METRO10180M10180", 2024): 78700, ("METRO10180M10180", 2025): 81000,
    ("METRO16980M16980", 2019): "", ("METRO16980M16980", 2024): 113400, ("METRO16980M16980", 2025): 117300,
}
NEWEST = {"fmr": 2026, "il": 2025}

MERGED = (
    "cbsa_code,place_name,geo_level,parent_cbsa,year\n"
    "10180,\"Abilene, TX\",msa,,2019\n"
    "10180,\"Abilene, TX\",msa,,2024\n"
    "16980,\"Chicago-Naperville-Elgin, IL-IN-WI\",msa,,2024\n"
    "16984,\"Chicago-Naperville-Schaumburg, IL (MSAD)\",division,16980,2024\n"
    "99999,\"Nowhere, ZZ\",msa,,2024\n"
)


class TestCollect(unittest.TestCase):
    def setUp(self):
        self.calls = []

    def fake_get(self, url, params=None, timeout=None, headers=None):
        self.calls.append((url, dict(params or {}), headers))
        if headers.get("Authorization") != f"Bearer {TOKEN}":
            return response(401, {"error": "Unauthenticated"})
        if url == hud.LIST_URL:
            return response(200, LISTING)
        for dataset, base, table in (("fmr", hud.FMR_URL, FMR), ("il", hud.IL_URL, IL)):
            if url.startswith(base):
                entity = url[len(base):]
                year = params["year"] if params and "year" in params else NEWEST[dataset]
                if (entity, year) not in table:
                    return response(404, {"error": f"No data found using '{entity}'"})
                value = table[(entity, year)]
                if dataset == "il":
                    return response(200, il_payload(year, value))
                if entity == "METRO16980M16980" and year == 2024:
                    return response(200, fmr_small_area(year, value))
                return response(200, fmr_plain(year, value))
        return response(404, {"error": "no route"})

    def run_collect(self, token=TOKEN, listing=None):
        with tempfile.TemporaryDirectory() as tmp:
            merged = Path(tmp) / "merged.csv"
            merged.write_text(MERGED)
            out_dir = Path(tmp) / "hud"
            fake = self.fake_get
            if listing is not None:
                def fake(url, params=None, timeout=None, headers=None):
                    return response(200, listing)
            with patch.dict(os.environ, {"HUD_API_TOKEN": token}), \
                    patch.object(hud, "INTEGRATED", merged), \
                    patch.object(hud, "OUT_DIR", out_dir), \
                    patch.object(hud, "OUT_FILE", out_dir / "metrics.csv"), \
                    patch("bot.collectors.hud.requests.get", side_effect=fake), \
                    patch("bot.collectors.hud.time.sleep"), \
                    contextlib.redirect_stdout(io.StringIO()) as out:
                result = hud.collect()
            files = sorted(p.name for p in out_dir.iterdir()) if out_dir.exists() else []
            frame = pd.read_csv(out_dir / "metrics.csv", dtype={"cbsa_code": str, "period": str}) if result else None
            manifest = json.loads((out_dir / "download_manifest.json").read_text()) if result else None
            raw = {p.name: json.loads(p.read_text()) for p in out_dir.glob("hud_*.json")} if result else {}
        return result, frame, manifest, files, raw, out.getvalue()

    def test_metrics_csv_exact_rows(self):
        result, frame, _, _, _, _ = self.run_collect()
        self.assertEqual(result.name, "metrics.csv")
        self.assertEqual(list(frame.columns), ["cbsa_code", "metric", "period", "value"])
        self.assertEqual(frame.values.tolist(), [
            ["10180", "fmr_2br", "2019", 801.0],
            ["10180", "fmr_2br", "2024", 1048.0],
            ["10180", "fmr_2br", "2026", 1190.0],
            ["16980", "fmr_2br", "2019", 1180.0],
            ["16980", "fmr_2br", "2024", 1428.0],
            ["16980", "fmr_2br", "2026", 1600.0],
            ["10180", "median_family_income", "2019", 60800.0],
            ["10180", "median_family_income", "2024", 78700.0],
            ["10180", "median_family_income", "2025", 81000.0],
            ["16980", "median_family_income", "2024", 113400.0],
            ["16980", "median_family_income", "2025", 117300.0],
        ])

    def test_only_whole_metro_entities_of_study_codes_are_requested(self):
        self.run_collect()
        urls = [url for url, _, _ in self.calls]
        for absent in ("16984", "99999", "MM1600", "N22001", "01234"):
            self.assertFalse(any(absent in url for url in urls), absent)
        for dataset, base in (("fmr", hud.FMR_URL), ("il", hud.IL_URL)):
            years = {p.get("year") for url, p, _ in self.calls if url.startswith(base) and "year" in p}
            self.assertEqual(years, {2014, 2019, 2024, NEWEST[dataset]}, dataset)
        # the metro list, two probes per dataset at most, then two entities per dataset and year
        self.assertLessEqual(len(self.calls), 1 + 6 + 2 * 2 * 4)

    def test_every_call_carries_the_bearer_header_and_user_agent(self):
        self.run_collect()
        for _, _, headers in self.calls:
            self.assertEqual(headers["Authorization"], f"Bearer {TOKEN}")
            self.assertEqual(headers["User-Agent"], USER_AGENT)

    def test_raw_json_per_year_and_manifest(self):
        _, _, manifest, files, raw, out = self.run_collect()
        self.assertEqual(files, ["download_manifest.json", "hud_2019.json", "hud_2024.json",
                                 "hud_2025.json", "hud_2026.json", "metrics.csv"])
        self.assertEqual(raw["hud_2024.json"]["fmr"]["METRO16980M16980"]["data"]["smallarea_status"], "1")
        self.assertEqual(set(raw["hud_2026.json"]["il"]), set())
        self.assertEqual(manifest[0]["filename"], "metrics.csv")
        self.assertEqual(manifest[0]["version"], "fmr through 2026, income limits through 2025")
        self.assertEqual(manifest[0]["integrity"]["row_count"], 11)
        notes = manifest[0]["notes"]
        self.assertEqual(notes["years_without_data"], [2014])
        self.assertEqual(notes["entities"], 2)
        self.assertEqual(notes["study_codes"], 4)
        self.assertEqual(notes["years"], {"fmr": [2014, 2019, 2024, 2026], "il": [2014, 2019, 2024, 2025]})
        self.assertEqual(notes["responses_skipped"], {"404": 4})
        self.assertEqual([e["filename"] for e in manifest[1:]], ["hud_2019.json", "hud_2024.json",
                                                                  "hud_2025.json", "hud_2026.json"])
        # the blank income for chicago in 2019 is still a captured response
        self.assertEqual(manifest[1]["integrity"]["row_count"], 4)
        self.assertNotIn(TOKEN, out)
        self.assertNotIn(TOKEN, json.dumps(manifest))

    def test_no_token_skips_with_one_line_and_no_request(self):
        for token in ("", "   "):
            self.calls = []
            result, _, _, files, _, out = self.run_collect(token=token)
            self.assertIsNone(result)
            self.assertEqual(self.calls, [])
            self.assertEqual(files, [])
            self.assertEqual(out.count("\n"), 1)
            self.assertIn("skipped", out)

    def test_bad_token_raises_without_leaking_it(self):
        with self.assertRaises(RuntimeError) as ctx:
            self.run_collect(token="wrong-token-9999")
        self.assertIn("401", str(ctx.exception))
        self.assertNotIn("wrong-token-9999", str(ctx.exception))

    def test_empty_metro_list_raises(self):
        with self.assertRaises(RuntimeError):
            self.run_collect(listing={"data": []})


class TestStudyCodes(unittest.TestCase):
    def test_levels_sorted_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "merged.csv"
            path.write_text(MERGED)
            self.assertEqual(hud.study_codes(path),
                             {"10180": "msa", "16980": "msa", "16984": "division", "99999": "msa"})


if __name__ == "__main__":
    unittest.main()


class TestRateLimitWindow(unittest.TestCase):
    # a 429 waits out the minute (Retry-After when given) and then succeeds
    @patch("bot.collectors.hud.time.sleep")
    @patch("bot.collectors.hud.requests.get")
    def test_429_waits_for_the_window_then_retries(self, get, sleep):
        limited = Mock(status_code=429, headers={"Retry-After": "7"})
        ok = Mock(status_code=200, headers={})
        get.side_effect = [limited, ok]
        client = hud.Client("tok")
        self.assertIs(client.get("https://example.test"), ok)
        self.assertIn(7.0, [c.args[0] for c in sleep.call_args_list])

    @patch("bot.collectors.hud.time.sleep")
    @patch("bot.collectors.hud.requests.get")
    def test_429_without_retry_after_waits_a_minute(self, get, sleep):
        get.side_effect = [Mock(status_code=429, headers={}), Mock(status_code=200, headers={})]
        hud.Client("tok").get("https://example.test")
        self.assertIn(61.0, [c.args[0] for c in sleep.call_args_list])

    def test_pace_is_under_sixty_a_minute(self):
        self.assertGreater(hud.MIN_INTERVAL, 1.0)
