from lab.chain import Chain
from lab.seeds import derive_seed


def test_chain_roundtrip(tmp_path):
    c = Chain(tmp_path / "journal.jsonl")
    c.append({"a": 1})
    c.append({"b": 2})
    assert c.verify() == []


def test_chain_detects_payload_edit(tmp_path):
    c = Chain(tmp_path / "journal.jsonl")
    c.append({"a": 1})
    c.append({"b": 2})
    raw = (tmp_path / "journal.jsonl").read_text().replace('"b": 2', '"b": 3')
    (tmp_path / "journal.jsonl").write_text(raw)
    assert c.verify() != []


def test_chain_detects_middle_deletion(tmp_path):
    c = Chain(tmp_path / "journal.jsonl")
    c.append({"a": 1})
    c.append({"b": 2})
    c.append({"c": 3})
    lines = (tmp_path / "journal.jsonl").read_text().splitlines()
    del lines[1]
    (tmp_path / "journal.jsonl").write_text("\n".join(lines) + "\n")
    assert c.verify() != []


def test_chain_tail_truncation_undetectable_by_design(tmp_path):
    """Обрезка хвоста не обнаружима (crash-safe: журнал цел до последней записи)."""
    c = Chain(tmp_path / "journal.jsonl")
    c.append({"a": 1})
    c.append({"b": 2})
    lines = (tmp_path / "journal.jsonl").read_text().splitlines()
    (tmp_path / "journal.jsonl").write_text(lines[0] + "\n")
    assert Chain(tmp_path / "journal.jsonl").verify() == []


def test_seeds_deterministic_and_distinct():
    assert derive_seed(7, "g0", 1) == derive_seed(7, "g0", 1)
    assert derive_seed(7, "g0", 1) != derive_seed(7, "g0", 2)
    assert derive_seed(7, "g0", 1) != derive_seed(8, "g0", 1)
