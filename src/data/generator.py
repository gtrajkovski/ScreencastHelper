"""Flexible data generator based on AI-analyzed requirements."""

import json
import random
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

try:
    from faker import Faker
    fake = Faker()
except ImportError:
    fake = None

from ..config import DatasetConfig
from ..ai.client import AIClient
from ..ai.prompts import DATA_ANALYZER, DATA_GENERATOR


@dataclass
class GeneratedDataset:
    """A generated dataset with metadata."""
    config: DatasetConfig
    dataframe: pd.DataFrame
    generation_code: str
    preview: str

    def save(self, directory: Path) -> Path:
        """Save dataset to CSV."""
        filepath = directory / self.config.filename
        self.dataframe.to_csv(filepath, index=False)
        return filepath


class DataSchemaAnalyzer:
    """AI-powered schema analysis and design."""

    def __init__(self):
        self.ai = AIClient()

    def analyze_requirements(
        self,
        topic: str,
        demo_requirements: str,
        demo_type: str,
        duration_minutes: int
    ) -> List[DatasetConfig]:
        """Analyze demo requirements and design optimal datasets."""

        prompt = f"""Analyze these demo requirements and design optimal datasets:

TOPIC: {topic}
DEMO TYPE: {demo_type}
DURATION: {duration_minutes} minutes
REQUIREMENTS:
{demo_requirements}

Design datasets that:
1. Support all demo needs
2. Are sized appropriately for a {duration_minutes}-minute demo
3. Have realistic, authentic data
4. Include data quality issues ONLY if the demo is about data quality

Output JSON with this structure:
{{
  "datasets": [
    {{
      "name": "descriptive_name",
      "filename": "name.csv",
      "purpose": "why this dataset is needed",
      "columns": [
        {{"name": "col1", "type": "string", "description": "...", "example": "..."}},
        ...
      ],
      "rows": 1000,
      "issues": null,
      "relationships": null
    }}
  ],
  "reasoning": "Explanation of design decisions"
}}"""

        response = self.ai.generate(DATA_ANALYZER, prompt)

        # Parse JSON response
        try:
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]

            data = json.loads(json_str)

            configs = []
            for ds in data.get("datasets", []):
                config = DatasetConfig(
                    name=ds["name"],
                    filename=ds["filename"],
                    columns=ds["columns"],
                    rows=ds["rows"],
                    issues=ds.get("issues"),
                    relationships=ds.get("relationships")
                )
                configs.append(config)

            return configs

        except (json.JSONDecodeError, KeyError):
            # Fallback: return basic config
            return [DatasetConfig(
                name="sample_data",
                filename="sample_data.csv",
                columns=[
                    {"name": "id", "type": "int", "description": "Row ID"},
                    {"name": "value", "type": "float", "description": "Value"}
                ],
                rows=1000,
                issues=None,
                relationships=None
            )]


class FlexibleDataGenerator:
    """Generate datasets based on schema configurations."""

    def __init__(self):
        self.ai = AIClient()

    def generate_dataset(self, config: DatasetConfig) -> GeneratedDataset:
        """Generate a dataset from configuration."""

        # Generate data based on column types
        data = {}
        for col in config.columns:
            data[col["name"]] = self._generate_column(
                col_type=col.get("type", "string"),
                count=config.rows,
                description=col.get("description", ""),
                example=col.get("example", "")
            )

        df = pd.DataFrame(data)

        # Apply data quality issues if specified
        if config.issues:
            df = self._apply_issues(df, config.issues)

        # Generate the code that would create this data
        code = self._generate_creation_code(config)

        # Create preview
        preview = df.head(10).to_string()

        return GeneratedDataset(
            config=config,
            dataframe=df,
            generation_code=code,
            preview=preview
        )

    def _generate_column(
        self,
        col_type: str,
        count: int,
        description: str = "",
        example: str = ""
    ) -> list:
        """Generate column data based on type and hints."""

        col_type = col_type.lower()
        desc_lower = description.lower()

        # Infer from description first
        if fake:
            if "name" in desc_lower and ("user" in desc_lower or "customer" in desc_lower):
                return [fake.name() for _ in range(count)]
            elif "email" in desc_lower:
                return [fake.email() for _ in range(count)]
            elif "date" in desc_lower and "signup" in desc_lower:
                return [fake.date_between(start_date='-2y', end_date='today')
                        for _ in range(count)]
            elif "date" in desc_lower:
                return [fake.date_between(start_date='-1y', end_date='today')
                        for _ in range(count)]

        if "timestamp" in desc_lower or "datetime" in col_type:
            base = datetime.now()
            return [(base - timedelta(days=random.randint(0, 365),
                                      hours=random.randint(0, 23),
                                      minutes=random.randint(0, 59))).isoformat()
                    for _ in range(count)]

        if "amount" in desc_lower or "price" in desc_lower:
            return [round(random.uniform(1, 500), 2) for _ in range(count)]

        if "status" in desc_lower:
            statuses = ["completed", "pending", "failed"]
            weights = [85, 10, 5]
            return random.choices(statuses, weights=weights, k=count)

        if "plan" in desc_lower or "type" in desc_lower or "category" in desc_lower:
            if example:
                options = [x.strip() for x in example.split(",")]
            else:
                options = ["type_a", "type_b", "type_c"]
            return [random.choice(options) for _ in range(count)]

        if "id" in desc_lower or col_type == "id":
            prefix = "ID"
            if "user" in desc_lower:
                prefix = "U"
            elif "transaction" in desc_lower or "txn" in desc_lower:
                prefix = "T"
            elif "order" in desc_lower:
                prefix = "O"
            return [f"{prefix}{i+1:05d}" for i in range(count)]

        # Fallback to type-based generation
        if col_type in ["int", "integer"]:
            return [random.randint(1, 1000) for _ in range(count)]
        elif col_type in ["float", "decimal", "number"]:
            return [round(random.uniform(0, 1000), 2) for _ in range(count)]
        elif col_type in ["date"]:
            base = datetime.now()
            return [(base - timedelta(days=random.randint(0, 365))).strftime('%Y-%m-%d')
                    for _ in range(count)]
        elif col_type in ["bool", "boolean"]:
            return [random.choice([True, False]) for _ in range(count)]
        else:
            # String fallback
            if fake:
                return [fake.word() for _ in range(count)]
            return [f"value_{i}" for i in range(count)]

    def _apply_issues(self, df: pd.DataFrame, issues: Dict) -> pd.DataFrame:
        """Apply data quality issues to dataframe."""

        df = df.copy()

        # Null injection
        if "nulls" in issues:
            null_config = issues["nulls"]
            if isinstance(null_config, dict):
                columns = null_config.get("columns", df.columns[:2].tolist())
                percentage = null_config.get("percentage", 0.05)
            else:
                columns = df.columns[:2].tolist()
                percentage = float(null_config)

            for col in columns:
                if col in df.columns:
                    n_nulls = int(len(df) * percentage)
                    null_indices = random.sample(range(len(df)), min(n_nulls, len(df)))
                    df.loc[null_indices, col] = None

        # Duplicate injection
        if "duplicates" in issues:
            dup_config = issues["duplicates"]
            n_dupes = dup_config.get("count", 10) if isinstance(dup_config, dict) else int(dup_config)
            dupes = df.sample(n=min(n_dupes, len(df)))
            df = pd.concat([df, dupes], ignore_index=True)

        # Type errors
        if "type_errors" in issues:
            type_config = issues["type_errors"]
            col = type_config.get("column") if isinstance(type_config, dict) else None
            bad_values = type_config.get("bad_values", ["N/A", "unknown", "-"]) if isinstance(type_config, dict) else ["N/A"]

            if col and col in df.columns:
                n_errors = int(len(df) * 0.02)
                error_indices = random.sample(range(len(df)), min(n_errors, len(df)))
                for idx in error_indices:
                    df.loc[idx, col] = random.choice(bad_values)

        # Outliers
        if "outliers" in issues:
            outlier_config = issues["outliers"]
            col = outlier_config.get("column") if isinstance(outlier_config, dict) else None
            n_outliers = outlier_config.get("count", 5) if isinstance(outlier_config, dict) else 5
            multiplier = outlier_config.get("multiplier", 100) if isinstance(outlier_config, dict) else 100

            if col and col in df.columns:
                outlier_indices = random.sample(range(len(df)), min(n_outliers, len(df)))
                for idx in outlier_indices:
                    try:
                        current_val = float(df.loc[idx, col])
                        df.loc[idx, col] = current_val * multiplier
                    except (ValueError, TypeError):
                        pass

        # New/unexpected columns
        if "new_columns" in issues:
            new_col_config = issues["new_columns"]
            col_name = new_col_config.get("name", "unexpected_column") if isinstance(new_col_config, dict) else "unexpected_column"
            df[col_name] = [random.choice(["value_a", "value_b", None])
                          for _ in range(len(df))]

        return df

    def _generate_creation_code(self, config: DatasetConfig) -> str:
        """Generate Python code that would create this dataset."""

        code_lines = [
            '"""',
            f'Generate {config.name} dataset',
            f'Rows: {config.rows}',
            '"""',
            '',
            'import pandas as pd',
            'import random',
            'from datetime import datetime, timedelta',
            '',
            'try:',
            '    from faker import Faker',
            '    fake = Faker()',
            'except ImportError:',
            '    fake = None',
            '',
            f'def generate_{config.name.replace(" ", "_").replace("-", "_").lower()}(n={config.rows}):',
            '    """Generate the dataset."""',
            '    data = []',
            '    for i in range(n):',
            '        row = {}',
        ]

        for col in config.columns:
            col_name = col["name"]
            col_type = col.get("type", "string")
            desc = col.get("description", "").lower()

            if "id" in col_name.lower():
                code_lines.append(f'        row["{col_name}"] = f"ID{{i+1:05d}}"')
            elif "name" in col_name.lower():
                code_lines.append(f'        row["{col_name}"] = fake.name() if fake else f"Name_{{i}}"')
            elif "email" in col_name.lower():
                code_lines.append(f'        row["{col_name}"] = fake.email() if fake else f"user{{i}}@example.com"')
            elif "date" in col_name.lower():
                code_lines.append(f'        row["{col_name}"] = (datetime.now() - timedelta(days=random.randint(0, 365))).strftime("%Y-%m-%d")')
            elif "amount" in col_name.lower() or "price" in col_name.lower():
                code_lines.append(f'        row["{col_name}"] = round(random.uniform(1, 500), 2)')
            elif "status" in col_name.lower():
                code_lines.append(f'        row["{col_name}"] = random.choice(["completed", "pending", "failed"])')
            elif col_type in ["int", "integer"]:
                code_lines.append(f'        row["{col_name}"] = random.randint(1, 1000)')
            elif col_type in ["float", "number"]:
                code_lines.append(f'        row["{col_name}"] = round(random.uniform(0, 1000), 2)')
            else:
                code_lines.append(f'        row["{col_name}"] = f"value_{{i}}"')

        code_lines.extend([
            '        data.append(row)',
            '    return pd.DataFrame(data)',
            '',
            '',
            'if __name__ == "__main__":',
            f'    df = generate_{config.name.replace(" ", "_").replace("-", "_").lower()}()',
            f'    df.to_csv("data/{config.filename}", index=False)',
            '    print(f"Generated {len(df)} rows")',
            '    print(df.head())',
        ])

        return '\n'.join(code_lines)

    def generate_all(
        self,
        configs: List[DatasetConfig],
        output_dir: Path
    ) -> List[GeneratedDataset]:
        """Generate all datasets and save to directory."""

        output_dir.mkdir(parents=True, exist_ok=True)

        datasets = []
        for config in configs:
            dataset = self.generate_dataset(config)
            dataset.save(output_dir)
            datasets.append(dataset)

        return datasets
