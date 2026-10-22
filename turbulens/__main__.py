"""Punto de entrada: ``python -m turbulens`` (``--autoprueba`` para la prueba sin ventana)."""
import sys

if __name__ == "__main__":
    if "--autoprueba" in sys.argv:
        from turbulens.selftest import run

        raise SystemExit(run(sys.argv[1:]))
    from turbulens.gui.app import main

    raise SystemExit(main())
