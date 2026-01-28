"""Tests for asset generator."""

import pytest
import tempfile
from pathlib import Path
from src.generators.asset_generator import AssetGenerator, GeneratedAsset


class TestAssetGenerator:
    """Test suite for AssetGenerator."""

    def test_generated_asset_dataclass(self):
        """Test GeneratedAsset dataclass."""
        asset = GeneratedAsset(
            filename="test.txt",
            content="Test content",
            file_type="text"
        )

        assert asset.filename == "test.txt"
        assert asset.content == "Test content"
        assert asset.file_type == "text"

    def test_generated_asset_save(self):
        """Test saving GeneratedAsset to file."""
        asset = GeneratedAsset(
            filename="test.txt",
            content="Test content",
            file_type="text"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = asset.save(Path(tmpdir))

            assert filepath.exists()
            assert filepath.read_text() == "Test content"

    def test_generate_terminal_output(self):
        """Test terminal output generation."""
        generator = AssetGenerator()

        results = [
            {'check': 'Schema check', 'status': 'pass', 'message': 'OK'},
            {'check': 'Null check', 'status': 'fail', 'message': 'Found nulls'},
        ]

        asset = generator.generate_terminal_output(results, "Test Results")

        assert asset.filename == "terminal_output.sh"
        assert asset.file_type == "bash"
        assert "#!/bin/bash" in asset.content
        assert "Schema check" in asset.content
        assert "Null check" in asset.content
        assert "PASS" in asset.content
        assert "FAIL" in asset.content

    def test_generate_terminal_output_summary(self):
        """Test terminal output includes summary."""
        generator = AssetGenerator()

        results = [
            {'check': 'Check 1', 'status': 'pass'},
            {'check': 'Check 2', 'status': 'pass'},
            {'check': 'Check 3', 'status': 'fail'},
        ]

        asset = generator.generate_terminal_output(results)

        assert "2 passed" in asset.content
        assert "1 failed" in asset.content

    def test_generate_sample_csv(self):
        """Test CSV generation."""
        generator = AssetGenerator()

        columns = ['date', 'id', 'amount', 'category']
        asset = generator.generate_sample_csv(columns, rows=5, include_issues=False)

        assert asset.filename == "sample_data.csv"
        assert asset.file_type == "csv"

        lines = asset.content.split('\n')
        assert len(lines) == 6  # Header + 5 rows
        assert lines[0] == "date,id,amount,category"

    def test_generate_sample_csv_with_issues(self):
        """Test CSV generation with data quality issues."""
        generator = AssetGenerator()

        columns = ['id', 'amount']
        issues = {
            'null_rows': [1],
            'new_column': 'extra_col'
        }

        asset = generator.generate_sample_csv(columns, rows=3, issues=issues)

        lines = asset.content.split('\n')
        header = lines[0].split(',')

        # Check for extra column
        assert 'extra_col' in header

    def test_generate_lineage_yaml(self):
        """Test YAML lineage generation."""
        generator = AssetGenerator()

        transformations = [
            {'name': 'filter', 'description': 'Filter nulls'},
            {'name': 'aggregate', 'description': 'Group by category'},
        ]

        asset = generator.generate_lineage_yaml(
            source_table='raw_data',
            transformations=transformations,
            target_table='clean_data'
        )

        assert asset.filename == "lineage.yaml"
        assert asset.file_type == "yaml"
        assert "raw_data" in asset.content
        assert "clean_data" in asset.content
        assert "filter" in asset.content
        assert "aggregate" in asset.content

    def test_generate_lineage_yaml_has_markers(self):
        """Test YAML lineage has navigation markers."""
        generator = AssetGenerator()

        transformations = [
            {'name': 'step1', 'description': 'First step'},
        ]

        asset = generator.generate_lineage_yaml(
            source_table='src',
            transformations=transformations,
            target_table='tgt'
        )

        assert ">>> STEP" in asset.content

    def test_generate_html_report(self):
        """Test HTML report generation."""
        generator = AssetGenerator()

        sections = [
            {
                'title': 'Data Quality',
                'status': 'pass',
                'items': [
                    {'name': 'Completeness', 'status': 'pass', 'message': '100%'},
                ]
            }
        ]

        asset = generator.generate_html_report("Test Report", sections)

        assert asset.filename == "validation_report.html"
        assert asset.file_type == "html"
        assert "<!DOCTYPE html>" in asset.content
        assert "Test Report" in asset.content
        assert "Data Quality" in asset.content
        assert "Completeness" in asset.content

    def test_generate_html_report_dark_theme(self):
        """Test HTML report with dark theme."""
        generator = AssetGenerator()

        asset = generator.generate_html_report("Test", [], theme='dark')

        assert "#1a1a2e" in asset.content  # Dark background color

    def test_generate_html_report_light_theme(self):
        """Test HTML report with light theme."""
        generator = AssetGenerator()

        asset = generator.generate_html_report("Test", [], theme='light')

        assert "#ffffff" in asset.content  # Light background color
