"""Tests for the Dataset Generator with Result Alignment module."""

import json
import pytest
import pandas as pd
import numpy as np

from src.generators.dataset_generator import (
    ScriptResultExtractor,
    DatasetGenerator,
    DatasetValidator,
    DatasetAuditor,
    CodeBlock,
    ExpectedResult,
    ValidationResult,
    DatasetAudit,
)


# ---------------------------------------------------------------------------
# Sample scripts
# ---------------------------------------------------------------------------

SCRIPT_WITH_CODE = """## CONTENT

Let's calculate basic statistics on our customer data.

```python
import pandas as pd
df = pd.read_csv('customers.csv')
mean_revenue = df['revenue'].mean()
total_customers = len(df)
```

The mean revenue is **42.5** and we have a total of `total_customers = 100` customers.

Now let's check the churn rate:

```python
churn_rate = df['churned'].mean()
```

The churn rate should be **0.25**.
"""

SCRIPT_NO_CODE = """## HOOK
Welcome to this video about data science.

## OBJECTIVE
You'll learn about pandas.

## SUMMARY
We covered pandas basics.
"""

SCRIPT_MULTIPLE_FILES = """## CONTENT

```python
import pandas as pd
sales = pd.read_csv('sales.csv')
users = pd.read_excel('users.xlsx')
result = sales.merge(users, on='user_id')
```

The merged dataset has **500** rows.
"""


# ---------------------------------------------------------------------------
# Tests: ScriptResultExtractor
# ---------------------------------------------------------------------------

class TestScriptResultExtractor:
    def test_extract_code_blocks_basic(self):
        """Should find Python code blocks."""
        extractor = ScriptResultExtractor()
        blocks = extractor.extract_code_blocks(SCRIPT_WITH_CODE)

        assert len(blocks) == 2
        assert blocks[0].language == 'python'
        assert 'read_csv' in blocks[0].code
        assert blocks[0].section == 'CONTENT'

    def test_extract_code_blocks_empty_script(self):
        """Empty script should return no blocks."""
        extractor = ScriptResultExtractor()
        assert extractor.extract_code_blocks("") == []
        assert extractor.extract_code_blocks(None) == []

    def test_extract_no_code_script(self):
        """Script without code blocks should return empty list."""
        extractor = ScriptResultExtractor()
        blocks = extractor.extract_code_blocks(SCRIPT_NO_CODE)
        assert len(blocks) == 0

    def test_detect_data_loading(self):
        """Should detect read_csv as requiring data."""
        extractor = ScriptResultExtractor()
        blocks = extractor.extract_code_blocks(SCRIPT_WITH_CODE)

        assert blocks[0].requires_data is True
        assert blocks[1].requires_data is False  # No read_csv

    def test_find_input_datasets(self):
        """Should extract input filenames from code."""
        extractor = ScriptResultExtractor()
        blocks = extractor.extract_code_blocks(SCRIPT_WITH_CODE)

        assert 'customers.csv' in blocks[0].input_datasets

    def test_find_multiple_input_files(self):
        """Should find multiple input files."""
        extractor = ScriptResultExtractor()
        blocks = extractor.extract_code_blocks(SCRIPT_MULTIPLE_FILES)

        assert 'sales.csv' in blocks[0].input_datasets
        assert 'users.xlsx' in blocks[0].input_datasets

    def test_extract_expected_results_bold(self):
        """Should parse **42.5** as expected value."""
        extractor = ScriptResultExtractor()
        blocks = extractor.extract_code_blocks(SCRIPT_WITH_CODE)

        # First block: mean_revenue = 42.5
        results = blocks[0].expected_results
        var_names = {r.variable_name for r in results}
        assert 'mean_revenue' in var_names or 'revenue' in var_names

    def test_extract_expected_results_inline_code(self):
        """Should parse `total_customers = 100`."""
        extractor = ScriptResultExtractor()
        blocks = extractor.extract_code_blocks(SCRIPT_WITH_CODE)

        # Check across all blocks for total_customers
        all_results = []
        for b in blocks:
            all_results.extend(b.expected_results)
        var_names = {r.variable_name for r in all_results}
        assert 'total_customers' in var_names

    def test_extract_expected_results_second_block(self):
        """Should find churn_rate = 0.25 for second code block."""
        extractor = ScriptResultExtractor()
        blocks = extractor.extract_code_blocks(SCRIPT_WITH_CODE)

        results = blocks[1].expected_results
        var_names = {r.variable_name for r in results}
        assert 'churn_rate' in var_names

        churn = next(r for r in results if r.variable_name == 'churn_rate')
        assert churn.expected_value == 0.25

    def test_code_block_to_dict(self):
        """CodeBlock.to_dict() should be serializable."""
        extractor = ScriptResultExtractor()
        blocks = extractor.extract_code_blocks(SCRIPT_WITH_CODE)
        d = blocks[0].to_dict()

        assert isinstance(d['id'], str)
        assert isinstance(d['code'], str)
        assert isinstance(d['expected_results'], list)
        json.dumps(d)  # Should not raise

    def test_section_detection(self):
        """Should detect correct WWHAA section."""
        extractor = ScriptResultExtractor()
        blocks = extractor.extract_code_blocks(SCRIPT_WITH_CODE)

        for block in blocks:
            assert block.section == 'CONTENT'


# ---------------------------------------------------------------------------
# Tests: DatasetValidator
# ---------------------------------------------------------------------------

class TestDatasetValidator:
    def test_validate_matching_results(self):
        """Should pass when actual matches expected."""
        df = pd.DataFrame({
            'revenue': [40.0, 42.0, 45.5],
        })
        # mean = 42.5

        code_block = CodeBlock(
            id="c0", code="mean_revenue = df['revenue'].mean()",
            language='python', section='CONTENT', requires_data=True,
            expected_results=[
                ExpectedResult("c0", "mean_revenue", 42.5, tolerance=0.01)
            ],
        )

        validator = DatasetValidator()
        result = validator.validate(code_block, {'df': df})

        assert result.passed is True
        assert abs(result.actual_results.get('mean_revenue', 0) - 42.5) < 0.1

    def test_validate_mismatch(self):
        """Should fail when actual doesn't match expected."""
        df = pd.DataFrame({
            'revenue': [10.0, 20.0, 30.0],
        })
        # mean = 20.0, not 42.5

        code_block = CodeBlock(
            id="c0", code="mean_revenue = df['revenue'].mean()",
            language='python', section='CONTENT', requires_data=True,
            expected_results=[
                ExpectedResult("c0", "mean_revenue", 42.5, tolerance=0.01)
            ],
        )

        validator = DatasetValidator()
        result = validator.validate(code_block, {'df': df})

        assert result.passed is False
        assert len(result.errors) > 0

    def test_validate_missing_variable(self):
        """Should report error when expected variable not found."""
        df = pd.DataFrame({'a': [1, 2, 3]})

        code_block = CodeBlock(
            id="c0", code="x = df['a'].sum()",
            language='python', section='CONTENT', requires_data=True,
            expected_results=[
                ExpectedResult("c0", "nonexistent_var", 6.0, tolerance=0.01)
            ],
        )

        validator = DatasetValidator()
        result = validator.validate(code_block, {'df': df})

        assert result.passed is False
        assert any('not found' in e for e in result.errors)

    def test_validate_syntax_error_in_code(self):
        """Should handle code with syntax errors gracefully."""
        df = pd.DataFrame({'a': [1, 2, 3]})

        code_block = CodeBlock(
            id="c0", code="x = df['a'.mean()",  # syntax error
            language='python', section='CONTENT', requires_data=True,
            expected_results=[
                ExpectedResult("c0", "x", 2.0)
            ],
        )

        validator = DatasetValidator()
        result = validator.validate(code_block, {'df': df})

        assert result.passed is False
        assert len(result.errors) > 0

    def test_validate_to_dict(self):
        """ValidationResult.to_dict() should be serializable."""
        result = ValidationResult(
            code_block_id="c0",
            passed=True,
            actual_results={'mean': 42.5},
            expected_results={'mean': 42.5},
            errors=[],
        )
        d = result.to_dict()
        json.dumps(d)

    def test_values_match_within_tolerance(self):
        """Should match values within tolerance."""
        validator = DatasetValidator()
        assert validator._values_match(0.923, 0.92, 0.01) is True
        assert validator._values_match(0.90, 0.92, 0.01) is False

    def test_values_match_zero_expected(self):
        """Should handle zero expected value."""
        validator = DatasetValidator()
        assert validator._values_match(0.0, 0.0, 0.01) is True
        assert validator._values_match(0.005, 0.0, 0.01) is True
        assert validator._values_match(0.1, 0.0, 0.01) is False


# ---------------------------------------------------------------------------
# Tests: DatasetAuditor
# ---------------------------------------------------------------------------

class TestDatasetAuditor:
    def test_audit_clean_data(self):
        """Clean data should get score 100."""
        df = pd.DataFrame({
            'id': [1, 2, 3, 4, 5],
            'value': [10.0, 20.0, 30.0, 40.0, 50.0],
        })

        auditor = DatasetAuditor()
        audit = auditor.audit(df, 'test_clean')

        assert audit.quality_score == 100.0
        assert audit.row_count == 5
        assert audit.column_count == 2
        assert len(audit.issues) == 0

    def test_audit_missing_values(self):
        """Should detect missing values."""
        df = pd.DataFrame({
            'id': [1, 2, None, 4, 5],
            'value': [10.0, None, 30.0, 40.0, 50.0],
        })

        auditor = DatasetAuditor()
        audit = auditor.audit(df, 'test_nulls')

        assert audit.quality_score < 100
        assert any(i['type'] == 'missing_values' for i in audit.issues)
        null_issue = next(i for i in audit.issues if i['type'] == 'missing_values')
        assert null_issue['count'] == 2

    def test_audit_duplicates(self):
        """Should detect duplicate rows."""
        df = pd.DataFrame({
            'id': [1, 1, 2, 3, 4],
            'value': [10, 10, 20, 30, 40],
        })

        auditor = DatasetAuditor()
        audit = auditor.audit(df, 'test_dups')

        assert any(i['type'] == 'duplicates' for i in audit.issues)

    def test_audit_constant_column(self):
        """Should detect columns with single unique value."""
        df = pd.DataFrame({
            'id': [1, 2, 3, 4, 5],
            'const': ['A', 'A', 'A', 'A', 'A'],
        })

        auditor = DatasetAuditor()
        audit = auditor.audit(df, 'test_const')

        assert any(i['type'] == 'constant_column' for i in audit.issues)

    def test_audit_to_dict(self):
        """DatasetAudit.to_dict() should be serializable."""
        df = pd.DataFrame({'a': [1, 2, 3]})
        auditor = DatasetAuditor()
        audit = auditor.audit(df, 'test')
        d = audit.to_dict()
        json.dumps(d)

    def test_audit_score_penalties(self):
        """Score should decrease with more issues."""
        # Data with multiple problems
        df = pd.DataFrame({
            'id': [1, 1, None, 4, 5],
            'const': ['A', 'A', 'A', 'A', 'A'],
            'value': [None, 20, 30, 40, 50],
        })

        auditor = DatasetAuditor()
        audit = auditor.audit(df, 'test_multi')

        # Should have missing values + duplicates + constant column
        assert audit.quality_score < 100
        assert len(audit.issues) >= 2
