"""Input de teclado para terminal."""
from __future__ import annotations

import sys


def read_key() -> str:
    """Lê uma tecla e retorna string semântica."""
    if sys.platform == "win32":
        import msvcrt
        ch = msvcrt.getwch()
        if ch in ("\x00", "à"):
            ch2 = msvcrt.getwch()
            return {
                "H": "up", "P": "down", "K": "left", "M": "right",
            }.get(ch2, ch2)
        if ch == "\r":
            return "enter"
        if ch in ("\x1b", "q", "Q"):
            return "q"
        if ch == "\x03":
            return "q"
        return ch
    else:
        import tty, termios
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                ch2 = sys.stdin.read(1)
                if ch2 == "[":
                    ch3 = sys.stdin.read(1)
                    return {
                        "A": "up", "B": "down", "C": "right", "D": "left",
                    }.get(ch3, ch3)
                return "q"
            if ch in ("\r", "\n"):
                return "enter"
            if ch in ("q", "Q", "\x03"):
                return "q"
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
