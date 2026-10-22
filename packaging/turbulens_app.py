"""Punto de entrada para el ejecutable empaquetado."""
import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    if "--autoprueba" in sys.argv:
        from turbulens.selftest import run

        sys.exit(run(sys.argv[1:]))
    from turbulens.gui.app import main

    sys.exit(main())
