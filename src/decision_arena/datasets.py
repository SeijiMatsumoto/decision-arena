from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

QuestionType = Literal["noul", "choice", "score"]


class Question(BaseModel):
    """One Decisions API question. `criteria` carries the meaning; the key is never sent."""

    type: QuestionType
    instructions: str
    criteria: dict[str, str] | list[str]

    @model_validator(mode="after")
    def check_criteria(self) -> Question:
        if self.type == "noul" and (
            not isinstance(self.criteria, dict) or set(self.criteria) != {"true", "false"}
        ):
            raise ValueError("noul criteria must be a mapping with exactly 'true' and 'false'")
        if self.type == "choice" and not isinstance(self.criteria, dict):
            raise ValueError("choice criteria must map option -> description")
        if self.type == "score" and not isinstance(self.criteria, list):
            raise ValueError("score criteria must be a list of levels, lowest first")
        return self

    @property
    def labels(self) -> list[str]:
        """Every label a prediction can take, as strings."""
        if self.type == "score":
            return [str(i) for i in range(len(self.criteria))]
        return list(self.criteria)

    def to_api(self) -> dict[str, Any]:
        return {"type": self.type, "instructions": self.instructions, "criteria": self.criteria}


class Example(BaseModel):
    id: str
    state: dict[str, Any] | str
    expected: bool | str | int
    tags: list[str] = Field(default_factory=list)
    # Examples sharing a group are candidates for the same query; enables ranking metrics.
    group: str | None = None
    note: str | None = None

    @property
    def expected_label(self) -> str:
        if isinstance(self.expected, bool):
            return "true" if self.expected else "false"
        return str(self.expected)


class Dataset(BaseModel):
    name: str
    description: str
    use_case: str
    question: Question
    examples: list[Example]

    @model_validator(mode="after")
    def check_examples(self) -> Dataset:
        labels = set(self.question.labels)
        seen: set[str] = set()
        for example in self.examples:
            if example.id in seen:
                raise ValueError(f"{self.name}: duplicate example id {example.id}")
            seen.add(example.id)
            if example.expected_label not in labels:
                raise ValueError(
                    f"{self.name}/{example.id}: expected {example.expected!r} not in {sorted(labels)}"
                )
        return self


def load_dataset(path: Path) -> Dataset:
    return Dataset.model_validate(yaml.safe_load(path.read_text()))


def load_datasets(directory: Path, names: list[str] | None = None) -> list[Dataset]:
    datasets = [load_dataset(path) for path in sorted(directory.glob("*.yaml"))]
    if names:
        unknown = set(names) - {d.name for d in datasets}
        if unknown:
            raise SystemExit(f"Unknown dataset(s): {', '.join(sorted(unknown))}")
        datasets = [d for d in datasets if d.name in names]
    return datasets
