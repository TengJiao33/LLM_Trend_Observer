import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from compare import DeltaEngine
from main import collect_sources, run_pipeline
from report_generator import ReportGenerator, noteworthy
from scrapers.artalanaly_scraper import parse_api, parse_embed_html, parse_value
from scrapers.lmsys_scraper import CONFIGS, parse_arena_rows
from scrapers.openrouter_scraper import parse_daily_api, parse_rankings_html
from utils.data import read_json, snapshot, validate_board, write_json


def board(rows=None, **kwargs):
    return {"scope": "test", "metric": "tokens", "unit": "tokens", "coverage": "top50",
            "published_at": "2026-10-23", "fetched_at": "2026-10-23T08:00:00+00:00",
            "method": "official_api", "rows": rows or [{"model_id": "a", "name": "Model A", "rank": 1, "score": 100}], **kwargs}


def or_html(missing=None):
    cards = []
    for i in range(1, 11):
        if i == missing:
            continue
        growth = 'new' if i == 1 else '<span class="text-negative-text">44%</span>' if i == 2 else '0%'
        cards.append(f'<div data-testid="model-rankings-leaderboard-row"><div>{i}.</div>'
                     f'<div><a href="/vendor/model-{i}:free">Display Name {i}</a></div>'
                     f'<div><div>1.2T tokens</div><div title="Change in tokens processed in the last week from the previous period">{growth}</div></div></div>')
    return ''.join(cards)


def aa_html(reorder=False, cost_header="Cost per Task USD"):
    headers = ["API Provider", "Model", "Context Window", "License", "Artificial Analysis Intelligence Index", cost_header, "Median Tokens/s", "Further Analysis"]
    cells = ["Host", "Reasoner (high)", "1M", "Open", "50", "$0.02", "1,250", '<a href="/models/reasoner">Model</a><a href="/providers/host">Provider</a>']
    if reorder:
        headers[4], headers[6] = headers[6], headers[4]
        cells[4], cells[6] = cells[6], cells[4]
    return '<table><tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '</tr><tr>' + ''.join(f'<td>{v}</td>' for v in cells) + '</tr></table>'


class ParserTests(unittest.TestCase):
    def test_openrouter_new_and_negative_growth_are_not_skipped(self):
        rows = parse_rankings_html(or_html())["rows"]
        self.assertEqual(list(range(1, 11)), [r["rank"] for r in rows])
        self.assertEqual("new", rows[0]["growth"])
        self.assertEqual("-44%", rows[1]["growth"])
        self.assertEqual("+0%", rows[2]["growth"])

    def test_openrouter_uses_link_identity_and_numeric_tokens(self):
        row = parse_rankings_html(or_html())["rows"][0]
        self.assertEqual("vendor/model-1:free", row["model_id"])
        self.assertEqual(1_200_000_000_000, row["score"])

    def test_openrouter_incomplete_page_is_failure(self):
        with self.assertRaisesRegex(ValueError, "incomplete"):
            parse_rankings_html(or_html(missing=2))

    def test_daily_api_excludes_other_and_preserves_large_counts(self):
        day = "2026-10-23"
        payload = {"meta": {"start_date": day, "end_date": day}, "data": [
            {"date": day, "model_permaslug": "a/b:free", "total_tokens": "9007199254740993"},
            {"date": day, "model_permaslug": "other", "total_tokens": "999999999999999999"}]}
        result = parse_daily_api(payload, day)
        self.assertEqual(1, len(result["rows"]))
        self.assertEqual(9007199254740993, result["rows"][0]["score"])
        self.assertEqual("tokens", result["unit"])

    def test_daily_api_rejects_wrong_window(self):
        with self.assertRaises(ValueError):
            parse_daily_api({"meta": {}, "data": []}, "2026-10-23")

    def test_aa_headers_can_move_without_changing_metrics(self):
        a, b = parse_embed_html(aa_html()), parse_embed_html(aa_html(reorder=True))
        self.assertEqual(a, b)
        self.assertEqual("USD/task", a["CostPerTask"]["unit"])
        self.assertEqual(0.02, a["CostPerTask"]["rows"][0]["score"])
        self.assertEqual(1250, a["Speed"]["rows"][0]["score"])
        self.assertNotIn("Price", a)

    def test_aa_unknown_cost_definition_fails_instead_of_relabelling(self):
        with self.assertRaisesRegex(ValueError, "headers or cost units"):
            parse_embed_html(aa_html(cost_header="Price"))

    def test_aa_missing_values_are_not_zero(self):
        self.assertIsNone(parse_value("--"))
        self.assertIsNone(parse_value("unknown"))
        self.assertEqual(0, parse_value("$0.00"))

    def test_aa_api_prices_are_separate_metrics(self):
        payload = {"data": [{"id": "stable-id", "name": "Name", "evaluations": {"artificial_analysis_intelligence_index": 52},
                             "pricing": {"price_1m_input_tokens": 1.2, "price_1m_output_tokens": 4.8}, "median_output_tokens_per_second": 100}]}
        boards = parse_api(payload)
        self.assertEqual("USD/1M input tokens", boards["InputPrice"]["unit"])
        self.assertEqual(4.8, boards["OutputPrice"]["rows"][0]["score"])
        self.assertEqual("stable-id", boards["Intelligence"]["rows"][0]["model_id"])
        self.assertNotIn("CostPerTask", boards)

    def test_arena_filters_all_rows_before_ranking(self):
        raw = [{"category": "other"}] * 150 + [{"category": "overall", "model_name": "A", "rank": 1, "rating": 1525.5,
               "rating_lower": 1520, "rating_upper": 1530, "leaderboard_publish_date": "2026-10-22"}]
        result = parse_arena_rows(raw, "text_style_control")
        self.assertEqual("2026-10-22", result["published_at"])
        self.assertEqual(1525.5, result["rows"][0]["score"])
        self.assertEqual("arena:text_style_control:overall", result["scope"])

    def test_arena_agent_is_a_proportion_with_its_own_interval(self):
        result = parse_arena_rows([{"category": "overall", "model_name": "A", "rank": 1, "score": 0.207,
                                   "score_ci_lower": 0.18, "score_ci_upper": 0.23,
                                   "leaderboard_publish_date": "2026-10-23"}], "agent")
        self.assertEqual("proportion", result["unit"])
        self.assertEqual(0.18, result["rows"][0]["ci_low"])

    def test_arena_mixed_dates_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "publication dates"):
            parse_arena_rows([{"category": "overall", "leaderboard_publish_date": "2026-10-22"},
                              {"category": "overall", "leaderboard_publish_date": "2026-10-23"}], "text")

    def test_duplicate_ids_and_nan_are_rejected(self):
        for rows in [[{"model_id": "a", "rank": 1, "score": float('nan')}],
                     [{"model_id": "a", "rank": 1, "score": 1}] * 2]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                validate_board(board(rows))


class HistoryAndReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.engine = DeltaEngine(self.root / "data/history.json")

    def save(self, value):
        self.engine.update_many({"openrouter": snapshot("openrouter", "https://example.com", "official_api", {"Usage": value})})

    def test_legacy_history_is_preserved_but_not_compared(self):
        legacy = {"hf_leaderboard": [{"model_id": "incorrect-old-top", "rank": 1}]}
        write_json(self.engine.history_file, legacy)
        engine = DeltaEngine(self.engine.history_file)
        result = engine.compare("openrouter", "Usage", board())
        self.assertEqual("baseline", result["state"])
        engine.update_many({"openrouter": snapshot("openrouter", "url", "official_api", {"Usage": board()})})
        self.assertEqual(legacy, read_json(engine.history_file)["legacy"])
        backups = list((self.root / "data/backups").glob("*.json"))
        self.assertEqual(legacy, read_json(backups[0]))

    def test_value_change_is_detected_without_rank_change(self):
        self.save(board())
        current = board([{"model_id": "a", "name": "Model A", "rank": 1, "score": 10}])
        result = self.engine.compare("openrouter", "Usage", current)
        self.assertEqual(0, result["rows"][0]["rank_delta"])
        self.assertEqual(-90, result["rows"][0]["score_delta"])
        self.assertTrue(noteworthy(result["rows"][0], current))

    def test_scope_unit_and_coverage_changes_reset_baselines(self):
        self.save(board())
        for key in ["scope", "metric", "unit", "coverage"]:
            with self.subTest(key=key):
                result = self.engine.compare("openrouter", "Usage", board(**{key: "changed"}))
                self.assertEqual("baseline", result["state"])
                self.assertIsNone(result["rows"][0]["rank_delta"])

    def test_increase_from_zero_cost_is_reported_without_division_by_zero(self):
        self.save(board([{"model_id": "a", "name": "A", "rank": 1, "score": 0}], unit="USD/task"))
        current = board(unit="USD/task")
        row = self.engine.compare("openrouter", "Usage", current)["rows"][0]
        self.assertIsNone(row["relative_delta"])
        self.assertTrue(noteworthy(row, current))

    def test_fallback_has_no_changes_or_departures(self):
        self.save(board())
        result = self.engine.compare("openrouter", "Usage", board(), fresh=False)
        self.assertEqual("fallback", result["state"])
        self.assertIsNone(result["rows"][0]["score_delta"])
        self.assertEqual([], result["departures"])

    def test_departure_from_collected_range_is_reported(self):
        self.save(board())
        result = self.engine.compare("openrouter", "Usage", board([{"model_id": "b", "name": "B", "rank": 1, "score": 10}]))
        self.assertEqual("entered", result["rows"][0]["change"])
        self.assertEqual([{"name": "Model A", "old_rank": 1, "new_rank": None}], result["departures"])

    def test_ties_are_included_even_with_more_than_ten_rows(self):
        rows = [{"model_id": str(i), "name": str(i), "rank": 1, "score": 100} for i in range(12)]
        self.save(board(rows))
        result = self.engine.compare("openrouter", "Usage", board(rows))
        self.assertEqual([], result["departures"])
        path = ReportGenerator(self.root / "reports", self.engine).generate(
            {"openrouter": snapshot("openrouter", "url", "official_api", {"Usage": board(rows)})}, {})
        self.assertIn("| 1 | 11 |", Path(path).read_text(encoding="utf-8"))

    def test_partial_update_retains_category_observation_dates(self):
        original = snapshot("lmsys", "url", "official_dataset", {"Text": board(), "Agent": board()})
        self.engine.update_many({"lmsys": original})
        newer = board(fetched_at="2026-10-24T02:00:00+00:00")
        self.engine.update_many({"lmsys": snapshot("lmsys", "url", "official_dataset", {"Text": newer})})
        self.assertEqual("2026-10-23T08:00:00+00:00", self.engine.previous_boards("lmsys")["Agent"]["fetched_at"])
        self.assertEqual(newer, self.engine.previous_boards("lmsys")["Text"])

    def test_report_preserves_ranks_and_marks_unknown_fallback(self):
        rows = [{"model_id": "a", "name": "A", "rank": 1, "score": 100}, {"model_id": "b", "name": "B", "rank": 4, "score": 40}]
        self.save(board(rows))
        generator = ReportGenerator(self.root / "reports", self.engine)
        path = generator.generate({}, {s: {"state": "failed", "errors": {"source": "timeout"}} for s in ["openrouter", "lmsys", "artalanaly"]})
        text = Path(path).read_text(encoding="utf-8")
        self.assertIn("| 4 | B |", text)
        self.assertNotIn("| 2 | B |", text)
        self.assertIn("本次未更新", text)
        self.assertIn("2026-10-23 历史数据", text)
        self.assertNotIn("名次变化", text)
        self.assertNotIn("## HF", text)
        self.assertIn("暂无可比数据", text)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_collection_records_partial_categories_without_losing_good_data(self):
        collectors = {"lmsys": lambda: snapshot("lmsys", "url", "official_dataset", {"Text": board()})}
        with patch("main.COLLECTORS", collectors):
            current, statuses = collect_sources(self.root / "data")
        self.assertEqual("partial", statuses["lmsys"]["state"])
        self.assertIn("Agent", statuses["lmsys"]["errors"])
        self.assertIn("Text", current["lmsys"]["boards"])

    def test_all_source_failure_writes_report_and_fails(self):
        def fail():
            raise TimeoutError("upstream timeout")
        with patch("main.COLLECTORS", {s: fail for s in ["openrouter", "lmsys", "artalanaly"]}):
            result = run_pipeline(self.root / "data", self.root / "reports")
        self.assertEqual(1, result)
        self.assertTrue((self.root / "reports/latest_report.md").exists())
        self.assertFalse((self.root / "data/history.json").exists())

    def test_notification_is_opt_in_and_failure_is_not_suppressed(self):
        collectors = {"openrouter": lambda: snapshot("openrouter", "url", "official_api", {"Usage": board()})}
        with patch("main.COLLECTORS", collectors), patch("utils.notifier.HubNotifier") as notifier:
            self.assertEqual(0, run_pipeline(self.root / "data", self.root / "reports"))
            notifier.assert_not_called()
            notifier.return_value.send_all.return_value = False
            self.assertEqual(1, run_pipeline(self.root / "data", self.root / "reports", notify=True, allow_partial=True))

    def test_every_configured_notification_channel_must_succeed(self):
        from utils.notifier import HubNotifier
        hub = HubNotifier()
        from unittest.mock import Mock
        hub.notifiers = [Mock(), Mock()]
        hub.notifiers[0].send.return_value = True
        hub.notifiers[1].send.return_value = False
        self.assertFalse(hub.send_all("report"))


if __name__ == "__main__":
    unittest.main()
