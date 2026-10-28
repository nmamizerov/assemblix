import pytest

from assemblix_api.schemas.node import JevNodeConfig


def _noul(name: str = "q") -> dict:
    return {"name": name, "type": "noul", "instructions": "Is it?"}


def _choice(n_options: int, name: str = "c") -> dict:
    return {
        "name": name,
        "type": "choice",
        "options": [{"name": f"o{i}", "description": ""} for i in range(n_options)],
    }


def _score(n_levels: int, name: str = "s") -> dict:
    return {"name": name, "type": "score", "levels": [f"l{i}" for i in range(n_levels)]}


def _config(
    questions: list[dict], credential_id: str | None = "00000000-0000-0000-0000-000000000001"
) -> JevNodeConfig:
    return JevNodeConfig(**{"credentialId": credential_id, "questions": questions})


def test_parses_camel_case() -> None:
    # Arrange
    raw = {
        "credentialId": "x",
        "longContext": True,
        "outputKey": "j",
        "questions": [{"name": "a", "type": "noul", "trueCriteria": "t"}],
    }
    # Act
    cfg = JevNodeConfig(**raw)
    # Assert
    assert cfg.credential_id == "x"
    assert cfg.long_context is True
    assert cfg.output_key == "j"
    assert cfg.questions[0].true_criteria == "t"


def test_defaults() -> None:
    # Arrange / Act
    cfg = JevNodeConfig()
    # Assert
    assert cfg.model == "jev-latest"
    assert cfg.state == "{{ input.message }}"
    assert cfg.output_key == "jev"
    assert cfg.long_context is False


@pytest.mark.parametrize(
    ("cfg", "expected"),
    [
        (_config([_noul()], credential_id=None), "credential"),
        (_config([_noul()], credential_id="<placeholder>"), "credential"),
        (_config([]), "question"),
        (_config([_noul("a"), _noul("a")]), "unique"),
        (_config([_noul("1bad")]), "name"),
        (_config([_choice(0)]), "option"),
        (_config([_choice(256)]), "255"),
        (
            _config(
                [
                    {
                        "name": "c",
                        "type": "choice",
                        "options": [{"name": "x"}, {"name": "x"}],
                    }
                ]
            ),
            "unique",
        ),
        (_config([_score(1)]), "2"),
        (_config([_score(11)]), "10"),
    ],
)
def test_validation_errors(cfg: JevNodeConfig, expected: str) -> None:
    # Act
    errors = cfg.validation_errors()
    # Assert
    assert any(expected in e for e in errors), errors


def test_valid_config_has_no_errors() -> None:
    # Arrange
    cfg = _config([_noul(), _choice(2), _score(3)])
    # Act / Assert
    assert cfg.validation_errors() == []
