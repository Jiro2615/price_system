"""Offline tests of the production AOD loading logic; no DB/browser access."""
import ast
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, Mock


def loader():
    source = Path(__file__).parents[1] / "scripts/price_check_one_asin_db.py"
    tree = ast.parse(source.read_text(encoding="utf-8-sig"))
    names = {"open_all_offers", "read_lowest_amazon_fulfilled_offer_with_status"}
    node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name in names)
    # Price checker combines loading and parsing. Exercise its unchanged
    # production loading statements up to the candidate parsing phase.
    statements = []
    for statement in node.body:
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name) and statement.target.id == "candidates":
            break
        statements.append(statement)
    node.body = statements
    node.returns = None
    async def click_force(element):
        await element.click()
    namespace = {"click_force": click_force}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(source), "exec"), namespace)
    return namespace[node.name]


class OfferLoadingTests(unittest.IsolatedAsyncioTestCase):
    def page(self, total="75", *, stalled=False, scroll=False, fail=False):
        state = {"loaded": 10, "loads": 0}
        offers = Mock()
        offers.count = AsyncMock(side_effect=lambda: state["loaded"])
        offers.first.wait_for = AsyncMock()
        ingress = Mock()
        ingress.count = AsyncMock(return_value=1)
        ingress.first = ingress
        ingress.click = AsyncMock()
        total_node = Mock()
        total_node.first = total_node
        total_node.get_attribute = AsyncMock(return_value=total)
        more = Mock()
        more.first = more
        more.count = AsyncMock(return_value=0 if scroll else 1)
        more.is_visible = AsyncMock(return_value=True)
        scroller = Mock()
        scroller.first = scroller
        scroller.count = AsyncMock(return_value=1)
        scroller.is_visible = AsyncMock(return_value=True)
        async def advance(*args, **kwargs):
            state["loads"] += 1
            if fail:
                raise RuntimeError("network")
            if not stalled:
                state["loaded"] = min(state["loaded"] + 10, int(total or "30"))
        more.click = AsyncMock(side_effect=advance)
        scroller.evaluate = AsyncMock(side_effect=advance)
        nodes = {"#aod-ingress-link": ingress, "#aod-offer-list #aod-offer": offers,
                 "#aod-total-offer-count": total_node, "#aod-show-more-offers": more,
                 "#all-offers-display-scroller": scroller}
        page = Mock()
        page.locator.side_effect = nodes.__getitem__
        page.wait_for_timeout = AsyncMock()
        async def wait_for_function(expression, **kwargs):
            if 'arg' in kwargs and state['loaded'] <= kwargs['arg']:
                raise TimeoutError('delayed response timed out')
        page.wait_for_function = AsyncMock(side_effect=wait_for_function)
        return page, state

    async def test_more_button_loads_all_75(self):
        page, state = self.page()
        await loader()(page)
        self.assertEqual(state["loaded"], 75)
        self.assertEqual(state["loads"], 7)

    async def test_scroll_loads_all_105(self):
        page, state = self.page("105", scroll=True)
        await loader()(page)
        self.assertEqual(state["loaded"], 105)

    async def test_small_complete_list(self):
        page, state = self.page("10")
        await loader()(page)
        self.assertEqual(state["loads"], 0)

    async def test_stalled_list_is_not_success(self):
        page, state = self.page(stalled=True)
        with self.assertRaisesRegex(RuntimeError, "読み込み未完了"):
            await loader()(page)
        self.assertEqual(state["loads"], 1)
        self.assertEqual(page.wait_for_function.call_args.kwargs['timeout'], 15000)

    async def test_unknown_total_is_not_success(self):
        page, state = self.page("", stalled=True)
        with self.assertRaisesRegex(RuntimeError, "総件数 不明"):
            await loader()(page)

    async def test_loading_error_is_not_success(self):
        page, state = self.page(fail=True)
        with self.assertRaisesRegex(RuntimeError, "読み込み未完了"):
            await loader()(page)

    async def test_initial_timeout_is_not_no_candidates(self):
        page, state = self.page()
        page.locator('#aod-offer-list #aod-offer').first.wait_for.side_effect = TimeoutError('initial')
        with self.assertRaisesRegex(RuntimeError, '初期表示'):
            await loader()(page)

    async def test_late_response_waits_for_progress(self):
        page, state = self.page('20', stalled=True)
        async def delayed(expression, **kwargs):
            if 'arg' in kwargs:
                self.assertEqual(kwargs['timeout'], 15000)
                state['loaded'] = 20
        page.wait_for_function.side_effect = delayed
        await loader()(page)
        self.assertEqual(state['loaded'], 20)
        self.assertEqual(state['loads'], 1)

    async def test_skeleton_cards_are_not_no_candidates(self):
        page, state = self.page('10')
        page.wait_for_function.side_effect = TimeoutError('empty content')
        with self.assertRaisesRegex(RuntimeError, '出品内容'):
            await loader()(page)


if __name__ == "__main__":
    unittest.main()
