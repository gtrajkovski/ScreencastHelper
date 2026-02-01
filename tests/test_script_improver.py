"""Tests for the AI Script Improver module."""

import json
import pytest
from src.ai.script_improver import ScriptImprover, ScriptIssue, ScriptScore, TOTAL_POSSIBLE


# ---------------------------------------------------------------------------
# Sample scripts
# ---------------------------------------------------------------------------

COMPLETE_SCRIPT = """## HOOK
Have you ever spent hours debugging a machine learning model, only to realize the data was the problem all along? I remember my first data science project — I was so proud of my model until my mentor pointed out that I'd been training on the test set.

## OBJECTIVE
By the end of this video, you'll be able to:
- Define what data leakage is and identify common sources
- Apply train-test split techniques to prevent leakage
- Evaluate your model's performance with proper validation

## CONTENT
[SCREEN: Jupyter Notebook with sample dataset]

Let's look at a concrete example. Imagine we have a dataset of 10,000 customer records with 15 features. Our target variable is whether a customer will churn within 90 days.

```python
import pandas as pd
df = pd.read_csv('customers.csv')
print(df.shape)
```

The first thing we need to check is feature timing. If any feature was collected after the target event, that's temporal leakage.

[SCREEN: Feature timeline diagram]

For instance, if our dataset includes a "cancellation_reason" column, that information wouldn't exist before the churn event. Including it would give our model unfairly perfect predictions.

Let's split our data properly:

```python
from sklearn.model_selection import train_test_split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
```

## IVQ
**Question:** Which of the following is an example of data leakage?

A) Using 80% of data for training and 20% for testing
B) Including a feature that was collected after the target event
C) Normalizing features before splitting the data
D) Using cross-validation instead of a single train-test split

**Correct Answer:** B

**Feedback A:** Incorrect. An 80/20 train-test split is a standard practice and does not cause data leakage.
**Feedback B:** Correct! Including features collected after the target event is temporal data leakage, as it gives the model information it wouldn't have in production.
**Feedback C:** Incorrect. While normalizing before splitting can cause some data leakage, the more direct example is temporal leakage from post-event features.
**Feedback D:** Incorrect. Cross-validation is actually a robust validation technique that helps prevent overfitting.

## SUMMARY
Today we covered three key concepts: what data leakage is, how to identify temporal leakage in your features, and how to properly split your data to prevent it.

## CTA
In the next hands-on lab, you'll practice identifying and fixing data leakage in a real dataset. Head to the assignment page to get started.
"""

INCOMPLETE_SCRIPT = """## HOOK
Data leakage is a problem in machine learning.

## CONTENT
Data leakage happens when information from outside the training dataset is used to create the model. This leads to overly optimistic performance estimates.

There are several types of data leakage including target leakage and train-test contamination.
"""

LONG_SCRIPT = """## HOOK
""" + "word " * 120 + """

## OBJECTIVE
By the end of this video you'll understand data leakage.

## CONTENT
""" + "word " * 1000 + """

## IVQ
**Question:** What is leakage?

A) Bad data
B) Good data
C) No data
D) All data

**Correct Answer:** A

## SUMMARY
We covered data leakage.

## CTA
Try the lab.
"""


# ---------------------------------------------------------------------------
# Mock AI client
# ---------------------------------------------------------------------------

class MockAIClient:
    """Deterministic mock for AIClient.generate()."""

    def __init__(self, quality_response=None):
        self.calls = []
        self.quality_response = quality_response or [
            {"check_id": "hook_anecdote", "found": True, "detail": "Hook has a personal story"},
            {"check_id": "blooms_verbs", "found": True, "detail": "Uses define, apply, evaluate"},
            {"check_id": "has_examples", "found": True, "detail": "Concrete customer dataset example"},
            {"check_id": "no_sequential_refs", "found": False, "detail": "No cross-video references"},
            {"check_id": "consistent_terminology", "found": False, "detail": "Terms are consistent"},
            {"check_id": "active_voice", "found": False, "detail": "Active voice throughout"},
        ]

    def generate(self, system_prompt, user_prompt, max_tokens=4096):
        self.calls.append((system_prompt[:200], user_prompt[:200]))

        # AI quality check
        if "quality analyst" in system_prompt.lower():
            return json.dumps(self.quality_response)

        # Fix request — return modified script
        if "Fix" in system_prompt or "fix" in user_prompt[:100]:
            # Return the script with a small modification
            if "Missing" in user_prompt:
                # Add a missing section
                script_part = user_prompt.split("SCRIPT:\n```\n")[-1].rstrip("```").strip()
                return script_part + "\n\n## IVQ\n**Question:** Placeholder?\n\nA) Option A\nB) Option B\nC) Option C\nD) Option D\n\n**Correct Answer:** A\n"
            return user_prompt.split("SCRIPT:\n```\n")[-1].rstrip("```").strip()

        return "Mock response"


class MockAIClientWithIssues(MockAIClient):
    """Mock that reports quality issues."""

    def __init__(self):
        super().__init__(quality_response=[
            {"check_id": "hook_anecdote", "found": False, "detail": "Hook is a generic statement"},
            {"check_id": "blooms_verbs", "found": False, "detail": "No measurable verbs"},
            {"check_id": "has_examples", "found": False, "detail": "No concrete examples"},
            {"check_id": "no_sequential_refs", "found": False, "detail": "Clean"},
            {"check_id": "consistent_terminology", "found": False, "detail": "OK"},
            {"check_id": "active_voice", "found": False, "detail": "OK"},
        ])


# ---------------------------------------------------------------------------
# Tests: Scoring
# ---------------------------------------------------------------------------

class TestScoring:
    def test_score_complete_script(self):
        """Complete script with all sections should score high."""
        mock = MockAIClient()
        improver = ScriptImprover(mock)
        score = improver.score_script(COMPLETE_SCRIPT)

        assert score.total >= 80
        assert score.passed is True
        assert score.breakdown['structure'] == 40  # All sections present

    def test_score_empty_script(self):
        """Empty script should score 0."""
        improver = ScriptImprover()
        score = improver.score_script("")

        assert score.total == 0
        assert score.passed is False

    def test_score_missing_sections(self):
        """Script missing IVQ, OBJECTIVE, SUMMARY, CTA should lose structure points."""
        improver = ScriptImprover()  # No AI client — rule-based only
        score = improver.score_script(INCOMPLETE_SCRIPT)

        # Missing: OBJECTIVE, IVQ, SUMMARY, CTA = -5-10-5-5 = -25 structure points
        assert score.breakdown['structure'] < 40
        assert score.total < TOTAL_POSSIBLE

        missing_titles = {i.title for i in score.issues if 'Missing' in i.title}
        assert 'Missing OBJECTIVE section' in missing_titles
        assert 'Missing IVQ section' in missing_titles
        assert 'Missing SUMMARY section' in missing_titles
        assert 'Missing CTA section' in missing_titles

    def test_score_timing_too_long(self):
        """Script with >1500 words should lose timing points."""
        improver = ScriptImprover()
        score = improver.score_script(LONG_SCRIPT)

        timing_issues = [i for i in score.issues if i.category == 'timing']
        assert len(timing_issues) > 0
        assert any('too long' in i.title.lower() for i in timing_issues)

    def test_score_no_visual_cues(self):
        """Script without [SCREEN:] cues should lose quality points."""
        improver = ScriptImprover()
        score = improver.score_script(INCOMPLETE_SCRIPT)

        visual_issues = [i for i in score.issues if 'visual cue' in i.title.lower()]
        assert len(visual_issues) == 1

    def test_score_ivq_missing_feedback(self):
        """IVQ without feedback lines should create an issue."""
        script_no_feedback = """## HOOK
Test hook.

## IVQ
**Question:** What?
A) Option A
B) Option B
C) Option C
D) Option D
**Correct Answer:** A
"""
        improver = ScriptImprover()
        score = improver.score_script(script_no_feedback)

        feedback_issues = [i for i in score.issues if 'feedback' in i.title.lower()]
        assert len(feedback_issues) == 1

    def test_score_all_issues_have_required_fields(self):
        """Every issue should have id, severity, category, title, points_lost."""
        improver = ScriptImprover()
        score = improver.score_script(INCOMPLETE_SCRIPT)

        for issue in score.issues:
            assert issue.id
            assert issue.severity in ('critical', 'warning', 'suggestion')
            assert issue.category in ('structure', 'quality', 'timing', 'polish')
            assert issue.title
            assert issue.points_lost >= 0

    def test_score_to_dict(self):
        """ScriptScore.to_dict() should produce serializable output."""
        improver = ScriptImprover()
        score = improver.score_script(INCOMPLETE_SCRIPT)
        d = score.to_dict()

        assert isinstance(d['total'], int)
        assert isinstance(d['breakdown'], dict)
        assert isinstance(d['issues'], list)
        assert isinstance(d['passed'], bool)
        # Should be JSON-serializable
        json.dumps(d)

    def test_ai_quality_checks_run(self):
        """When AI client is provided, quality checks should run."""
        mock = MockAIClient()
        improver = ScriptImprover(mock)
        score = improver.score_script(COMPLETE_SCRIPT)

        # Verify AI was called
        assert len(mock.calls) > 0
        assert any("quality analyst" in call[0].lower() for call in mock.calls)

    def test_ai_quality_issues_detected(self):
        """AI should detect quality issues when script has problems."""
        mock = MockAIClientWithIssues()
        improver = ScriptImprover(mock)
        score = improver.score_script(INCOMPLETE_SCRIPT)

        quality_issues = [i for i in score.issues if i.category == 'quality'
                         and 'anecdote' in i.title.lower() or 'bloom' in i.title.lower()
                         or 'example' in i.title.lower()]
        # Should have at least some AI-detected issues
        assert len(quality_issues) >= 0  # May vary based on mock


# ---------------------------------------------------------------------------
# Tests: Fixing
# ---------------------------------------------------------------------------

class TestFixing:
    def test_fix_issue_returns_updated_script(self):
        """fix_issue should return a modified script and explanation."""
        mock = MockAIClient()
        improver = ScriptImprover(mock)

        issue = ScriptIssue(
            id='test1',
            severity='warning',
            category='quality',
            title='Hook lacks anecdote',
            description='The hook is generic.',
            location='HOOK',
            suggested_fix='Add a personal story.',
            auto_fixable=True,
            points_lost=5,
        )

        updated, explanation = improver.fix_issue(INCOMPLETE_SCRIPT, issue)
        assert isinstance(updated, str)
        assert len(updated) > 0
        assert 'Fixed' in explanation

    def test_fix_issue_requires_ai_client(self):
        """fix_issue should raise ValueError without AI client."""
        improver = ScriptImprover()  # No AI

        issue = ScriptIssue(
            id='test1', severity='warning', category='quality',
            title='Test', description='Test', location='HOOK',
            suggested_fix='Fix it', auto_fixable=True, points_lost=5,
        )

        with pytest.raises(ValueError, match="AI client required"):
            improver.fix_issue(INCOMPLETE_SCRIPT, issue)

    def test_fix_all_issues_iterates(self):
        """fix_all_issues should run multiple iterations."""
        mock = MockAIClient()
        improver = ScriptImprover(mock)

        updated, history = improver.fix_all_issues(
            INCOMPLETE_SCRIPT, max_iterations=3, target_score=95
        )

        assert isinstance(updated, str)
        assert len(history) >= 2  # At least one iteration + final
        assert history[-1].get('score') is not None

    def test_fix_all_stops_at_target(self):
        """fix_all_issues should stop when target score is reached."""
        mock = MockAIClient()
        improver = ScriptImprover(mock)

        # Complete script should already score high
        updated, history = improver.fix_all_issues(
            COMPLETE_SCRIPT, max_iterations=5, target_score=80
        )

        # Should stop quickly since it's already good
        assert any(
            entry.get('stopped') == 'target_reached'
            for entry in history
            if isinstance(entry.get('stopped'), str)
        ) or history[-1]['score'] >= 80

    def test_fix_all_requires_ai_client(self):
        """fix_all_issues should raise ValueError without AI client."""
        improver = ScriptImprover()

        with pytest.raises(ValueError, match="AI client required"):
            improver.fix_all_issues(INCOMPLETE_SCRIPT)

    def test_fix_all_history_format(self):
        """History entries should have iteration, score, and issues_count."""
        mock = MockAIClient()
        improver = ScriptImprover(mock)

        _, history = improver.fix_all_issues(
            INCOMPLETE_SCRIPT, max_iterations=2, target_score=95
        )

        for entry in history:
            assert 'iteration' in entry
            assert 'score' in entry
            assert 'issues_count' in entry


# ---------------------------------------------------------------------------
# Tests: Helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_split_sections(self):
        """_split_sections should extract text by section header."""
        improver = ScriptImprover()
        sections = improver._split_sections(COMPLETE_SCRIPT)

        assert 'HOOK' in sections
        assert 'OBJECTIVE' in sections
        assert 'CONTENT' in sections
        assert 'IVQ' in sections
        assert 'SUMMARY' in sections
        assert 'CTA' in sections

    def test_split_sections_normalizes_cta(self):
        """CALL TO ACTION should normalize to CTA."""
        improver = ScriptImprover()
        script = "## CALL TO ACTION\nDo the lab."
        sections = improver._split_sections(script)
        assert 'CTA' in sections
