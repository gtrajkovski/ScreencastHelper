"""Dataset generator with result alignment for screencast scripts.

Extracts code blocks and expected outputs from WWHAA scripts, generates
datasets that produce those exact results, validates by executing code,
and audits data quality.
"""

import json
import re
import subprocess
import tempfile
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import pandas as pd
    import numpy as np
except ImportError:
    pd = None
    np = None


# ============================================================================
# Data models
# ============================================================================

@dataclass
class ExpectedResult:
    """An expected output value from running a code block."""
    code_block_id: str
    variable_name: str
    expected_value: Any  # numeric, string, etc.
    value_type: str = "float"  # "float", "int", "string"
    tolerance: float = 0.01  # for float comparisons (1%)
    context: str = ""  # surrounding text from script

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CodeBlock:
    """A code block extracted from a script."""
    id: str
    code: str
    language: str
    section: str  # HOOK, CONTENT, etc.
    requires_data: bool  # does it load a CSV/file?
    expected_results: List[ExpectedResult] = field(default_factory=list)
    input_datasets: List[str] = field(default_factory=list)
    line_start: int = 0
    line_end: int = 0

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'code': self.code,
            'language': self.language,
            'section': self.section,
            'requires_data': self.requires_data,
            'expected_results': [r.to_dict() for r in self.expected_results],
            'input_datasets': self.input_datasets,
            'line_start': self.line_start,
            'line_end': self.line_end,
        }


@dataclass
class ValidationResult:
    """Result of running code against a dataset."""
    code_block_id: str
    passed: bool
    actual_results: Dict[str, Any]
    expected_results: Dict[str, Any]
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'code_block_id': self.code_block_id,
            'passed': self.passed,
            'actual_results': {k: _serialize(v) for k, v in self.actual_results.items()},
            'expected_results': {k: _serialize(v) for k, v in self.expected_results.items()},
            'errors': self.errors,
        }


@dataclass
class DatasetAudit:
    """Quality audit results for a dataset."""
    dataset_name: str
    row_count: int
    column_count: int
    issues: List[Dict[str, Any]] = field(default_factory=list)
    quality_score: float = 100.0

    def to_dict(self) -> dict:
        return asdict(self)


class DatasetStatus(Enum):
    """Status of a generated dataset."""
    PENDING = "pending"
    GENERATING = "generating"
    VALIDATING = "validating"
    MISMATCH = "mismatch"
    ALIGNED = "aligned"
    FINALIZED = "finalized"


class ResultMatchStatus(Enum):
    """Result of comparing expected vs actual values."""
    MATCH = "match"
    CLOSE = "close"
    MISMATCH = "mismatch"


@dataclass
class DatasetSpec:
    """Specification for a dataset to generate."""
    name: str
    description: str = ""
    columns: List[Dict[str, Any]] = field(default_factory=list)
    row_count: int = 100
    target_column: Optional[str] = None
    feature_columns: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)


@dataclass
class GeneratedDataset:
    """A generated dataset with validation results."""
    spec: DatasetSpec
    data: Any  # pd.DataFrame
    file_path: Optional[Path] = None
    status: DatasetStatus = DatasetStatus.PENDING
    validation_results: List[Dict[str, Any]] = field(default_factory=list)
    generation_attempts: int = 0
    last_error: Optional[str] = None


def _serialize(v: Any) -> Any:
    """Make a value JSON-serializable."""
    if isinstance(v, float):
        if v != v:  # NaN
            return None
        return round(v, 6)
    if hasattr(v, 'item'):  # numpy scalar
        return v.item()
    return v


# ============================================================================
# Script Result Extractor
# ============================================================================

# Patterns for data loading in code
DATA_LOAD_PATTERNS = [
    r'pd\.read_csv\s*\(["\']([^"\']+)["\']\)',
    r'pd\.read_excel\s*\(["\']([^"\']+)["\']\)',
    r'pd\.read_json\s*\(["\']([^"\']+)["\']\)',
    r'load_dataset\s*\(["\']([^"\']+)["\']\)',
]

# Patterns for expected outputs in narration
EXPECTED_OUTPUT_PATTERNS = [
    # Bold number: "churn rate should be **0.25**" (multi-word → underscore)
    (r'(\w+(?:\s+\w+)*)\s+(?:is|equals?|should\s+be|was|of)\s+\*\*([0-9.]+)\*\*', 'float'),
    # Inline code: `accuracy = 0.92`
    (r'`(\w+)\s*=\s*([0-9.]+)`', 'float'),
    # Quoted output: "Accuracy: 0.923"
    (r'["\'](\w+):\s*([\d.]+)["\']', 'float'),
    # OUTPUT block value: accuracy    0.923
    (r'(\w+)\s{2,}([\d.]+)', 'float'),
    # Print-like: accuracy = 0.92
    (r'(\w+)\s*=\s*([\d.]+)(?:\s|$)', 'float'),
]

# Variable names to skip (common false positives)
SKIP_VARS = {
    'line', 'step', 'cell', 'version', 'python', 'slide', 'section',
    'import', 'from', 'print', 'range', 'len', 'i', 'j', 'x', 'y',
    'fig', 'ax', 'plt', 'size', 'width', 'height', 'rows', 'columns',
    'shape', 'index', 'head', 'tail', 'iloc', 'loc', 'n',
}

# Known metric names (prioritized)
METRIC_NAMES = {
    'accuracy', 'auc', 'f1', 'precision', 'recall', 'r2', 'mse', 'mae',
    'rmse', 'roc_auc', 'f1_score', 'mean', 'median', 'std', 'variance',
    'correlation', 'silhouette', 'inertia', 'loss', 'error', 'score',
}


class ScriptResultExtractor:
    """Extract code blocks and expected results from scripts."""

    def extract_code_blocks(self, script: str) -> List[CodeBlock]:
        """Find all code blocks and their expected outputs."""
        if not script:
            return []

        blocks = []
        pattern = r'```(\w+)?\n(.*?)```'
        matches = list(re.finditer(pattern, script, re.DOTALL))

        for idx, match in enumerate(matches):
            language = match.group(1) or 'python'
            code = match.group(2).strip()
            block_id = f"code_{idx}"

            line_start = script[:match.start()].count('\n') + 1
            line_end = script[:match.end()].count('\n') + 1

            # Detect data loading
            requires_data = any(
                re.search(p, code) for p in DATA_LOAD_PATTERNS
            )
            input_datasets = self._find_input_files(code)

            # Find expected results in narration after code block
            expected = self._extract_expected_results(
                script, match.end(), block_id
            )

            blocks.append(CodeBlock(
                id=block_id,
                code=code,
                language=language,
                section=self._find_section(script, match.start()),
                requires_data=requires_data,
                expected_results=expected,
                input_datasets=input_datasets,
                line_start=line_start,
                line_end=line_end,
            ))

        return blocks

    def _find_input_files(self, code: str) -> List[str]:
        """Extract dataset filenames from code."""
        files = []
        for pattern in DATA_LOAD_PATTERNS:
            for match in re.finditer(pattern, code):
                files.append(match.group(1))
        return list(set(files))

    def _find_section(self, script: str, position: int) -> str:
        """Find which WWHAA section a position is in."""
        text_before = script[:position]
        sections = ['HOOK', 'OBJECTIVE', 'CONTENT', 'IVQ', 'SUMMARY', 'CTA', 'CALL TO ACTION']

        current = 'UNKNOWN'
        for section in sections:
            if re.search(rf'^#{{2,3}}\s+{section}', text_before, re.MULTILINE | re.IGNORECASE):
                current = section
                if current == 'CALL TO ACTION':
                    current = 'CTA'

        return current

    def _extract_expected_results(
        self, script: str, code_end: int, block_id: str
    ) -> List[ExpectedResult]:
        """Parse expected results from narration after a code block."""
        results = []
        seen_vars = set()

        # Look at next 600 chars after code block (but stop at next code block)
        remaining = script[code_end:]
        next_code = remaining.find('```')
        if next_code > 0:
            remaining = remaining[:next_code]
        chunk = remaining[:600]

        for pattern, vtype in EXPECTED_OUTPUT_PATTERNS:
            for match in re.finditer(pattern, chunk, re.IGNORECASE):
                var_name = match.group(1).lower().strip().replace(' ', '_')
                value_str = match.group(2)

                # Strip leading articles/determiners
                for prefix in ('the_', 'a_', 'an_', 'our_', 'its_', 'their_'):
                    if var_name.startswith(prefix):
                        var_name = var_name[len(prefix):]
                        break

                if var_name in SKIP_VARS or var_name in seen_vars:
                    continue

                try:
                    value = float(value_str)
                except ValueError:
                    continue

                # Prioritize known metric names
                if var_name not in METRIC_NAMES and not (0 <= value <= 1):
                    # Still allow if it looks like a metric
                    if var_name.endswith('_score') or var_name.startswith('mean_'):
                        pass
                    elif value > 10000:
                        continue  # Probably not a metric

                seen_vars.add(var_name)
                results.append(ExpectedResult(
                    code_block_id=block_id,
                    variable_name=var_name,
                    expected_value=value,
                    value_type=vtype,
                    tolerance=0.01,
                    context=match.group(0),
                ))

        return results

    def extract_from_script(self, script: str) -> Tuple[List[CodeBlock], List[ExpectedResult]]:
        """Extract code blocks and all expected results from a script.

        Convenience wrapper around extract_code_blocks() that also returns
        a flat list of all expected results across blocks.
        """
        blocks = self.extract_code_blocks(script)
        all_results = []
        for block in blocks:
            all_results.extend(block.expected_results)
        return blocks, all_results


# ============================================================================
# Dataset Generator
# ============================================================================

DATASET_GEN_SYSTEM = """You are a data scientist generating synthetic CSV datasets for educational screencasts.
Generate realistic data that produces EXACT expected results when the provided code runs.

Return ONLY valid CSV content. The first row must be column headers.
Do not include any explanation or markdown formatting — just raw CSV."""

DATASET_GEN_USER = """Generate a CSV dataset with {num_rows} rows for this code:

```python
{code}
```

The dataset must produce these expected results:
{expected}

Input file referenced: {filename}

Requirements:
- Column names must match exactly what the code expects
- Data types must be appropriate (numeric for calculations)
- Values should be realistic for the domain
- The data must produce the expected results when the code runs"""


class DatasetGenerator:
    """Generate CSV datasets that produce expected results when code runs."""

    def __init__(self, ai_client=None):
        self.ai_client = ai_client

    def generate_for_code_block(
        self,
        code_block: CodeBlock,
        num_rows: int = 100,
    ) -> 'pd.DataFrame':
        """Generate a dataset for a code block using AI."""
        if pd is None:
            raise ImportError("pandas is required for dataset generation")
        if not self.ai_client:
            raise ValueError("AI client required for dataset generation")

        expected_str = '\n'.join(
            f"- {r.variable_name} should equal {r.expected_value} (tolerance: {r.tolerance})"
            for r in code_block.expected_results
        ) or "No specific result targets"

        filename = code_block.input_datasets[0] if code_block.input_datasets else 'data.csv'

        prompt = DATASET_GEN_USER.format(
            num_rows=num_rows,
            code=code_block.code,
            expected=expected_str,
            filename=filename,
        )

        response = self.ai_client.generate(DATASET_GEN_SYSTEM, prompt, max_tokens=4096)

        # Parse CSV from response
        csv_text = self._extract_csv(response)
        df = pd.read_csv(pd.io.common.StringIO(csv_text))

        return df

    def _extract_csv(self, response: str) -> str:
        """Extract CSV content from AI response."""
        text = response.strip()

        # Remove markdown code fences
        if text.startswith('```'):
            lines = text.split('\n')
            text = '\n'.join(lines[1:])
        if text.endswith('```'):
            text = text[:-3].strip()

        return text


# ============================================================================
# Dataset Validator
# ============================================================================

class DatasetValidator:
    """Validate that datasets produce expected results when code runs."""

    def validate(
        self,
        code_block: CodeBlock,
        datasets: Dict[str, 'pd.DataFrame'],
        timeout: int = 10,
    ) -> ValidationResult:
        """Execute code against datasets and compare results."""
        if pd is None:
            return ValidationResult(
                code_block_id=code_block.id,
                passed=False,
                actual_results={},
                expected_results={},
                errors=["pandas not available"],
            )

        expected_map = {
            r.variable_name: r.expected_value
            for r in code_block.expected_results
        }

        errors = []
        actual_results = {}

        try:
            actual_results = self._execute_code(code_block.code, datasets, timeout)

            if '__error__' in actual_results:
                errors.append(str(actual_results.pop('__error__')))
        except Exception as e:
            errors.append(f"Execution error: {e}")
            return ValidationResult(
                code_block_id=code_block.id,
                passed=False,
                actual_results={},
                expected_results=expected_map,
                errors=errors,
            )

        # Compare results
        passed = True
        for er in code_block.expected_results:
            actual = actual_results.get(er.variable_name)
            if actual is None:
                passed = False
                errors.append(f"Variable '{er.variable_name}' not found in output")
                continue

            if not self._values_match(actual, er.expected_value, er.tolerance):
                passed = False
                errors.append(
                    f"{er.variable_name}: expected {er.expected_value}, got {actual} "
                    f"(tolerance: {er.tolerance})"
                )

        return ValidationResult(
            code_block_id=code_block.id,
            passed=passed,
            actual_results=actual_results,
            expected_results=expected_map,
            errors=errors,
        )

    def _execute_code(
        self,
        code: str,
        datasets: Dict[str, 'pd.DataFrame'],
        timeout: int,
    ) -> Dict[str, Any]:
        """Execute code in a subprocess with restricted environment."""
        # Write datasets to temp files
        temp_dir = tempfile.mkdtemp()
        temp_files = {}

        try:
            for name, df in datasets.items():
                path = Path(temp_dir) / f"{name}.csv"
                df.to_csv(path, index=False)
                temp_files[name] = str(path)

            # Modify code to use temp paths
            modified = code
            for name, path in temp_files.items():
                # Replace read_csv('name.csv') with temp path
                modified = re.sub(
                    rf"""(read_csv\s*\(\s*)['"]{re.escape(name)}(?:\.csv)?['"]""",
                    rf"""\1'{path.replace(chr(92), '/')}'""",
                    modified,
                )
                # Also handle variable assignments like: df = pd.read_csv('filename')
                modified = re.sub(
                    rf"""['"]{re.escape(name)}\.csv['"]""",
                    f"'{path.replace(chr(92), '/')}'",
                    modified,
                )

            # Pre-load datasets that are referenced as variables but not via read_csv
            preload_lines = []
            for name, path in temp_files.items():
                # Check if variable name is used in code but not loaded via read_csv
                if re.search(rf'\b{re.escape(name)}\b', modified) and \
                   not re.search(rf'{re.escape(name)}\s*=\s*pd\.read', modified):
                    safe_path = path.replace(chr(92), '/')
                    preload_lines.append(f"{name} = pd.read_csv('{safe_path}')")

            # Add result capture
            capture_code = """
import json, sys

# Capture numeric results
__results = {}
for __name, __val in list(locals().items()):
    if __name.startswith('_') or __name in ('pd', 'np', 'json', 'sys'):
        continue
    try:
        if isinstance(__val, (int, float)):
            __results[__name.lower()] = float(__val)
        elif hasattr(__val, 'item'):
            __results[__name.lower()] = float(__val.item())
    except (TypeError, ValueError):
        pass

print('__VALIDATION_RESULTS__:' + json.dumps(__results))
"""
            preload = '\n'.join(preload_lines)
            full_code = (
                "import warnings\nwarnings.filterwarnings('ignore')\n"
                "import pandas as pd\nimport numpy as np\n\n"
                + preload + ("\n" if preload else "")
                + modified + "\n\n" + capture_code
            )

            # Write to temp file and execute
            script_path = Path(temp_dir) / "validate.py"
            script_path.write_text(full_code, encoding='utf-8')

            result = subprocess.run(
                ['python', str(script_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=temp_dir,
            )

            if result.returncode != 0:
                return {'__error__': result.stderr[:500]}

            # Parse results
            output = result.stdout
            if '__VALIDATION_RESULTS__:' in output:
                json_str = output.split('__VALIDATION_RESULTS__:')[1].strip()
                return json.loads(json_str)

            return {'__error__': 'No results captured from execution'}

        except subprocess.TimeoutExpired:
            return {'__error__': f'Code execution timed out after {timeout}s'}
        finally:
            # Cleanup
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    @staticmethod
    def _values_match(actual: Any, expected: Any, tolerance: float) -> bool:
        """Compare values with tolerance."""
        try:
            a = float(actual)
            e = float(expected)
            if e == 0:
                return abs(a) <= tolerance
            return abs(a - e) / abs(e) <= tolerance
        except (TypeError, ValueError):
            return str(actual).lower() == str(expected).lower()

    @staticmethod
    def _compare(actual: Any, expected: Any, tolerance: float = 0.01) -> Tuple[float, 'ResultMatchStatus']:
        """Compare actual vs expected and return difference + match status.

        Returns:
            (difference, status) where difference is relative error
            and status is a ResultMatchStatus enum value.
        """
        try:
            a = float(actual)
            e = float(expected)
            if e == 0:
                diff = abs(a)
            else:
                diff = abs(a - e) / abs(e)

            if diff <= tolerance:
                return diff, ResultMatchStatus.MATCH
            elif diff <= tolerance * 5:
                return diff, ResultMatchStatus.CLOSE
            else:
                return diff, ResultMatchStatus.MISMATCH
        except (TypeError, ValueError):
            match = str(actual).lower() == str(expected).lower()
            return (0.0 if match else 1.0,
                    ResultMatchStatus.MATCH if match else ResultMatchStatus.MISMATCH)


# ============================================================================
# Dataset Auditor
# ============================================================================

class DatasetAuditor:
    """Quality checks on generated datasets."""

    def audit(self, df: 'pd.DataFrame', name: str) -> DatasetAudit:
        """Run quality checks on a DataFrame."""
        if pd is None or np is None:
            return DatasetAudit(
                dataset_name=name, row_count=0, column_count=0,
                issues=[{"type": "error", "severity": "critical", "details": "pandas not available"}],
                quality_score=0,
            )

        issues = []

        # Missing values
        null_total = int(df.isnull().sum().sum())
        if null_total > 0:
            null_cols = {col: int(c) for col, c in df.isnull().sum().items() if c > 0}
            issues.append({
                "type": "missing_values",
                "severity": "warning",
                "details": f"{null_total} missing values in columns: {null_cols}",
                "count": null_total,
            })

        # Duplicates
        dup_count = int(df.duplicated().sum())
        if dup_count > 0:
            issues.append({
                "type": "duplicates",
                "severity": "info",
                "details": f"{dup_count} duplicate rows ({dup_count/len(df)*100:.1f}%)",
                "count": dup_count,
            })

        # Outliers in numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            q1 = df[col].quantile(0.25)
            q3 = df[col].quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue
            outliers = int(((df[col] < q1 - 1.5 * iqr) | (df[col] > q3 + 1.5 * iqr)).sum())
            if outliers > len(df) * 0.05:
                issues.append({
                    "type": "outliers",
                    "severity": "info",
                    "details": f"Column '{col}' has {outliers} outliers ({outliers/len(df)*100:.1f}%)",
                    "column": col,
                    "count": outliers,
                })

        # Constant columns (zero variance)
        for col in df.columns:
            if df[col].nunique() <= 1:
                issues.append({
                    "type": "constant_column",
                    "severity": "warning",
                    "details": f"Column '{col}' has only 1 unique value",
                    "column": col,
                })

        # Calculate quality score
        score = 100.0
        for issue in issues:
            sev = issue.get("severity", "info")
            if sev == "critical":
                score -= 20
            elif sev == "warning":
                score -= 10
            elif sev == "info":
                score -= 5
        score = max(0.0, score)

        return DatasetAudit(
            dataset_name=name,
            row_count=len(df),
            column_count=len(df.columns),
            issues=issues,
            quality_score=score,
        )
