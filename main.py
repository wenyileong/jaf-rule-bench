"""Entry point for the JAF Rule Bench executable."""
import multiprocessing
from app.server import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
