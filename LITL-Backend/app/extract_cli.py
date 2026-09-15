"""Resource-isolated parser entrypoint. Never makes network requests."""
import json
import resource
import sys

from .config import MAX_FILE_BYTES
from .extraction import ExtractionError, extract


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    if sys.platform != "darwin":
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    try:
        result = extract(sys.argv[1], sys.stdin.buffer.read(MAX_FILE_BYTES + 1))
    except ExtractionError as exc:
        result = {"error": str(exc)}
    except Exception:
        # Untrusted parser diagnostics must never contain document content.
        result = {"error": "Malformed file or unsupported extraction structure"}
    sys.stdout.write(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
