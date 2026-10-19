# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Wen Yi LEONG
"""Entry point for the JAF Rule Bench executable."""
import multiprocessing
from app.server import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
