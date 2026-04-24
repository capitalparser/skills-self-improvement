from __future__ import annotations

from skill_evolution.config import load_config


def test_defaults_load_without_config_file(tmp_path):
    config = load_config(tmp_path)
    assert config.raw["evolution"]["auto"] == "light"
    assert config.raw["constraints"]["max_skill_lines"] == 500
    assert config.skills_dir == tmp_path / "skills"
    assert config.traces_dir == tmp_path / ".skill-evolution" / "traces"


def test_yaml_overrides_deep_merge(tmp_path):
    (tmp_path / ".skill-evolution").mkdir()
    (tmp_path / ".skill-evolution" / "config.yaml").write_text(
        "evolution:\n  auto: heavy\nconstraints:\n  max_skill_lines: 300\n"
    )
    config = load_config(tmp_path)
    assert config.raw["evolution"]["auto"] == "heavy"
    assert config.raw["evolution"]["min_traces_before_evolve"] == 5  # default preserved
    assert config.raw["constraints"]["max_skill_lines"] == 300
