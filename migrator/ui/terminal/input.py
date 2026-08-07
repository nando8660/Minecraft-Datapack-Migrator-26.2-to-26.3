"""Interface de terminal - Entrada por teclado."""
from __future__ import annotations

import sys
import os

if sys.platform == "win32":
    import msvcrt

    def read_key() -> str:
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            ch2 = msvcrt.getwch()
            if ch2 == "H":
                return "up"
            if ch2 == "P":
                return "down"
            if ch2 == "K":
                return "left"
            if ch2 == "M":
                return "right"
            if ch2 == "s":
                return "left"
            if ch2 == "d":
                return "right"
            return ""
        if ch == "\r":
            return "enter"
        if ch == "\x1b":
            return "q"
        if ch.lower() == "q":
            return "q"
        return ""
else:
    import tty
    import termios

    def read_key() -> str:
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                ch2 = sys.stdin.read(1)
                if ch2 == "[":
                    ch3 = sys.stdin.read(1)
                    if ch3 == "A":
                        return "up"
                    if ch3 == "B":
                        return "down"
                    if ch3 == "C":
                        return "right"
                    if ch3 == "D":
                        return "left"
                return "q"
            if ch == "\r":
                return "enter"
            if ch.lower() == "q":
                return "q"
            return ""
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
