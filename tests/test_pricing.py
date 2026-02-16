from __future__ import annotations

import unittest

from venta_app.pricing import calculate_auto_price, round_to_nearest_base


class PricingTestCase(unittest.TestCase):
    def test_rounding_to_nearest_hundred_examples(self) -> None:
        self.assertEqual(round_to_nearest_base(5535, 100), 5500)
        self.assertEqual(round_to_nearest_base(5580, 100), 5600)
        self.assertEqual(round_to_nearest_base(6101, 100), 6100)

    def test_calculate_auto_price(self) -> None:
        self.assertEqual(calculate_auto_price(1000, 30, 100), 1300)
        self.assertEqual(calculate_auto_price(1575, 35, 100), 2100)


if __name__ == "__main__":
    unittest.main()
