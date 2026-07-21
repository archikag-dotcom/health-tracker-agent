"""
Unit tests for Golden Dataset Regression Eval Harness, SecretManager, and Agent CLI.
"""
import unittest
import os
from tests.eval_harness import RegressionEvalHarness
from services.secrets import SecretManager


class TestHarnessAndSecrets(unittest.TestCase):

    def test_golden_dataset_eval_harness(self):
        """Verify regression evaluation harness measures macro accuracy against golden dataset."""
        harness = RegressionEvalHarness(golden_dataset_path="tests/golden_dataset.json")
        metrics = harness.run_eval(max_allowed_mape=5.0)

        self.assertEqual(metrics.total_test_cases, 5)
        self.assertTrue(metrics.passed_threshold)
        self.assertLessEqual(metrics.overall_mape_pct, 5.0)
        self.assertGreaterEqual(metrics.passed_cases, 5)

    def test_secret_manager_injection(self):
        """Verify SecretManager injects credentials securely without hardcoded plain text keys."""
        # Test env variable injection
        os.environ["TEST_SECRET_KEY"] = "super_secret_12345"
        val = SecretManager.get_secret("TEST_SECRET_KEY")
        self.assertEqual(val, "super_secret_12345")

        # Test API key secure retrieval
        api_key = SecretManager.get_api_key()
        self.assertIsNotNone(api_key)
        self.assertGreater(len(api_key), 0)


if __name__ == "__main__":
    unittest.main()
