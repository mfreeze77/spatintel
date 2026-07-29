from __future__ import annotations

from pathlib import Path

from tools import run_test_matrix


def test_progress06_r1_parallel_shards_receive_unique_database_and_runtime_roots() -> None:
    """REQ: TSTLAY-003, TSTSTRAT-002 parallel test shards are hermetic and never race on the repository runtime database."""
    writer = "r1-hermetic-writer"
    root_a, env_a = run_test_matrix._shard_runtime_environment(
        environment={"PYTHONPATH": "src:."},
        writer_token=writer,
        shard_name="tests__security__one",
    )
    root_b, env_b = run_test_matrix._shard_runtime_environment(
        environment={"PYTHONPATH": "src:."},
        writer_token=writer,
        shard_name="tests__security__two",
    )

    assert root_a != root_b
    assert env_a["SIP_DATABASE_URL"] != env_b["SIP_DATABASE_URL"]
    assert env_a["SIP_OBJECT_STORE_ROOT"] != env_b["SIP_OBJECT_STORE_ROOT"]
    assert env_a["SIP_MULTIPART_ROOT"] != env_b["SIP_MULTIPART_ROOT"]
    assert "runtime/sip.sqlite3" not in env_a["SIP_DATABASE_URL"]
    assert "runtime/sip.sqlite3" not in env_b["SIP_DATABASE_URL"]
    assert Path(env_a["SIP_OBJECT_STORE_ROOT"]).is_relative_to(root_a)
    assert Path(env_b["SIP_OBJECT_STORE_ROOT"]).is_relative_to(root_b)
