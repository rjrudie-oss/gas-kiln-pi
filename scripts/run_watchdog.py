#!/usr/bin/env python3
"""Entry point for the independent fail-safe watchdog."""
from kiln_controller.safety.watchdog import main

if __name__ == "__main__":
    raise SystemExit(main())
