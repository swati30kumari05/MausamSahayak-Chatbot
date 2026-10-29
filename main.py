"""Launch the MausamSahayak Telegram Bot (Swati's Module)."""
import os
import sys

# Ensure package directory is on path
root = os.path.dirname(os.path.abspath(__file__))
if root not in sys.path:
    sys.path.insert(0, root)

from swati_bot.bot import main

if __name__ == "__main__":
    main()
