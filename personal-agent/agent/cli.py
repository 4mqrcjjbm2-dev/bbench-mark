"""Tester l'agent dans le terminal : python -m agent.cli "Quel est le prix du bitcoin ?" """

import sys

from .config import load_settings
from .core import Agent


def main() -> None:
    agent = Agent(load_settings())
    question = " ".join(sys.argv[1:])
    if question:
        r = agent.ask(question, "terminal")
        print(r.text, f"\n[action iPhone] {r.iphone_action}" if r.iphone_action else "")
        return
    print("Agent personnel — tape 'quit' pour sortir, 'reset' pour une nouvelle conversation.")
    while (q := input("> ").strip()) not in {"quit", "exit"}:
        if q == "reset":
            agent.reset("terminal")
            continue
        if q:
            r = agent.ask(q, "terminal")
            print(r.text, f"\n[action iPhone] {r.iphone_action}" if r.iphone_action else "")


if __name__ == "__main__":
    main()
