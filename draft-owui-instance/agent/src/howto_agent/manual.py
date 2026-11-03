"""Load the source-controlled Open WebUI instruction manual."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import yaml


_HEADING_PATTERN = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_UI_REFERENCE_PATTERN = re.compile(r"\[ui:([^\]]+)\]")
_RECIPE_REFERENCE_PATTERN = re.compile(r"\[recipe:([^\]]+)\]")


class ManualDefinitionError(ValueError):
    """Raised when the instruction manual does not match the draft schema."""


@dataclass(frozen=True, slots=True)
class ManualSection:
    """One addressable level-two section from the instruction manual."""

    id: str
    title: str
    markdown: str


class InstructionManual:
    """Parsed manual metadata, sections, and semantic references."""

    def __init__(
        self,
        *,
        metadata: Mapping[str, Any],
        preamble: str,
        sections: tuple[ManualSection, ...],
        ui_references: frozenset[str],
        recipe_references: frozenset[str],
    ) -> None:
        self._metadata = deepcopy(dict(metadata))
        self._preamble = preamble
        self._sections = sections
        self._sections_by_id = {section.id: section for section in sections}
        self._ui_references = ui_references
        self._recipe_references = recipe_references

    @classmethod
    def from_markdown(cls, path: str | Path) -> InstructionManual:
        """Load a UTF-8 Markdown manual with YAML frontmatter."""

        manual_path = Path(path)
        try:
            text = manual_path.read_text(encoding="utf-8")
        except OSError as error:
            raise ManualDefinitionError(
                f"could not load instruction manual from {manual_path}"
            ) from error

        metadata, markdown = cls._split_frontmatter(text)
        cls._validate_metadata(metadata)
        preamble, sections = cls._parse_sections(markdown)

        return cls(
            metadata=metadata,
            preamble=preamble,
            sections=sections,
            ui_references=frozenset(_UI_REFERENCE_PATTERN.findall(markdown)),
            recipe_references=frozenset(
                _RECIPE_REFERENCE_PATTERN.findall(markdown)
            ),
        )

    @property
    def metadata(self) -> dict[str, Any]:
        return deepcopy(self._metadata)

    @property
    def preamble(self) -> str:
        return self._preamble

    @property
    def sections(self) -> tuple[ManualSection, ...]:
        return self._sections

    @property
    def ui_references(self) -> frozenset[str]:
        return self._ui_references

    @property
    def recipe_references(self) -> frozenset[str]:
        return self._recipe_references

    def get_section(self, section_id: str) -> ManualSection | None:
        """Return an addressable section by its generated slug."""

        return self._sections_by_id.get(section_id)

    def validate_references(
        self,
        *,
        allowed_targets: set[str] | frozenset[str],
        allowed_recipes: set[str] | frozenset[str],
    ) -> None:
        """Reject semantic references absent from the corresponding registry."""

        missing_targets = sorted(self.ui_references - set(allowed_targets))
        missing_recipes = sorted(self.recipe_references - set(allowed_recipes))
        problems = []
        if missing_targets:
            problems.append(f"unknown UI references: {', '.join(missing_targets)}")
        if missing_recipes:
            problems.append(
                f"unknown recipe references: {', '.join(missing_recipes)}"
            )
        if problems:
            raise ManualDefinitionError("; ".join(problems))

    @staticmethod
    def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
        normalized = text.lstrip("\ufeff")
        if not normalized.startswith("---\n"):
            raise ManualDefinitionError("instruction manual requires YAML frontmatter")

        try:
            frontmatter_text, markdown = normalized[4:].split("\n---\n", 1)
        except ValueError as error:
            raise ManualDefinitionError(
                "instruction manual frontmatter is not terminated"
            ) from error

        try:
            metadata = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as error:
            raise ManualDefinitionError(
                "instruction manual frontmatter is invalid YAML"
            ) from error
        if not isinstance(metadata, Mapping):
            raise ManualDefinitionError("manual frontmatter must be a mapping")
        return dict(metadata), markdown.strip()

    @staticmethod
    def _validate_metadata(metadata: Mapping[str, Any]) -> None:
        for key in ("id", "title", "version", "status"):
            value = metadata.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ManualDefinitionError(
                    f"manual frontmatter requires a non-empty '{key}'"
                )

    @staticmethod
    def _parse_sections(markdown: str) -> tuple[str, tuple[ManualSection, ...]]:
        matches = list(_HEADING_PATTERN.finditer(markdown))
        if not matches:
            raise ManualDefinitionError("instruction manual requires level-two sections")

        preamble = markdown[: matches[0].start()].strip()
        sections = []
        seen_ids: set[str] = set()

        for index, match in enumerate(matches):
            title = match.group(1).strip()
            section_id = InstructionManual._slugify(title)
            if not section_id:
                raise ManualDefinitionError(f"manual heading has no usable ID: {title}")
            if section_id in seen_ids:
                raise ManualDefinitionError(f"duplicate manual section ID: {section_id}")

            end = matches[index + 1].start() if index + 1 < len(matches) else None
            section_markdown = markdown[match.end() : end].strip()
            if not section_markdown:
                raise ManualDefinitionError(f"manual section is empty: {section_id}")

            sections.append(
                ManualSection(
                    id=section_id,
                    title=title,
                    markdown=section_markdown,
                )
            )
            seen_ids.add(section_id)

        return preamble, tuple(sections)

    @staticmethod
    def _slugify(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
        return slug

