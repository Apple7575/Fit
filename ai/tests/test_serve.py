import unittest

from fastapi.testclient import TestClient

from ai.serve import build_app


class AiServeTest(unittest.TestCase):
    def test_mounts_position_service(self):
        client = TestClient(build_app())

        health = client.get("/health")
        position_health = client.get("/position/health")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["services"]["position"], "/position")
        self.assertEqual(position_health.status_code, 200)


if __name__ == "__main__":
    unittest.main()
