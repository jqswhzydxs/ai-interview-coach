from dataclasses import dataclass
from pathlib import Path


class PromptNotFoundError(FileNotFoundError):
    pass


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    path: Path
    content: str


def prompt_dir() -> Path:
    return Path(__file__).parent / "prompts"


def load_prompt(name: str, version: str) -> Prompt:
    path = prompt_dir() / f"{name}_{version}.md"
    if not path.exists():
        raise PromptNotFoundError(f"Prompt not found: {path.name}")
    return Prompt(
        name=name,
        version=version,
        path=path,
        content=path.read_text(encoding="utf-8"),
    )
