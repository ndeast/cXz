"""Main entry point for cXz vinyl record cataloging TUI."""

import asyncio
import sys
from typing import NoReturn

from cxz.tui.app import CxzApp


def main() -> NoReturn:
    """Main entry point for the cXz application."""
    try:
        app = CxzApp()
        asyncio.run(app.run_async())
    except KeyboardInterrupt:
        print("\nExiting cXz...")
        sys.exit(0)
    except Exception as e:
        print(f"Error running cXz: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
