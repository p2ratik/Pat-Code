"""Shelter that manages a collection of animals."""

from animals import Dog, Cat
from base import Animal


SHELTER_NAME = "City Shelter"


class Shelter:
    def __init__(self) -> None:
        self._residents: list[Animal] = []

    def admit(self, animal: Animal) -> None:
        self._residents.append(animal)

    def count(self) -> int:
        return len(self._residents)

    def make_noise(self) -> list[str]:
        return [a.speak() for a in self._residents]
