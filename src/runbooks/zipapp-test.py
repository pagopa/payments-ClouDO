# Python
# __main__.py
import json
import sys
import time


def main(argv=None) -> int:
    """Entry point of the runbook zipapp."""
    argv = argv or sys.argv[1:]
    # Simple args parsing (replace with argparse if needed)
    name = "world"
    for i, a in enumerate(argv):
        if a in ("-n", "--name") and i + 1 < len(argv):
            name = argv[i + 1]

    # Simulate some work
    started = time.time()
    time.sleep(0.3)
    duration_ms = int((time.time() - started) * 1000)

    # Print a structured JSON result to stdout
    result = {
        "status": "ok",
        "message": f"Hello, {name}!",
        "duration_ms": duration_ms,
    }
    print(json.dumps(result, ensure_ascii=False))

    # Exit code 0 = success
    return 0


if __name__ == "__main__":
    sys.exit(main())
