from __future__ import annotations

import unittest

from src.common.config import collection_config, iter_search_queries, load_yaml


class ConfigTests(unittest.TestCase):
    def test_search_layers_load(self) -> None:
        config = load_yaml("configs/search_layers.yaml")
        entries = iter_search_queries(config, "all")
        self.assertTrue(entries)
        self.assertEqual(entries[0]["search_layer"], "discovery")
        collection = collection_config(config)
        self.assertEqual(collection["display"], 20)
        self.assertEqual(collection["raw_retention_days"], 7)


if __name__ == "__main__":
    unittest.main()

