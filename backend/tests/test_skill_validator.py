"""Tests for SkillValidator -- procedure_json validation."""
import pytest

from skills.validator import SkillValidator


@pytest.fixture
def validator() -> SkillValidator:
    return SkillValidator()


@pytest.fixture
def valid_procedure() -> dict:
    """Minimal valid procedure_json."""
    return {
        "schema_version": "1.0",
        "steps": [
            {
                "id": "fetch",
                "type": "tool",
                "tool": "email.fetch",
                "description": "Fetch emails",
            },
            {
                "id": "summarize",
                "type": "llm",
                "model_alias": "blitz/fast",
                "prompt_template": "Summarize: {{fetch.output}}",
                "description": "Summarize results",
            },
        ],
        "output": "{{summarize.output}}",
    }


class TestValidProcedure:
    def test_valid_procedure_passes(
        self, validator: SkillValidator, valid_procedure: dict
    ) -> None:
        errors = validator.validate_procedure(valid_procedure)
        assert errors == []

    def test_valid_with_condition(self, validator: SkillValidator) -> None:
        procedure = {
            "schema_version": "1.0",
            "steps": [
                {
                    "id": "check",
                    "type": "tool",
                    "tool": "status.check",
                },
                {
                    "id": "decide",
                    "type": "condition",
                    "expression": "len(x) > 0",
                    "true_step": "notify",
                },
                {
                    "id": "notify",
                    "type": "tool",
                    "tool": "email.send",
                },
            ],
        }
        errors = validator.validate_procedure(procedure)
        assert errors == []


class TestSchemaVersion:
    def test_missing_schema_version(self, validator: SkillValidator) -> None:
        procedure = {"steps": [{"id": "s1", "type": "tool", "tool": "t"}]}
        errors = validator.validate_procedure(procedure)
        assert any("schema_version is required" in e for e in errors)

    def test_wrong_schema_version(self, validator: SkillValidator) -> None:
        procedure = {
            "schema_version": "2.0",
            "steps": [{"id": "s1", "type": "tool", "tool": "t"}],
        }
        errors = validator.validate_procedure(procedure)
        assert any("schema_version must be '1.0'" in e for e in errors)


class TestStepBasics:
    def test_missing_steps(self, validator: SkillValidator) -> None:
        procedure = {"schema_version": "1.0"}
        errors = validator.validate_procedure(procedure)
        assert any("steps is required" in e for e in errors)

    def test_empty_steps(self, validator: SkillValidator) -> None:
        procedure = {"schema_version": "1.0", "steps": []}
        errors = validator.validate_procedure(procedure)
        assert any("steps must not be empty" in e for e in errors)

    def test_too_many_steps(self, validator: SkillValidator) -> None:
        steps = [
            {"id": f"s{i}", "type": "tool", "tool": f"t{i}"}
            for i in range(21)
        ]
        procedure = {"schema_version": "1.0", "steps": steps}
        errors = validator.validate_procedure(procedure)
        assert any("exceeds maximum" in e for e in errors)

    def test_unknown_step_type(self, validator: SkillValidator) -> None:
        procedure = {
            "schema_version": "1.0",
            "steps": [{"id": "s1", "type": "webhook"}],
        }
        errors = validator.validate_procedure(procedure)
        assert any("invalid type 'webhook'" in e for e in errors)

    def test_duplicate_step_ids(self, validator: SkillValidator) -> None:
        procedure = {
            "schema_version": "1.0",
            "steps": [
                {"id": "s1", "type": "tool", "tool": "t1"},
                {"id": "s1", "type": "tool", "tool": "t2"},
            ],
        }
        errors = validator.validate_procedure(procedure)
        assert any("duplicate id 's1'" in e for e in errors)

    def test_missing_step_id(self, validator: SkillValidator) -> None:
        procedure = {
            "schema_version": "1.0",
            "steps": [{"type": "tool", "tool": "t1"}],
        }
        errors = validator.validate_procedure(procedure)
        assert any("missing 'id'" in e for e in errors)


class TestToolSteps:
    def test_tool_step_missing_tool(self, validator: SkillValidator) -> None:
        procedure = {
            "schema_version": "1.0",
            "steps": [{"id": "s1", "type": "tool"}],
        }
        errors = validator.validate_procedure(procedure)
        assert any("requires 'tool' field" in e for e in errors)


class TestLlmSteps:
    def test_llm_step_missing_model_alias(
        self, validator: SkillValidator
    ) -> None:
        procedure = {
            "schema_version": "1.0",
            "steps": [
                {
                    "id": "s1",
                    "type": "llm",
                    "prompt_template": "Hello",
                },
            ],
        }
        errors = validator.validate_procedure(procedure)
        assert any("requires 'model_alias'" in e for e in errors)

    def test_llm_step_missing_prompt(self, validator: SkillValidator) -> None:
        procedure = {
            "schema_version": "1.0",
            "steps": [
                {
                    "id": "s1",
                    "type": "llm",
                    "model_alias": "blitz/fast",
                },
            ],
        }
        errors = validator.validate_procedure(procedure)
        assert any("requires 'prompt_template'" in e for e in errors)

    def test_llm_step_prompt_too_large(
        self, validator: SkillValidator
    ) -> None:
        procedure = {
            "schema_version": "1.0",
            "steps": [
                {
                    "id": "s1",
                    "type": "llm",
                    "model_alias": "blitz/fast",
                    "prompt_template": "x" * 11000,
                },
            ],
        }
        errors = validator.validate_procedure(procedure)
        assert any("exceeds" in e for e in errors)


class TestConditionSteps:
    def test_condition_missing_expression(
        self, validator: SkillValidator
    ) -> None:
        procedure = {
            "schema_version": "1.0",
            "steps": [
                {
                    "id": "s1",
                    "type": "condition",
                    "true_step": "s2",
                },
                {"id": "s2", "type": "tool", "tool": "t"},
            ],
        }
        errors = validator.validate_procedure(procedure)
        assert any("requires 'expression'" in e for e in errors)

    def test_condition_missing_true_step(
        self, validator: SkillValidator
    ) -> None:
        procedure = {
            "schema_version": "1.0",
            "steps": [
                {
                    "id": "s1",
                    "type": "condition",
                    "expression": "x > 5",
                },
            ],
        }
        errors = validator.validate_procedure(procedure)
        assert any("requires 'true_step'" in e for e in errors)

    def test_condition_unsafe_expression(
        self, validator: SkillValidator
    ) -> None:
        procedure = {
            "schema_version": "1.0",
            "steps": [
                {
                    "id": "s1",
                    "type": "condition",
                    "expression": "__import__('os').system('rm -rf /')",
                    "true_step": "s2",
                },
                {"id": "s2", "type": "tool", "tool": "t"},
            ],
        }
        errors = validator.validate_procedure(procedure)
        assert any("unsafe condition expression" in e for e in errors)


class TestVariableReferences:
    def test_var_ref_to_nonexistent_step(
        self, validator: SkillValidator
    ) -> None:
        procedure = {
            "schema_version": "1.0",
            "steps": [
                {
                    "id": "s1",
                    "type": "llm",
                    "model_alias": "blitz/fast",
                    "prompt_template": "Use {{nonexistent.output}}",
                },
            ],
        }
        errors = validator.validate_procedure(procedure)
        assert any("unknown prior step 'nonexistent'" in e for e in errors)

    def test_var_ref_to_later_step_fails(
        self, validator: SkillValidator
    ) -> None:
        procedure = {
            "schema_version": "1.0",
            "steps": [
                {
                    "id": "first",
                    "type": "llm",
                    "model_alias": "blitz/fast",
                    "prompt_template": "Use {{second.output}}",
                },
                {
                    "id": "second",
                    "type": "tool",
                    "tool": "t",
                },
            ],
        }
        errors = validator.validate_procedure(procedure)
        assert any("unknown prior step 'second'" in e for e in errors)

    def test_output_template_unknown_ref(
        self, validator: SkillValidator
    ) -> None:
        procedure = {
            "schema_version": "1.0",
            "steps": [{"id": "s1", "type": "tool", "tool": "t"}],
            "output": "Result: {{ghost.output}}",
        }
        errors = validator.validate_procedure(procedure)
        assert any("output template references unknown step 'ghost'" in e for e in errors)


class TestConditionRouting:
    def test_condition_true_step_unknown(
        self, validator: SkillValidator
    ) -> None:
        procedure = {
            "schema_version": "1.0",
            "steps": [
                {
                    "id": "cond",
                    "type": "condition",
                    "expression": "x > 5",
                    "true_step": "nonexistent",
                },
            ],
        }
        errors = validator.validate_procedure(procedure)
        assert any("true_step 'nonexistent' references unknown step" in e for e in errors)

    def test_condition_backward_jump_rejected(
        self, validator: SkillValidator
    ) -> None:
        procedure = {
            "schema_version": "1.0",
            "steps": [
                {"id": "start", "type": "tool", "tool": "t"},
                {
                    "id": "cond",
                    "type": "condition",
                    "expression": "x > 5",
                    "true_step": "start",
                },
            ],
        }
        errors = validator.validate_procedure(procedure)
        assert any("backward jump" in e for e in errors)
