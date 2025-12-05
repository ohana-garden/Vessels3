#!/usr/bin/env python3
"""
Health check script for Vessels container.

Checks:
1. FalkorDB is running and loaded
2. FalkorDB graph module is available
3. Vessels API is responding
4. Database operations are working
"""

import sys
import os

# Add app to path
sys.path.insert(0, "/app")


def check_falkordb() -> bool:
    """Check FalkorDB connectivity and readiness."""
    try:
        from redis import Redis

        host = os.environ.get("FALKORDB_HOST", "localhost")
        port = int(os.environ.get("FALKORDB_PORT", 6379))
        password = os.environ.get("FALKORDB_PASSWORD")

        client = Redis(host=host, port=port, password=password, decode_responses=True)

        # Basic ping
        if not client.ping():
            print("FAIL: FalkorDB ping failed")
            return False

        # Check module loaded
        modules = client.module_list()
        graph_loaded = any(
            m.get("name", "").lower() in ("graph", "falkordb") for m in modules
        )
        if not graph_loaded:
            print("FAIL: FalkorDB graph module not loaded")
            return False

        # Check not loading
        info = client.info("persistence")
        if info.get("loading", 0) == 1:
            print("FAIL: FalkorDB still loading data")
            return False

        print("OK: FalkorDB healthy")
        return True

    except Exception as e:
        print(f"FAIL: FalkorDB check failed: {e}")
        return False


def check_vessels_api() -> bool:
    """Check Vessels API is responding."""
    try:
        import httpx

        response = httpx.get("http://localhost:8000/health", timeout=5.0)

        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "healthy":
                print("OK: Vessels API healthy")
                return True
            else:
                print(f"FAIL: Vessels API unhealthy: {data}")
                return False
        else:
            print(f"FAIL: Vessels API returned {response.status_code}")
            return False

    except Exception as e:
        print(f"FAIL: Vessels API check failed: {e}")
        return False


def check_graph_operations() -> bool:
    """Check graph operations are working."""
    try:
        from falkordb import FalkorDB

        host = os.environ.get("FALKORDB_HOST", "localhost")
        port = int(os.environ.get("FALKORDB_PORT", 6379))
        password = os.environ.get("FALKORDB_PASSWORD")

        client = FalkorDB(host=host, port=port, password=password)
        graph = client.select_graph("__healthcheck__")

        # Simple query
        result = graph.query("RETURN 1 as test")
        if not result.result_set:
            print("FAIL: Graph query returned no results")
            return False

        print("OK: Graph operations working")
        return True

    except Exception as e:
        print(f"FAIL: Graph operations check failed: {e}")
        return False


def main() -> int:
    """Run all health checks."""
    print("=== Vessels Health Check ===")

    checks = [
        ("FalkorDB", check_falkordb),
        ("Graph Operations", check_graph_operations),
        ("Vessels API", check_vessels_api),
    ]

    all_passed = True
    for name, check_fn in checks:
        try:
            if not check_fn():
                all_passed = False
        except Exception as e:
            print(f"FAIL: {name} check threw exception: {e}")
            all_passed = False

    print("")
    if all_passed:
        print("=== All checks passed ===")
        return 0
    else:
        print("=== Some checks failed ===")
        return 1


if __name__ == "__main__":
    sys.exit(main())
