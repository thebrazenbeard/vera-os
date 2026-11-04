from __future__ import annotations

import unittest

from veraos.host_model_readiness import (
    HostModelObservationError,
    classify_host_model_observation,
)


def observation() -> dict:
    return {
        "schema": "VERAOS_HOST_MODEL_OBSERVATION_V1",
        "host_id": "Lappy",
        "os": "windows",
        "backend": "ollama",
        "endpoint": "http://127.0.0.1:11434",
        "model_id": "vera-qwen35:trial-20261029",
        "observed_at": "2026-11-04T15:00:00Z",
        "process_seen": True,
        "catalogued_models": ["vera-qwen35:trial-20261029"],
        "resident_models": [],
        "endpoint_health": {"healthy": False, "model_id": None},
    }


class HostModelObservationTests(unittest.TestCase):
    def test_catalogued_model_is_not_ready_or_qualified(self) -> None:
        result = classify_host_model_observation(observation())
        self.assertEqual(result["observed_state"], "MODEL_CATALOGUED")
        self.assertFalse(result["inference_qualified"])
        self.assertFalse(result["route_eligible"])

    def test_health_of_different_model_cannot_promote_target(self) -> None:
        item = observation()
        item["endpoint_health"] = {"healthy": True, "model_id": "other-model"}
        result = classify_host_model_observation(item)
        self.assertEqual(result["observed_state"], "MODEL_CATALOGUED")
        self.assertFalse(result["route_eligible"])

    def test_exact_model_endpoint_observation_still_grants_no_authority(self) -> None:
        item = observation()
        item["endpoint_health"] = {"healthy": True, "model_id": item["model_id"]}
        result = classify_host_model_observation(item)
        self.assertEqual(result["observed_state"], "EXACT_MODEL_ENDPOINT_OBSERVED")
        self.assertFalse(result["inference_qualified"])
        self.assertFalse(result["route_eligible"])

    def test_resident_only_state_does_not_infer_endpoint_ready(self) -> None:
        item = observation()
        item["resident_models"] = [item["model_id"]]
        result = classify_host_model_observation(item)
        self.assertEqual(result["observed_state"], "MODEL_RESIDENT")
        self.assertFalse(result["route_eligible"])

    def test_rejects_self_asserted_ready_state(self) -> None:
        item = observation()
        item["claimed_state"] = "READY"
        with self.assertRaises(HostModelObservationError):
            classify_host_model_observation(item)

    def test_rejects_nonloopback_remote_endpoint(self) -> None:
        item = observation()
        item["endpoint"] = "https://lappy.tailnet.ts.net:11434"
        with self.assertRaises(HostModelObservationError):
            classify_host_model_observation(item)

    def test_rejects_bad_observation_types_and_timestamps(self) -> None:
        item = observation()
        item["process_seen"] = "true"
        with self.assertRaises(HostModelObservationError):
            classify_host_model_observation(item)

    def test_rejects_unhashable_os_and_backend_with_domain_error(self) -> None:
        for key in ("os", "backend"):
            item = observation()
            item[key] = []
            with self.assertRaises(HostModelObservationError):
                classify_host_model_observation(item)

    def test_rejects_embedded_controls_in_loopback_origin(self) -> None:
        item = observation()
        item["endpoint"] = "http://127.0.0.1:\n11434"
        with self.assertRaises(HostModelObservationError):
            classify_host_model_observation(item)

    def test_rejects_empty_query_and_fragment_delimiters_on_origin(self) -> None:
        for suffix in ("?", "#"):
            item = observation()
            item["endpoint"] += suffix
            with self.assertRaises(HostModelObservationError):
                classify_host_model_observation(item)

    def test_rejects_non_rfc3339_timestamp_even_if_datetime_accepts_it(self) -> None:
        for stamp in ("2026-11-04", "2026-11-04 15:00:00Z", "2026-11-04T15:00Z"):
            item = observation()
            item["observed_at"] = stamp
            with self.assertRaises(HostModelObservationError):
                classify_host_model_observation(item)

    def test_rejects_controls_in_requested_or_advertised_model_ids(self) -> None:
        for key in ("model_id", "catalogued_models", "resident_models"):
            item = observation()
            if key == "model_id":
                item[key] = "qwen\n5"
            else:
                item[key] = ["qwen\n5"]
            with self.assertRaises(HostModelObservationError):
                classify_host_model_observation(item)
        item = observation()
        item["endpoint_health"]["model_id"] = "qwen\n5"
        with self.assertRaises(HostModelObservationError):
            classify_host_model_observation(item)

    def test_endpoint_evidence_outweighs_process_name_probe(self) -> None:
        item = observation()
        item["process_seen"] = False
        item["resident_models"] = [item["model_id"]]
        self.assertEqual(classify_host_model_observation(item)["observed_state"], "MODEL_RESIDENT")
        item["endpoint_health"] = {"healthy": True, "model_id": item["model_id"]}
        result = classify_host_model_observation(item)
        self.assertEqual(result["observed_state"], "EXACT_MODEL_ENDPOINT_OBSERVED")
        self.assertFalse(result["route_eligible"])
        item = observation()
        item["observed_at"] = "yesterday"
        with self.assertRaises(HostModelObservationError):
            classify_host_model_observation(item)


if __name__ == "__main__":
    unittest.main()
