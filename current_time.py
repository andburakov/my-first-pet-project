#!/usr/bin/env python3
"""Print the current local time."""

from datetime import datetime


def main() -> None:
    print(datetime.now().astimezone().strftime("%H:%M:%S"))


if __name__ == "__main__":
    main()
