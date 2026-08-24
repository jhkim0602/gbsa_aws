from interview_evidence.submission_analysis.domain.git_analysis import (
    CommitIdentityInput,
    GitCommitCandidate,
    OwnershipClass,
    classify_commit_ownership,
)
from interview_evidence.workers.analysis.code_units import expand_python_code_units


def test_commit_identity_is_a_candidate_signal_not_proof() -> None:
    commit = GitCommitCandidate(
        parent_sha="a" * 40,
        commit_sha="b" * 40,
        author_name="홍길동",
        author_email="candidate@example.com",
        changed_paths=("src/payment.py", "tests/test_payment.py"),
    )
    result = classify_commit_ownership(
        commit,
        CommitIdentityInput(
            claimed_names=("홍길동",),
            claimed_emails=("candidate@example.com",),
            claimed_handles=("candidate-dev",),
        ),
    )

    assert result.ownership_class is OwnershipClass.PRIMARY_OWNED
    assert 0.5 < result.confidence < 1
    assert result.requires_verification is True


def test_low_confidence_commit_is_context_only_and_generates_verification_need() -> None:
    commit = GitCommitCandidate(
        parent_sha="a" * 40,
        commit_sha="c" * 40,
        author_name="다른 사람",
        author_email="other@example.com",
        changed_paths=("src/payment.py",),
    )
    result = classify_commit_ownership(
        commit,
        CommitIdentityInput(claimed_handles=("candidate-dev",)),
    )

    assert result.ownership_class is OwnershipClass.CONTEXT_ONLY
    assert result.requires_verification is True
    assert "본인이 작성한 범위" in result.verification_prompt


def test_exact_github_login_is_strong_ownership_evidence() -> None:
    commit = GitCommitCandidate(
        parent_sha="a" * 40,
        commit_sha="d" * 40,
        author_name="Applicant",
        author_email="private@example.com",
        author_login="candidate-dev",
        changed_paths=("src/payment.py",),
    )

    result = classify_commit_ownership(
        commit,
        CommitIdentityInput(claimed_handles=("candidate-dev",)),
    )

    assert result.ownership_class is OwnershipClass.PRIMARY_OWNED
    assert result.confidence >= 0.7
    assert "github_login_match" in result.explanation_codes


def test_python_ast_expands_changed_lines_to_symbol_and_related_test() -> None:
    source = """
def calculate_total(items):
    return sum(item.price for item in items)

def unused():
    return 0
""".strip()
    tests = """
from payment import calculate_total

def test_calculate_total():
    assert calculate_total([]) == 0
""".strip()

    units = expand_python_code_units(
        path="src/payment.py",
        source=source,
        changed_line_ranges=((1, 2),),
        related_files={"tests/test_payment.py": tests},
    )

    assert len(units) == 1
    assert units[0].symbol == "calculate_total"
    assert units[0].candidate_owned_regions == ((1, 2),)
    assert units[0].related_test_paths == ("tests/test_payment.py",)
