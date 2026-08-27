from interview_evidence.workers.analysis.git_fetch import RepositoryFile, RepositorySnapshot
from interview_evidence.workers.analysis.repository_overview import (
    build_repository_overview_documents,
)


def test_repository_overview_contains_structure_and_head_documents() -> None:
    snapshot = RepositorySnapshot(
        repository_url="https://github.com/example/project",
        default_branch="main",
        pinned_head_sha="a" * 40,
        files=(
            RepositoryFile(path="README.md", content=b"# Project\nAPI and worker\n"),
            RepositoryFile(
                path="src/changed.py",
                content=b"def changed(): pass\n",
                commit_sha="b" * 40,
            ),
        ),
        commit_count=1,
        tree_paths=("README.md", "src/api/main.py", "src/worker/jobs.py"),
    )

    documents = build_repository_overview_documents(snapshot)

    assert [document.section for document in documents] == [
        "repository_structure",
        "readme",
    ]
    assert "src: 2개 파일" in documents[0].text
    assert "src/api/main.py" in documents[0].text
    assert "API and worker" in documents[1].text
