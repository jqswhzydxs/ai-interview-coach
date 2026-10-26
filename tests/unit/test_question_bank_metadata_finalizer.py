from copy import deepcopy

import pytest

from app.services.question_bank_metadata_finalizer import (
    EXPECTED_TOTAL_SCORES,
    MetadataReviewValidationError,
    REVIEW_VERSION,
    validate_completed_review,
)


FIELDS = ("purpose", "source", "framework", "anchors", "follow_up", "advice")


def review_documents():
    submissions = [
        {
            "submission_id": f"metadata-{index:02d}",
            "metadata_fit_scores": [None] * 25,
            "field_notes": {field: "" for field in FIELDS},
        }
        for index in range(38)
    ]
    template = {
        "review_version": REVIEW_VERSION,
        "scale": "1-5",
        "evaluator": {
            "type": None,
            "identifier": None,
            "independence_confirmed": None,
        },
        "instructions": "synthetic",
        "submissions": submissions,
    }
    completed = deepcopy(template)
    completed["evaluator"] = {
        "type": "ai",
        "identifier": "synthetic-independent-reviewer",
        "independence_confirmed": True,
    }
    for submission in completed["submissions"]:
        submission["metadata_fit_scores"] = [4] * 25
    return template, completed


def test_completed_review_accepts_exactly_38_submissions_and_950_scores():
    template, completed = review_documents()

    validated = validate_completed_review(template, completed)

    assert validated["submission_count"] == 38
    assert validated["score_count"] == EXPECTED_TOTAL_SCORES == 950
    assert validated["evaluator"] == {
        "type": "ai",
        "identifier": "synthetic-independent-reviewer",
        "independence_confirmed": True,
    }


def test_completed_review_rejects_missing_and_extra_submissions():
    template, completed = review_documents()
    missing = deepcopy(completed)
    missing["submissions"].pop()
    with pytest.raises(MetadataReviewValidationError, match="exactly 38"):
        validate_completed_review(template, missing)

    extra = deepcopy(completed)
    extra["submissions"].append(deepcopy(extra["submissions"][0]))
    with pytest.raises(MetadataReviewValidationError, match="exactly 38"):
        validate_completed_review(template, extra)


def test_completed_review_rejects_id_or_order_changes():
    template, completed = review_documents()
    changed_id = deepcopy(completed)
    changed_id["submissions"][0]["submission_id"] = "unexpected"
    with pytest.raises(MetadataReviewValidationError, match="IDs do not exactly match"):
        validate_completed_review(template, changed_id)

    reordered = deepcopy(completed)
    reordered["submissions"][0], reordered["submissions"][1] = (
        reordered["submissions"][1],
        reordered["submissions"][0],
    )
    with pytest.raises(MetadataReviewValidationError, match="order differs"):
        validate_completed_review(template, reordered)


@pytest.mark.parametrize("invalid_score", [None, 0, 6, 3.5, True])
def test_completed_review_rejects_null_out_of_range_or_non_integer_scores(
    invalid_score,
):
    template, completed = review_documents()
    completed["submissions"][0]["metadata_fit_scores"][0] = invalid_score

    with pytest.raises(MetadataReviewValidationError, match="integer from 1 to 5"):
        validate_completed_review(template, completed)


@pytest.mark.parametrize(
    "evaluator",
    [
        {"type": None, "identifier": "reviewer", "independence_confirmed": True},
        {"type": "ai", "identifier": "", "independence_confirmed": True},
        {"type": "ai", "identifier": "reviewer", "independence_confirmed": None},
        {"type": "ai", "identifier": "reviewer", "independence_confirmed": False},
    ],
)
def test_completed_review_rejects_incomplete_evaluator_identity(evaluator):
    template, completed = review_documents()
    completed["evaluator"] = evaluator

    with pytest.raises(MetadataReviewValidationError):
        validate_completed_review(template, completed)


def test_completed_review_rejects_wrong_review_version():
    template, completed = review_documents()
    completed["review_version"] = "unexpected"

    with pytest.raises(MetadataReviewValidationError, match="review_version"):
        validate_completed_review(template, completed)
