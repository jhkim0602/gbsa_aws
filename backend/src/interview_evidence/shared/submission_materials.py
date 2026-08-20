from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SubmissionMaterialType(StrEnum):
    RESUME = "resume"
    COVER_LETTER = "cover_letter"
    CAREER_DESCRIPTION = "career_description"
    PROJECTS = "projects"
    PORTFOLIO = "portfolio"


class SubmissionRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    material_type: SubmissionMaterialType
    required: bool = True
    enabled: bool = True
    instructions: str | None = Field(default=None, max_length=1000)


DEFAULT_SUBMISSION_REQUIREMENTS: tuple[SubmissionRequirement, ...] = (
    SubmissionRequirement(
        material_type=SubmissionMaterialType.RESUME,
        required=True,
    ),
    SubmissionRequirement(
        material_type=SubmissionMaterialType.COVER_LETTER,
        required=True,
    ),
    SubmissionRequirement(
        material_type=SubmissionMaterialType.CAREER_DESCRIPTION,
        required=False,
    ),
    SubmissionRequirement(
        material_type=SubmissionMaterialType.PROJECTS,
        required=False,
    ),
    SubmissionRequirement(
        material_type=SubmissionMaterialType.PORTFOLIO,
        required=False,
    ),
)


class SubmissionRequirementSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[SubmissionRequirement, ...] = DEFAULT_SUBMISSION_REQUIREMENTS

    @model_validator(mode="after")
    def validate_unique_enabled_requirements(self) -> SubmissionRequirementSet:
        material_types = [item.material_type for item in self.items]
        if len(material_types) != len(set(material_types)):
            raise ValueError("submission material requirements must be unique")
        if not any(item.enabled and item.required for item in self.items):
            raise ValueError("at least one required submission material must be enabled")
        if any(item.required and not item.enabled for item in self.items):
            raise ValueError("disabled submission materials cannot be required")
        return self


def normalize_submission_requirements(
    requirements: tuple[SubmissionRequirement, ...] | list[SubmissionRequirement],
) -> tuple[SubmissionRequirement, ...]:
    return SubmissionRequirementSet(items=tuple(requirements)).items


def submission_requirements_from_json(
    payload: list[dict[str, object]] | None,
) -> tuple[SubmissionRequirement, ...]:
    if payload is None:
        return DEFAULT_SUBMISSION_REQUIREMENTS
    return normalize_submission_requirements(
        [SubmissionRequirement.model_validate(item) for item in payload]
    )


def submission_requirements_to_json(
    requirements: tuple[SubmissionRequirement, ...],
) -> list[dict[str, object]]:
    return [
        requirement.model_dump(mode="json")
        for requirement in normalize_submission_requirements(requirements)
    ]
