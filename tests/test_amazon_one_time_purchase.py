import unittest

from scripts.price_check_one_asin_db import (
    get_selected_new_buybox_row,
    select_one_time_purchase,
)


class FakeRadio:
    def __init__(self, active: bool) -> None:
        self.active = active

    @property
    def first(self):
        return self

    async def get_attribute(self, name: str):
        self.assert_name = name
        return "a-icon-radio-active" if self.active else "a-icon-radio-inactive"


class FakeHeader:
    def __init__(self, active: bool, visible: bool = True) -> None:
        self.radio = FakeRadio(active)
        self.visible = visible
        self.clicked = False

    @property
    def first(self):
        return self

    def locator(self, selector: str):
        if selector == ".a-accordion-radio":
            return self.radio
        raise AssertionError(selector)

    async def is_visible(self, **_kwargs) -> bool:
        return self.visible

    async def get_attribute(self, name: str):
        if name == "aria-expanded":
            return "true" if self.radio.active else "false"
        raise AssertionError(name)

    async def scroll_into_view_if_needed(self, **_kwargs) -> None:
        return None

    async def click(self, **_kwargs) -> None:
        self.clicked = True

    async def evaluate(self, _script: str) -> None:
        self.clicked = True


class FakeRow:
    def __init__(self, header: FakeHeader) -> None:
        self.header = header

    def locator(self, selector: str):
        if selector == ".a-accordion-row-a11y":
            return self.header
        raise AssertionError(selector)

    async def is_visible(self, **_kwargs) -> bool:
        return True

    async def get_attribute(self, name: str):
        if name == "class":
            return "a-box a-accordion-active" if self.header.radio.active else "a-box"
        raise AssertionError(name)


class FakeRows:
    def __init__(self, rows) -> None:
        self.rows = rows

    async def count(self) -> int:
        return len(self.rows)

    def nth(self, index: int):
        return self.rows[index]


class FakePage:
    def __init__(self, rows) -> None:
        self.rows = FakeRows(rows)
        self.waits = []

    def locator(self, _selector: str):
        return self.rows

    async def wait_for_timeout(self, timeout: int) -> None:
        self.waits.append(timeout)


class AmazonOneTimePurchaseTests(unittest.IsolatedAsyncioTestCase):
    async def test_selects_inactive_one_time_purchase_row(self) -> None:
        header = FakeHeader(active=False)
        page = FakePage([FakeRow(header)])

        self.assertTrue(await select_one_time_purchase(page))
        self.assertTrue(header.clicked)
        self.assertEqual(page.waits, [750])

    async def test_keeps_active_one_time_purchase_row(self) -> None:
        header = FakeHeader(active=True)
        page = FakePage([FakeRow(header)])

        self.assertFalse(await select_one_time_purchase(page))
        self.assertFalse(header.clicked)
        self.assertEqual(page.waits, [])

    async def test_selected_row_excludes_inactive_used_sibling(self) -> None:
        new_row = FakeRow(FakeHeader(active=True))
        used_row = FakeRow(FakeHeader(active=False))
        page = FakePage([new_row, used_row])

        self.assertIs(await get_selected_new_buybox_row(page), new_row)


if __name__ == "__main__":
    unittest.main()
