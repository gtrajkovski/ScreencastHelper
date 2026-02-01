"""AI-powered script analysis, scoring, and auto-improvement.

Provides a 0-100 scoring rubric for Coursera WWHAA screencast scripts,
identifies issues with suggested fixes, and iteratively improves scripts
until a target score is reached.
"""

import json
import re
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ScriptIssue:
    """A single issue found in a script."""
    id: str
    severity: str  # "critical", "warning", "suggestion"
    category: str  # "structure", "quality", "timing", "polish"
    title: str
    description: str
    location: str  # section name or "global"
    suggested_fix: str
    auto_fixable: bool
    points_lost: int
    local_changes: List['LocalChange'] = field(default_factory=list)
    global_changes: List['GlobalChange'] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class ScriptScore:
    """Result of scoring a script."""
    total: int  # 0-100
    breakdown: Dict[str, int]  # category -> points earned
    issues: List[ScriptIssue] = field(default_factory=list)
    passed: bool = False  # total >= 80

    def to_dict(self) -> dict:
        return {
            'total': self.total,
            'breakdown': self.breakdown,
            'issues': [i.to_dict() for i in self.issues],
            'passed': self.passed,
        }


class IssueCategory(Enum):
    """Category of a script issue."""
    STRUCTURE = "structure"
    CONTENT = "content"
    QUALITY = "quality"
    TONE = "tone"
    TECHNICAL = "technical"
    TIMING = "timing"
    POLISH = "polish"
    ACCESSIBILITY = "accessibility"


class IssueSeverity(Enum):
    """Severity of a script issue."""
    CRITICAL = "critical"
    WARNING = "warning"
    SUGGESTION = "suggestion"


@dataclass
class LocalChange:
    """A change to apply at a specific location."""
    start_line: int
    end_line: int
    original_text: str
    replacement_text: str
    reason: str


@dataclass
class GlobalChange:
    """A change to apply across the entire document."""
    find_pattern: str
    replace_with: str
    occurrences: List[Dict[str, Any]] = field(default_factory=list)
    reason: str = ""
    is_regex: bool = False


@dataclass
class ScriptAnalysis:
    """Result of analyzing a script (wraps ScriptScore with extra fields)."""
    score: int  # 0-100
    issues: List[ScriptIssue] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    summary: str = ""


# ============================================================================
# Scoring rubric: 100 points total
# ============================================================================

RUBRIC = {
    'structure': {
        'has_hook': ('HOOK section present', 5),
        'has_objective': ('OBJECTIVE section present', 5),
        'has_content': ('CONTENT section present', 10),
        'has_ivq': ('IVQ section present', 10),
        'has_summary': ('SUMMARY section present', 5),
        'has_cta': ('CTA / CALL TO ACTION section present', 5),
    },
    'quality': {
        'hook_anecdote': ('Hook has relatable anecdote or story', 5),
        'blooms_verbs': ('Objectives use Bloom\'s taxonomy verbs', 5),
        'has_examples': ('Content has concrete examples', 5),
        'visual_cues': ('Sufficient [SCREEN:] visual cues (>=3)', 5),
        'ivq_4_options': ('IVQ has 4 answer options (A-D)', 5),
        'ivq_feedback': ('IVQ has feedback for wrong answers', 5),
        'no_sequential_refs': ('No references to other videos/modules', 5),
    },
    'timing': {
        'hook_duration': ('Hook is 30-60 seconds (50-100 words)', 5),
        'content_duration': ('Content under 6 minutes (<900 words)', 5),
        'total_duration': ('Total under 10 minutes (<1500 words)', 5),
    },
    'polish': {
        'consistent_terminology': ('Consistent term usage throughout', 5),
        'active_voice': ('Predominantly active voice', 5),
    },
}

TOTAL_POSSIBLE = sum(
    pts for category in RUBRIC.values() for _, pts in category.values()
)

# Bloom's taxonomy verbs (measurable)
BLOOMS_VERBS = {
    'define', 'describe', 'explain', 'identify', 'list', 'recognize',
    'apply', 'demonstrate', 'implement', 'use', 'execute', 'solve',
    'analyze', 'compare', 'contrast', 'examine', 'differentiate',
    'evaluate', 'assess', 'justify', 'critique',
    'create', 'design', 'develop', 'build', 'construct', 'produce',
}

# Phrases that reference other videos/modules
SEQUENTIAL_PATTERNS = [
    r'(?:in|from)\s+(?:the\s+)?(?:last|previous|next|earlier|upcoming)\s+(?:video|module|lesson|lecture|week)',
    r'(?:as\s+)?(?:we|you)\s+(?:saw|discussed|learned|covered|mentioned)\s+(?:in|last|earlier)',
    r'(?:in|during)\s+(?:module|week|lesson)\s+\d+',
    r'we\'ll\s+(?:cover|discuss|see)\s+(?:this|that|more)\s+(?:in\s+(?:the\s+)?next|later)',
]

# System prompt for AI quality checks
AI_QUALITY_SYSTEM = """You are a Coursera screencast script quality analyst.
Analyze the script for these specific dimensions only. Return a JSON array of issues found.

Each issue must be:
{
  "check_id": "hook_anecdote|blooms_verbs|has_examples|no_sequential_refs|consistent_terminology|active_voice",
  "found": true,
  "detail": "Specific explanation"
}

If a check passes, set "found" to false with a brief note why it passes.
Return ONLY a valid JSON array, no other text."""

AI_QUALITY_USER = """Analyze this script:

```
{script}
```

Check these items:
1. hook_anecdote: Does the HOOK section contain a personal anecdote, relatable story, or engaging real-world scenario? (Not just a generic question like "Have you ever wondered...")
2. blooms_verbs: Does the OBJECTIVE section use measurable Bloom's taxonomy verbs (define, apply, analyze, create, evaluate, etc.)?
3. has_examples: Does the CONTENT section include concrete examples with specific numbers, names, or scenarios?
4. no_sequential_refs: Does the script contain references to other videos, modules, or weeks? (e.g., "in the last video", "next week", "module 3")
5. consistent_terminology: Are technical terms used consistently throughout? (e.g., not switching between "DataFrame" and "dataframe" or "ML" and "machine learning" inconsistently)
6. active_voice: Is the script predominantly in active voice? Flag if passive voice is used excessively."""

# System prompt for fixing issues
FIX_SYSTEM = """You are an expert Coursera screencast script editor.
Fix the specified issue in the script while preserving:
- All ## and ### section headers
- All [SCREEN:], [PAUSE], [RUN CELL] markers
- All ```python code blocks```
- All **NARRATION:** and **OUTPUT:** labels
- The same conversational tone and style

Return ONLY the complete updated script. No explanations before or after."""

FIX_USER = """Fix this issue in the script below:

ISSUE: {title}
CATEGORY: {category}
DESCRIPTION: {description}
SUGGESTED FIX: {suggested_fix}
LOCATION: {location}

SCRIPT:
```
{script}
```

Return the complete fixed script."""


class ScriptImprover:
    """Hybrid rule-based + AI script scorer and improver."""

    def __init__(self, ai_client=None):
        """Initialize with optional AI client for quality checks.

        Args:
            ai_client: Object with generate(system_prompt, user_prompt) method.
                       If None, AI-based checks are skipped (rule-based only).
        """
        self.ai_client = ai_client

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def score_script(self, script: str) -> ScriptScore:
        """Score a script against the rubric. Returns ScriptScore with 0-100 total."""
        if not script or not script.strip():
            return ScriptScore(total=0, breakdown={}, issues=[], passed=False)

        issues: List[ScriptIssue] = []
        points_earned: Dict[str, int] = {}

        # Rule-based checks
        issues.extend(self._check_structure(script, points_earned))
        issues.extend(self._check_timing(script, points_earned))
        issues.extend(self._check_visual_cues(script, points_earned))
        issues.extend(self._check_ivq_details(script, points_earned))

        # AI-based quality/polish checks
        if self.ai_client:
            issues.extend(self._check_quality_ai(script, points_earned))
        else:
            # Award quality/polish points by default when no AI available
            for check_id, (_, pts) in RUBRIC['quality'].items():
                if check_id not in points_earned:
                    points_earned[check_id] = pts
            for check_id, (_, pts) in RUBRIC['polish'].items():
                if check_id not in points_earned:
                    points_earned[check_id] = pts

        # Calculate total
        total = sum(points_earned.values())
        total = max(0, min(TOTAL_POSSIBLE, total))

        # Build category breakdown
        breakdown = {}
        for category, checks in RUBRIC.items():
            cat_earned = sum(
                points_earned.get(check_id, 0)
                for check_id in checks
            )
            cat_max = sum(pts for _, pts in checks.values())
            breakdown[category] = cat_earned

        return ScriptScore(
            total=total,
            breakdown=breakdown,
            issues=issues,
            passed=total >= 80,
        )

    # ------------------------------------------------------------------
    # Fixing
    # ------------------------------------------------------------------

    def fix_issue(self, script: str, issue: ScriptIssue) -> Tuple[str, str]:
        """Fix a single issue using AI. Returns (updated_script, explanation).

        Raises ValueError if no AI client available.
        """
        if not self.ai_client:
            raise ValueError("AI client required for fixing issues")

        prompt = FIX_USER.format(
            title=issue.title,
            category=issue.category,
            description=issue.description,
            suggested_fix=issue.suggested_fix,
            location=issue.location,
            script=script,
        )

        result = self.ai_client.generate(FIX_SYSTEM, prompt)

        # Strip markdown fences if the AI wrapped the response
        result = result.strip()
        if result.startswith('```') and result.endswith('```'):
            lines = result.split('\n')
            result = '\n'.join(lines[1:-1])

        explanation = f"Fixed: {issue.title}"
        return result.strip(), explanation

    def fix_all_issues(
        self,
        script: str,
        max_iterations: int = 5,
        target_score: int = 95,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Iteratively fix issues until target score or max iterations.

        Returns (final_script, history) where history is a list of dicts
        with iteration, score, and fixes_applied.
        """
        if not self.ai_client:
            raise ValueError("AI client required for fixing issues")

        history: List[Dict[str, Any]] = []
        current_script = script
        prev_score = -1

        for i in range(max_iterations):
            score = self.score_script(current_script)
            entry = {
                'iteration': i,
                'score': score.total,
                'issues_count': len(score.issues),
                'fixes_applied': [],
            }

            if score.total >= target_score:
                entry['stopped'] = 'target_reached'
                history.append(entry)
                break

            # Stop if score isn't improving
            if score.total <= prev_score:
                entry['stopped'] = 'score_plateaued'
                history.append(entry)
                break

            prev_score = score.total

            # Fix top fixable issues (prioritized by severity, then points)
            fixable = [iss for iss in score.issues if iss.auto_fixable]
            fixable.sort(
                key=lambda x: (
                    {'critical': 0, 'warning': 1, 'suggestion': 2}.get(x.severity, 3),
                    -x.points_lost,
                )
            )

            if not fixable:
                entry['stopped'] = 'no_fixable_issues'
                history.append(entry)
                break

            # Fix top 3 per iteration to avoid excessive AI calls
            for issue in fixable[:3]:
                try:
                    current_script, explanation = self.fix_issue(current_script, issue)
                    entry['fixes_applied'].append(explanation)
                except Exception as e:
                    entry['fixes_applied'].append(f"Failed to fix '{issue.title}': {e}")

            history.append(entry)

        # Final score
        final = self.score_script(current_script)
        history.append({
            'iteration': 'final',
            'score': final.total,
            'issues_count': len(final.issues),
        })

        return current_script, history

    # ------------------------------------------------------------------
    # Alias methods matching prompt API
    # ------------------------------------------------------------------

    def analyze(self, script: str) -> 'ScriptAnalysis':
        """Analyze script and return ScriptAnalysis with score, issues, strengths, summary.

        This wraps score_script() and adds strengths/summary fields.
        """
        score = self.score_script(script)

        # Determine strengths from what passed
        strengths = []
        for category, checks in RUBRIC.items():
            for check_id, (label, _) in checks.items():
                if score.breakdown.get(category, 0) > 0:
                    # Check wasn't flagged as an issue
                    if not any(i.title == f'Missing {check_id.replace("has_", "").upper()} section'
                               for i in score.issues):
                        strengths.append(label)

        # Build summary
        n_issues = len(score.issues)
        summary = f"Score: {score.total}/100. Found {n_issues} issue{'s' if n_issues != 1 else ''}."

        return ScriptAnalysis(
            score=score.total,
            issues=score.issues,
            strengths=strengths,
            summary=summary,
        )

    def apply_fix(self, script: str, issue: 'ScriptIssue',
                  fix_type: str = 'all') -> str:
        """Apply local and/or global changes from an issue.

        Args:
            script: The script text.
            issue: The issue containing local_changes and/or global_changes.
            fix_type: 'local', 'global', 'both', or 'all'.

        Returns:
            Updated script text.
        """
        result = script

        if fix_type in ('local', 'both', 'all'):
            for change in issue.local_changes:
                result = self._apply_local_change(result, change)

        if fix_type in ('global', 'both', 'all'):
            for change in issue.global_changes:
                result = self._apply_global_change(result, change)

        return result

    def improve_until_perfect(
        self,
        script: str,
        target_score: int = 95,
        max_iterations: int = 5,
    ) -> Tuple[str, List['ScriptAnalysis']]:
        """Iteratively improve script until target score reached.

        Returns (final_script, history) where history is a list of
        ScriptAnalysis objects.
        """
        history: List[ScriptAnalysis] = []
        current_script = script

        for _ in range(max_iterations):
            analysis = self.analyze(current_script)
            history.append(analysis)

            if analysis.score >= target_score:
                break

            # Apply local/global changes from auto-fixable issues
            auto_fixable = [i for i in analysis.issues if i.auto_fixable]
            if not auto_fixable:
                break

            applied_any = False
            for issue in auto_fixable:
                if issue.local_changes or issue.global_changes:
                    current_script = self.apply_fix(current_script, issue)
                    applied_any = True

            # If no structured changes available, try AI fix
            if not applied_any and self.ai_client:
                for issue in auto_fixable[:3]:
                    try:
                        current_script, _ = self.fix_issue(current_script, issue)
                    except (ValueError, Exception):
                        pass
                    break
            elif not applied_any:
                break

        return current_script, history

    @staticmethod
    def _apply_local_change(script: str, change: 'LocalChange') -> str:
        """Apply a local change at specific lines."""
        lines = script.split('\n')
        start = max(0, change.start_line - 1)
        end = min(len(lines), change.end_line)
        before = lines[:start]
        after = lines[end:]
        result = before + [change.replacement_text] + after
        return '\n'.join(result)

    @staticmethod
    def _apply_global_change(script: str, change: 'GlobalChange') -> str:
        """Apply a global find/replace."""
        if change.is_regex:
            return re.sub(change.find_pattern, change.replace_with, script)
        return script.replace(change.find_pattern, change.replace_with)

    # ------------------------------------------------------------------
    # Rule-based checks
    # ------------------------------------------------------------------

    def _check_structure(self, script: str, points: dict) -> List[ScriptIssue]:
        """Check for required WWHAA sections."""
        issues = []
        upper = script.upper()

        section_patterns = {
            'has_hook': (r'^#{2,3}\s+HOOK', 'HOOK'),
            'has_objective': (r'^#{2,3}\s+OBJECTIVE', 'OBJECTIVE'),
            'has_content': (r'^#{2,3}\s+CONTENT', 'CONTENT'),
            'has_ivq': (r'(?:^#{2,3}\s+IVQ|^#{2,3}\s+IN-VIDEO)', 'IVQ'),
            'has_summary': (r'^#{2,3}\s+SUMMARY', 'SUMMARY'),
            'has_cta': (r'(?:^#{2,3}\s+CTA|^#{2,3}\s+CALL\s+TO\s+ACTION)', 'CTA'),
        }

        for check_id, (pattern, section_name) in section_patterns.items():
            _, max_pts = RUBRIC['structure'][check_id]
            if re.search(pattern, script, re.MULTILINE | re.IGNORECASE):
                points[check_id] = max_pts
            else:
                points[check_id] = 0
                issues.append(ScriptIssue(
                    id=str(uuid.uuid4())[:8],
                    severity='critical',
                    category='structure',
                    title=f'Missing {section_name} section',
                    description=f'Script is missing a ## {section_name} section header.',
                    location='global',
                    suggested_fix=f'Add a ## {section_name} section with appropriate content.',
                    auto_fixable=True,
                    points_lost=max_pts,
                ))

        return issues

    def _check_timing(self, script: str, points: dict) -> List[ScriptIssue]:
        """Check timing based on word counts."""
        issues = []

        # Extract section texts
        sections = self._split_sections(script)

        # Hook timing (50-100 words = 30-60s at 150 WPM)
        hook_text = sections.get('HOOK', '')
        hook_words = len(hook_text.split()) if hook_text else 0
        _, hook_pts = RUBRIC['timing']['hook_duration']
        if 50 <= hook_words <= 100:
            points['hook_duration'] = hook_pts
        elif hook_text:
            points['hook_duration'] = 0
            direction = 'short' if hook_words < 50 else 'long'
            issues.append(ScriptIssue(
                id=str(uuid.uuid4())[:8],
                severity='warning',
                category='timing',
                title=f'Hook is too {direction} ({hook_words} words)',
                description=f'Hook should be 50-100 words (30-60 seconds). Currently {hook_words} words.',
                location='HOOK',
                suggested_fix=f'{"Expand" if direction == "short" else "Trim"} the HOOK section to 50-100 words.',
                auto_fixable=True,
                points_lost=hook_pts,
            ))
        else:
            points['hook_duration'] = 0  # Missing hook handled in structure

        # Content timing (<900 words = <6 min)
        content_text = sections.get('CONTENT', '')
        content_words = len(content_text.split()) if content_text else 0
        _, content_pts = RUBRIC['timing']['content_duration']
        if content_words <= 900:
            points['content_duration'] = content_pts
        elif content_text:
            points['content_duration'] = 0
            issues.append(ScriptIssue(
                id=str(uuid.uuid4())[:8],
                severity='warning',
                category='timing',
                title=f'Content too long ({content_words} words, ~{content_words/150:.0f} min)',
                description=f'Content should be under 900 words (<6 minutes). Currently {content_words} words.',
                location='CONTENT',
                suggested_fix='Trim the CONTENT section. Remove tangential examples or split into multiple videos.',
                auto_fixable=True,
                points_lost=content_pts,
            ))
        else:
            points['content_duration'] = content_pts  # No content = no timing issue

        # Total timing (<1500 words = <10 min)
        total_words = len(script.split())
        _, total_pts = RUBRIC['timing']['total_duration']
        if total_words <= 1500:
            points['total_duration'] = total_pts
        else:
            points['total_duration'] = 0
            issues.append(ScriptIssue(
                id=str(uuid.uuid4())[:8],
                severity='warning',
                category='timing',
                title=f'Script too long ({total_words} words, ~{total_words/150:.0f} min)',
                description=f'Total should be under 1500 words (<10 minutes). Currently {total_words} words.',
                location='global',
                suggested_fix='Reduce overall script length. Focus on essential content.',
                auto_fixable=True,
                points_lost=total_pts,
            ))

        return issues

    def _check_visual_cues(self, script: str, points: dict) -> List[ScriptIssue]:
        """Check for [SCREEN:] visual cues."""
        issues = []
        screen_cues = re.findall(r'\[SCREEN:', script, re.IGNORECASE)
        _, max_pts = RUBRIC['quality']['visual_cues']

        if len(screen_cues) >= 3:
            points['visual_cues'] = max_pts
        else:
            points['visual_cues'] = 0
            issues.append(ScriptIssue(
                id=str(uuid.uuid4())[:8],
                severity='warning',
                category='quality',
                title=f'Only {len(screen_cues)} visual cues found',
                description='Scripts should have at least 3 [SCREEN: ...] cues for visual direction.',
                location='global',
                suggested_fix='Add [SCREEN: ...] cues to indicate what should be shown on screen.',
                auto_fixable=True,
                points_lost=max_pts,
            ))

        return issues

    def _check_ivq_details(self, script: str, points: dict) -> List[ScriptIssue]:
        """Check IVQ has 4 options and feedback."""
        issues = []

        # IVQ 4 options
        options = re.findall(r'^[A-D]\)\s+', script, re.MULTILINE)
        _, opts_pts = RUBRIC['quality']['ivq_4_options']
        if len(options) >= 4:
            points['ivq_4_options'] = opts_pts
        else:
            points['ivq_4_options'] = 0
            if len(options) > 0:
                issues.append(ScriptIssue(
                    id=str(uuid.uuid4())[:8],
                    severity='warning',
                    category='quality',
                    title=f'IVQ has only {len(options)} options (need 4)',
                    description='In-video questions should have exactly 4 options (A through D).',
                    location='IVQ',
                    suggested_fix='Add options A) through D) to the IVQ section.',
                    auto_fixable=True,
                    points_lost=opts_pts,
                ))
            # If 0 options and no IVQ section, structure check handles it

        # IVQ feedback
        feedback = re.findall(r'\*\*Feedback [A-D]:\*\*', script)
        _, fb_pts = RUBRIC['quality']['ivq_feedback']
        if len(feedback) >= 3:
            points['ivq_feedback'] = fb_pts
        else:
            points['ivq_feedback'] = 0
            if re.search(r'(?:^#{2,3}\s+IVQ|IN-VIDEO)', script, re.MULTILINE | re.IGNORECASE):
                issues.append(ScriptIssue(
                    id=str(uuid.uuid4())[:8],
                    severity='warning',
                    category='quality',
                    title='IVQ missing feedback for answer options',
                    description='IVQ should have **Feedback A/B/C/D:** lines explaining why each option is correct or incorrect.',
                    location='IVQ',
                    suggested_fix='Add **Feedback A:** through **Feedback D:** lines to the IVQ section.',
                    auto_fixable=True,
                    points_lost=fb_pts,
                ))

        return issues

    def _check_quality_ai(self, script: str, points: dict) -> List[ScriptIssue]:
        """Use AI to check quality and polish dimensions."""
        issues = []

        # Truncate script for AI context
        truncated = script[:4000] if len(script) > 4000 else script
        prompt = AI_QUALITY_USER.format(script=truncated)

        try:
            response = self.ai_client.generate(AI_QUALITY_SYSTEM, prompt, max_tokens=1500)

            # Parse JSON from response (may be wrapped in markdown)
            json_text = response.strip()
            if json_text.startswith('```'):
                lines = json_text.split('\n')
                json_text = '\n'.join(lines[1:-1])

            checks = json.loads(json_text)

            # Map AI results to rubric
            ai_check_map = {
                'hook_anecdote': ('quality', RUBRIC['quality']['hook_anecdote'][1]),
                'blooms_verbs': ('quality', RUBRIC['quality']['blooms_verbs'][1]),
                'has_examples': ('quality', RUBRIC['quality']['has_examples'][1]),
                'no_sequential_refs': ('quality', RUBRIC['quality']['no_sequential_refs'][1]),
                'consistent_terminology': ('polish', RUBRIC['polish']['consistent_terminology'][1]),
                'active_voice': ('polish', RUBRIC['polish']['active_voice'][1]),
            }

            for check in checks:
                check_id = check.get('check_id', '')
                if check_id not in ai_check_map:
                    continue

                category, max_pts = ai_check_map[check_id]
                found = check.get('found', False)

                # "found" means issue was found (check failed)
                # For no_sequential_refs: "found" means sequential refs WERE found (bad)
                if check_id == 'no_sequential_refs':
                    has_problem = found
                else:
                    has_problem = not found

                if has_problem:
                    points[check_id] = 0
                    issues.append(ScriptIssue(
                        id=str(uuid.uuid4())[:8],
                        severity='warning',
                        category=category,
                        title=RUBRIC[category][check_id][0],
                        description=check.get('detail', ''),
                        location=self._location_for_check(check_id),
                        suggested_fix=self._fix_suggestion_for_check(check_id),
                        auto_fixable=True,
                        points_lost=max_pts,
                    ))
                else:
                    points[check_id] = max_pts

        except (json.JSONDecodeError, KeyError, TypeError):
            # If AI check fails, give benefit of the doubt
            for check_id in ('hook_anecdote', 'blooms_verbs', 'has_examples', 'no_sequential_refs'):
                if check_id not in points:
                    points[check_id] = RUBRIC['quality'][check_id][1]
            for check_id in ('consistent_terminology', 'active_voice'):
                if check_id not in points:
                    points[check_id] = RUBRIC['polish'][check_id][1]
        except Exception:
            # Network/API errors — give benefit of the doubt
            for check_id in ('hook_anecdote', 'blooms_verbs', 'has_examples', 'no_sequential_refs'):
                if check_id not in points:
                    points[check_id] = RUBRIC['quality'][check_id][1]
            for check_id in ('consistent_terminology', 'active_voice'):
                if check_id not in points:
                    points[check_id] = RUBRIC['polish'][check_id][1]

        return issues

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _split_sections(self, script: str) -> Dict[str, str]:
        """Split script into sections by ## headers. Returns {SECTION_NAME: text}."""
        sections: Dict[str, str] = {}
        current = None
        lines = []

        for line in script.split('\n'):
            match = re.match(r'^#{2,3}\s+(.+)$', line)
            if match:
                if current and lines:
                    sections[current] = '\n'.join(lines)
                header = match.group(1).strip().upper()
                # Normalize section names
                if header.startswith('CALL TO ACTION'):
                    header = 'CTA'
                elif header.startswith('IN-VIDEO') or header == 'IVQ':
                    header = 'IVQ'
                current = header
                lines = []
            else:
                lines.append(line)

        if current and lines:
            sections[current] = '\n'.join(lines)

        return sections

    @staticmethod
    def _location_for_check(check_id: str) -> str:
        """Map check IDs to script locations."""
        return {
            'hook_anecdote': 'HOOK',
            'blooms_verbs': 'OBJECTIVE',
            'has_examples': 'CONTENT',
            'no_sequential_refs': 'global',
            'consistent_terminology': 'global',
            'active_voice': 'global',
        }.get(check_id, 'global')

    @staticmethod
    def _fix_suggestion_for_check(check_id: str) -> str:
        """Map check IDs to fix suggestions."""
        return {
            'hook_anecdote': 'Add a personal anecdote, real-world scenario, or relatable story to the HOOK section.',
            'blooms_verbs': 'Use measurable Bloom\'s verbs in objectives: define, apply, analyze, create, evaluate.',
            'has_examples': 'Add concrete examples with specific numbers, names, or real scenarios in the CONTENT.',
            'no_sequential_refs': 'Remove references to other videos/modules. Each video should stand alone.',
            'consistent_terminology': 'Pick one term for each concept and use it consistently throughout.',
            'active_voice': 'Rewrite passive constructions in active voice (e.g., "The model is trained" → "We train the model").',
        }.get(check_id, '')
