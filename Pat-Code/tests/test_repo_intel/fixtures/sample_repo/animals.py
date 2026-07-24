"""Concrete animal implementations — inherits from base.Animal."""

from base import Animal


MAX_LEGS = 4


class Dog(Animal):
    def speak(self) -> str:
        return "woof"

    def fetch(self, item: str) -> str:
        return f"fetched {item}"


class Cat(Animal):
    def speak(self) -> str:
        return "meow"

    def purr(self) -> None:
        pass
