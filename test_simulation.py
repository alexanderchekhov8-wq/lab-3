"""Проверки правил отдельных очередей на заданных временах прихода."""

import unittest
from unittest.mock import Mock

import numpy as np

from simulation import generate_day, serve


class QueueTests(unittest.TestCase):
    def test_single_cashier_and_overtime(self):
        metrics, waits = serve([0, 1, 2], [3, 3, 3], 1, 5, 1, np.random.default_rng(42))
        np.testing.assert_allclose(waits, [0, 2, 4])
        self.assertEqual(metrics["utilization"], 1)
        self.assertEqual(metrics["overtime_min"], 4)

    def test_parallel_service(self):
        _, waits = serve([0, 0], [10, 10], 2, 20, 5, np.random.default_rng(42))
        np.testing.assert_allclose(waits, [0, 0])

    def test_tie_counts_served_person_and_no_switching(self):
        # В t=1 у каждой кассы по человеку, но касса 0 занята до t=10.
        # Покупатель выбирает её случайно и ждёт до t=10, даже когда
        # касса 1 освобождается в t=2. Новый покупатель в t=2 идёт к кассе 1.
        rng = Mock()
        rng.choice.side_effect = [0, 0]
        metrics, waits = serve([0, 0, 1, 2], [10, 2, 1, 1], 2, 5, 5, rng)
        np.testing.assert_allclose(waits, [0, 0, 9, 0])
        self.assertEqual(rng.choice.call_count, 2)
        for call in rng.choice.call_args_list:
            self.assertEqual(call.args[0], [0, 1])
        self.assertEqual(metrics["utilization"], 0.8)
        self.assertEqual(metrics["overtime_min"], 6)

    def test_variant_set_does_not_change_existing_results(self):
        def experiment(counts):
            rng = np.random.default_rng(42)
            result = {}
            for day in range(1, 4):
                arrivals, services = generate_day(rng, 20, 2, 60)
                for count in counts:
                    routing_rng = np.random.default_rng(np.random.SeedSequence([42, day, count, 1]))
                    result[day, count] = serve(arrivals, services, count, 60, 5, routing_rng)[1]
            return result
        original = experiment([2])
        extended = experiment([1, 2, 3])
        for key in original:
            np.testing.assert_array_equal(original[key], extended[key])


if __name__ == "__main__":
    unittest.main()
