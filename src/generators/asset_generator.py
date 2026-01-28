"""Generate supporting assets: terminal output, CSV, YAML, HTML."""

import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass
import yaml


@dataclass
class GeneratedAsset:
    """A generated asset file."""
    filename: str
    content: str
    file_type: str

    def save(self, directory: Path) -> Path:
        """Save asset to directory."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        filepath = directory / self.filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.content)
        return filepath


class AssetGenerator:
    """Generate supporting assets for screencasts."""

    # Terminal color codes
    COLORS = {
        'red': '\033[1;31m',
        'green': '\033[1;32m',
        'yellow': '\033[1;33m',
        'blue': '\033[1;34m',
        'magenta': '\033[1;35m',
        'cyan': '\033[1;36m',
        'white': '\033[1;37m',
        'reset': '\033[0m',
        'bold': '\033[1m',
    }

    def generate_terminal_output(
        self,
        validation_results: List[Dict],
        title: str = "Validation Results"
    ) -> GeneratedAsset:
        """Generate colorful terminal validation output.

        Args:
            validation_results: List of validation check results
            title: Output title

        Returns:
            GeneratedAsset with bash script content
        """
        lines = [
            '#!/bin/bash',
            '# Terminal output simulation',
            '',
            f'echo ""',
            f'echo "{self.COLORS["cyan"]}{"="*60}{self.COLORS["reset"]}"',
            f'echo "{self.COLORS["bold"]}{title}{self.COLORS["reset"]}"',
            f'echo "{self.COLORS["cyan"]}{"="*60}{self.COLORS["reset"]}"',
            'echo ""',
        ]

        passed = 0
        failed = 0

        for result in validation_results:
            check_name = result.get('check', 'Unknown check')
            status = result.get('status', 'unknown')
            message = result.get('message', '')

            if status == 'pass':
                passed += 1
                icon = f'{self.COLORS["green"]}Y{self.COLORS["reset"]}'
                status_text = f'{self.COLORS["green"]}PASS{self.COLORS["reset"]}'
            elif status == 'fail':
                failed += 1
                icon = f'{self.COLORS["red"]}X{self.COLORS["reset"]}'
                status_text = f'{self.COLORS["red"]}FAIL{self.COLORS["reset"]}'
            else:
                icon = f'{self.COLORS["yellow"]}?{self.COLORS["reset"]}'
                status_text = f'{self.COLORS["yellow"]}WARN{self.COLORS["reset"]}'

            lines.append(f'echo "{icon} [{status_text}] {check_name}"')
            if message:
                lines.append(f'echo "     {message}"')

        # Summary
        lines.extend([
            'echo ""',
            f'echo "{self.COLORS["cyan"]}{"-"*60}{self.COLORS["reset"]}"',
            f'echo "Summary: {self.COLORS["green"]}{passed} passed{self.COLORS["reset"]}, '
            f'{self.COLORS["red"]}{failed} failed{self.COLORS["reset"]}"',
            f'echo "{self.COLORS["cyan"]}{"-"*60}{self.COLORS["reset"]}"',
        ])

        return GeneratedAsset(
            filename='terminal_output.sh',
            content='\n'.join(lines),
            file_type='bash'
        )

    def generate_sample_csv(
        self,
        columns: List[str],
        rows: int = 10,
        include_issues: bool = True,
        issues: Optional[Dict] = None
    ) -> GeneratedAsset:
        """Generate sample CSV with optional data quality issues.

        Args:
            columns: Column names
            rows: Number of data rows
            include_issues: Whether to include intentional issues
            issues: Specific issues to include (nulls, new_columns, etc.)

        Returns:
            GeneratedAsset with CSV content
        """
        # Default issues if not specified
        if issues is None and include_issues:
            issues = {
                'null_rows': [3, 7],  # Rows with null values
                'new_column': 'campaign_region',  # Unexpected column
                'type_mismatch_row': 5,  # Row with type issues
            }

        # Generate header
        header = columns.copy()
        if issues and 'new_column' in issues:
            header.append(issues['new_column'])

        lines = [','.join(header)]

        # Generate data rows
        base_date = datetime.now() - timedelta(days=rows)

        for i in range(rows):
            row_data = []
            for col in columns:
                if issues and 'null_rows' in issues and i in issues['null_rows']:
                    # Insert null for some columns
                    if random.random() < 0.3:
                        row_data.append('')
                        continue

                # Generate appropriate data based on column name
                if 'date' in col.lower():
                    val = (base_date + timedelta(days=i)).strftime('%Y-%m-%d')
                elif 'id' in col.lower():
                    val = f'ID_{1000 + i}'
                elif 'amount' in col.lower() or 'value' in col.lower():
                    val = str(round(random.uniform(100, 10000), 2))
                elif 'count' in col.lower() or 'quantity' in col.lower():
                    val = str(random.randint(1, 100))
                elif 'type' in col.lower() or 'category' in col.lower():
                    val = random.choice(['A', 'B', 'C', 'D'])
                else:
                    val = f'value_{i}'

                # Type mismatch injection
                if issues and 'type_mismatch_row' in issues and i == issues['type_mismatch_row']:
                    if 'amount' in col.lower() or 'count' in col.lower():
                        val = 'N/A'  # String where number expected

                row_data.append(val)

            # Add new column value if present
            if issues and 'new_column' in issues:
                row_data.append(random.choice(['US-East', 'US-West', 'EU', 'APAC', '']))

            lines.append(','.join(row_data))

        return GeneratedAsset(
            filename='sample_data.csv',
            content='\n'.join(lines),
            file_type='csv'
        )

    def generate_lineage_yaml(
        self,
        source_table: str,
        transformations: List[Dict],
        target_table: str,
        metadata: Optional[Dict] = None
    ) -> GeneratedAsset:
        """Generate data lineage YAML file.

        Args:
            source_table: Source table/file name
            transformations: List of transformation steps
            target_table: Target table/file name
            metadata: Additional metadata

        Returns:
            GeneratedAsset with YAML content
        """
        lineage = {
            'lineage': {
                'source': {
                    'name': source_table,
                    'type': 'table',
                    'database': metadata.get('source_db', 'raw_data') if metadata else 'raw_data',
                },
                'transformations': [],
                'target': {
                    'name': target_table,
                    'type': 'table',
                    'database': metadata.get('target_db', 'analytics') if metadata else 'analytics',
                },
                'metadata': {
                    'created_at': datetime.now().isoformat(),
                    'created_by': metadata.get('created_by', 'screencast_studio') if metadata else 'screencast_studio',
                    'version': '1.0',
                }
            }
        }

        for i, transform in enumerate(transformations, 1):
            lineage['lineage']['transformations'].append({
                'step': i,
                'name': transform.get('name', f'step_{i}'),
                'description': transform.get('description', ''),
                'type': transform.get('type', 'custom'),
                'columns_affected': transform.get('columns', []),
            })

        yaml_content = yaml.dump(lineage, default_flow_style=False, sort_keys=False)

        # Add markers throughout for screencast navigation
        final_content = ['# Data Lineage Document',
                        '# Generated by ScreenCast Studio',
                        '# Markers: Search for ">>> STEP" to navigate during recording',
                        '']

        for line in yaml_content.split('\n'):
            final_content.append(line)
            # Add step marker after each transformation block
            if 'step:' in line:
                step_num = line.split(':')[1].strip()
                final_content.insert(-1, f'    # >>> STEP {step_num} <<<')

        return GeneratedAsset(
            filename='lineage.yaml',
            content='\n'.join(final_content),
            file_type='yaml'
        )

    def generate_html_report(
        self,
        title: str,
        sections: List[Dict],
        theme: str = 'dark'
    ) -> GeneratedAsset:
        """Generate HTML validation report.

        Args:
            title: Report title
            sections: List of report sections
            theme: 'dark' or 'light'

        Returns:
            GeneratedAsset with HTML content
        """
        bg_color = '#1a1a2e' if theme == 'dark' else '#ffffff'
        text_color = '#eaeaea' if theme == 'dark' else '#333333'
        card_bg = '#16213e' if theme == 'dark' else '#f5f5f5'
        accent = '#e94560'
        success = '#00d26a'
        warning = '#ffc107'

        sections_html = []
        for section in sections:
            status = section.get('status', 'info')
            status_color = {
                'pass': success,
                'fail': accent,
                'warning': warning,
                'info': '#17a2b8'
            }.get(status, text_color)

            items_html = ''
            for item in section.get('items', []):
                item_status = item.get('status', 'info')
                item_color = {
                    'pass': success,
                    'fail': accent,
                    'warning': warning,
                }.get(item_status, text_color)

                icon = {'pass': 'Y', 'fail': 'X', 'warning': '!'}.get(item_status, '-')

                items_html += f'''
                <div class="item" style="border-left: 3px solid {item_color}; padding-left: 15px; margin: 10px 0;">
                    <span style="color: {item_color}; font-weight: bold;">{icon}</span>
                    <span style="color: {text_color};">{item.get('name', 'Check')}</span>
                    <p style="color: {text_color}; opacity: 0.8; margin: 5px 0; font-size: 0.9em;">
                        {item.get('message', '')}
                    </p>
                </div>
                '''

            sections_html.append(f'''
            <div class="card" style="background: {card_bg}; border-radius: 8px; padding: 20px; margin: 15px 0; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
                <h3 style="color: {status_color}; margin-top: 0; border-bottom: 1px solid {status_color}; padding-bottom: 10px;">
                    {section.get('title', 'Section')}
                    <span style="float: right; font-size: 0.8em; background: {status_color}; color: white; padding: 2px 10px; border-radius: 12px;">
                        {status.upper()}
                    </span>
                </h3>
                {items_html}
            </div>
            ''')

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: {bg_color};
            color: {text_color};
            line-height: 1.6;
            padding: 20px;
        }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        h1 {{
            color: {text_color};
            border-bottom: 2px solid {accent};
            padding-bottom: 15px;
            margin-bottom: 25px;
        }}
        .timestamp {{
            color: {text_color};
            opacity: 0.6;
            font-size: 0.9em;
            margin-bottom: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        <p class="timestamp">Generated: {timestamp}</p>
        {''.join(sections_html)}
    </div>
</body>
</html>'''

        return GeneratedAsset(
            filename='validation_report.html',
            content=html,
            file_type='html'
        )
