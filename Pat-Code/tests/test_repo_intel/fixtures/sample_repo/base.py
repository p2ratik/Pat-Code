"""Base classes for the sample fixture repo."""

import os


BASE_CONSTANT = "base"


class Animal:
    def speak(self) -> str:
        raise NotImplementedError

    def breathe(self) -> None:
        pass
