#!/usr/bin/env python3
"""ScreenCast Studio v2.0 - AI-Powered Screencast Production."""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, Static, Button, Input, TextArea,
    TabbedContent, TabPane, Label, Rule, Select, Collapsible,
    RadioSet, RadioButton, DataTable
)
from textual.binding import Binding
from textual import work
from pathlib import Path
import subprocess
import json

from src.ai.actions import AIActions
from src.ai.client import AIClient
from src.ai.prompts import CHAT_ASSISTANT
from src.config import Config, Environment, AudienceLevel, DemoType
from src.environments.recommender import EnvironmentRecommender
from src.environments.jupyter import JupyterEnvironment
from src.environments.terminal import TerminalEnvironment
from src.data.generator import DataSchemaAnalyzer, FlexibleDataGenerator


class InputPanel(Container):
    """Left panel for input fields."""

    def compose(self) -> ComposeResult:
        yield Label("[bold cyan]INPUT[/bold cyan]", classes="panel-title")
        yield Rule()

        yield Label("Topic:", classes="field-label")
        yield Input(placeholder="e.g., Identifying Code Bottlenecks", id="topic-input")

        yield Label("Duration (minutes):", classes="field-label")
        yield Input(value="7", id="duration-input", type="integer")

        yield Label("Audience Level:", classes="field-label")
        yield Select(
            [(level.value.title(), level.value) for level in AudienceLevel],
            value=AudienceLevel.INTERMEDIATE.value,
            id="audience-select"
        )

        yield Label("Demo Type:", classes="field-label")
        yield Select(
            [("Auto-detect", "auto")] + [(dt.value.replace("_", " ").title(), dt.value) for dt in DemoType],
            value="auto",
            id="demo-type-select"
        )

        yield Label("Bullet Points:", classes="field-label")
        yield TextArea(id="bullets-input")

        yield Label("Demo Requirements:", classes="field-label")
        yield TextArea(id="demo-req-input")


class EnvironmentPanel(Container):
    """Environment selection and configuration panel."""

    def compose(self) -> ComposeResult:
        yield Label("[bold green]ENVIRONMENT[/bold green]", classes="panel-title")
        yield Rule()

        yield Label("Target Environment:", classes="field-label")
        with RadioSet(id="env-radio"):
            yield RadioButton("Jupyter Notebook", value=True, id="env-jupyter")
            yield RadioButton("Terminal/Bash", id="env-terminal")
            yield RadioButton("VS Code Project", id="env-vscode")
            yield RadioButton("IPython REPL", id="env-ipython")
            yield RadioButton("PyCharm Project", id="env-pycharm")

        yield Button("Get AI Recommendation", id="recommend-env-btn", variant="default")
        yield Static(id="env-recommendation", classes="recommendation-box")


class DataPanel(Container):
    """Data generation panel with preview."""

    def compose(self) -> ComposeResult:
        yield Label("[bold yellow]DATA GENERATION[/bold yellow]", classes="panel-title")
        yield Rule()

        with Collapsible(title="Dataset Configuration", collapsed=False):
            yield Label("Detected Datasets:", classes="field-label")
            yield Static(id="detected-datasets", classes="data-info")

            yield Button("Analyze & Generate Data", id="analyze-data-btn", variant="primary")

        with Collapsible(title="Data Preview", collapsed=True):
            yield DataTable(id="data-preview-table")

        with Collapsible(title="Data Quality Issues", collapsed=True):
            yield Label("Inject Issues (for data quality demos):", classes="field-label")
            yield Static(
                "[dim][ ] Null values  [ ] Duplicates  [ ] Type errors  [ ] Outliers[/dim]",
                id="issue-checkboxes"
            )


class PreviewPanel(Container):
    """Right panel for output preview."""

    def compose(self) -> ComposeResult:
        yield Label("[bold blue]OUTPUT PREVIEW[/bold blue]", classes="panel-title")
        yield Rule()

        with TabbedContent():
            with TabPane("Script", id="script-tab"):
                yield ScrollableContainer(
                    Static(id="script-preview", classes="preview-content"),
                    id="script-scroll"
                )
            with TabPane("TTS", id="tts-tab"):
                yield ScrollableContainer(
                    Static(id="tts-preview", classes="preview-content"),
                    id="tts-scroll"
                )
            with TabPane("Demo", id="demo-tab"):
                yield ScrollableContainer(
                    Static(id="demo-preview", classes="preview-content"),
                    id="demo-scroll"
                )
            with TabPane("Data", id="data-tab"):
                yield ScrollableContainer(
                    Static(id="data-preview", classes="preview-content"),
                    id="data-scroll"
                )
            with TabPane("Report", id="report-tab"):
                yield ScrollableContainer(
                    Static(id="report-preview", classes="preview-content"),
                    id="report-scroll"
                )


class ChatPanel(Container):
    """AI chat interface panel."""

    def compose(self) -> ComposeResult:
        yield Label("[bold magenta]AI ASSISTANT[/bold magenta]", classes="panel-title")
        yield Rule()

        yield ScrollableContainer(
            Static(id="chat-history", classes="chat-content"),
            id="chat-scroll"
        )

        with Horizontal(id="chat-input-row"):
            yield Input(placeholder="Ask AI to modify the script, demo, or data...", id="chat-input")
            yield Button("Send", id="send-btn", variant="primary")


class ActionsPanel(Container):
    """Action buttons panel."""

    def compose(self) -> ComposeResult:
        yield Label("[bold yellow]AI ACTIONS[/bold yellow]", classes="panel-title")

        with Horizontal(classes="button-row"):
            yield Button("Generate Full Package", id="gen-package-btn", variant="success")
            yield Button("Check Alignment", id="check-align-btn", variant="default")
            yield Button("Optimize TTS", id="opt-tts-btn", variant="default")

        with Horizontal(classes="button-row"):
            yield Button("Regenerate Script", id="regen-script-btn", variant="default")
            yield Button("Generate Demo", id="gen-demo-btn", variant="default")
            yield Button("Generate Data", id="gen-data-btn", variant="default")

        with Horizontal(classes="button-row"):
            yield Button("Quality Report", id="quality-btn", variant="default")
            yield Button("Export All", id="export-btn", variant="default")
            yield Button("Run Demo", id="run-demo-btn", variant="warning")


class StatusBar(Static):
    """Status bar showing component status."""

    def __init__(self):
        super().__init__()
        self.script_ready = False
        self.tts_ready = False
        self.demo_ready = False
        self.data_ready = False
        self.env_name = "Jupyter"

    def compose(self) -> ComposeResult:
        yield Static(self._get_status_text(), id="status-text")

    def _get_status_text(self) -> str:
        s = "[green]OK[/green]" if self.script_ready else "[dim]--[/dim]"
        t = "[green]OK[/green]" if self.tts_ready else "[dim]--[/dim]"
        d = "[green]OK[/green]" if self.demo_ready else "[dim]--[/dim]"
        dt = "[green]OK[/green]" if self.data_ready else "[dim]--[/dim]"
        return f"Env: [cyan]{self.env_name}[/cyan] | Script {s} | TTS {t} | Demo {d} | Data {dt}"

    def update_status(self, script=None, tts=None, demo=None, data=None, env=None):
        if script is not None:
            self.script_ready = script
        if tts is not None:
            self.tts_ready = tts
        if demo is not None:
            self.demo_ready = demo
        if data is not None:
            self.data_ready = data
        if env is not None:
            self.env_name = env
        self.query_one("#status-text", Static).update(self._get_status_text())


class ScreenCastStudio(App):
    """Main application v2.0."""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 4;
        grid-columns: 1fr 1fr 2fr;
        grid-rows: 1fr 1fr 8 5;
    }

    InputPanel {
        row-span: 2;
        border: solid green;
        padding: 1;
        overflow-y: auto;
    }

    EnvironmentPanel {
        border: solid cyan;
        padding: 1;
        overflow-y: auto;
    }

    DataPanel {
        border: solid yellow;
        padding: 1;
        overflow-y: auto;
    }

    PreviewPanel {
        row-span: 2;
        border: solid blue;
        padding: 1;
    }

    ChatPanel {
        column-span: 3;
        border: solid magenta;
        padding: 1;
    }

    ActionsPanel {
        column-span: 3;
        border: solid yellow;
        padding: 1;
    }

    .panel-title {
        text-style: bold;
        margin-bottom: 1;
    }

    .field-label {
        margin-top: 1;
        color: $text-muted;
    }

    .preview-content {
        padding: 1;
    }

    .chat-content {
        padding: 1;
        height: auto;
    }

    .button-row {
        margin: 1 0;
        height: auto;
    }

    Button {
        margin: 0 1;
    }

    #chat-input-row {
        margin-top: 1;
        height: 3;
    }

    #chat-input {
        width: 85%;
    }

    #send-btn {
        width: 15%;
    }

    TextArea {
        height: 6;
    }

    #bullets-input {
        height: 10;
    }

    #demo-req-input {
        height: 5;
    }

    ScrollableContainer {
        height: 100%;
    }

    StatusBar {
        dock: bottom;
        height: 1;
        background: $surface;
        padding: 0 1;
    }

    .recommendation-box {
        margin-top: 1;
        padding: 1;
        background: $surface;
        border: round $primary;
    }

    .data-info {
        padding: 1;
        background: $surface;
    }

    Select {
        width: 100%;
    }

    RadioSet {
        height: auto;
        padding: 0;
    }

    Collapsible {
        margin-top: 1;
    }

    DataTable {
        height: 10;
    }
    """

    BINDINGS = [
        Binding("ctrl+g", "generate_package", "Generate Package"),
        Binding("ctrl+r", "run_demo", "Run Demo"),
        Binding("ctrl+e", "export_all", "Export"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.ai_actions = AIActions()
        self.ai_chat = AIClient()
        self.chat_history = []
        self.env_recommender = EnvironmentRecommender()
        self.data_analyzer = DataSchemaAnalyzer()
        self.data_generator = FlexibleDataGenerator()
        self.current_env = Environment.JUPYTER
        self.generated_datasets = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield InputPanel()
        yield EnvironmentPanel()
        yield PreviewPanel()
        yield DataPanel()
        yield ChatPanel()
        yield ActionsPanel()
        yield StatusBar()
        yield Footer()

    def on_mount(self) -> None:
        """Set up initial state."""
        self.title = "ScreenCast Studio v2.0"
        self.sub_title = "AI-Powered Screencast Production"
        self._load_example()

    def _load_example(self):
        """Load example bullet points."""
        example_bullets = """### HOOK
- "Your code runs... but takes 45 seconds instead of 5"
- Most developers guess wrong about what's slow
- Profiling reveals the truth

### OBJECTIVE
- Identify bottlenecks using profiling tools
- Distinguish CPU-bound vs I/O-bound problems
- Apply targeted fixes to actual slow code

### CONTENT
- What is a bottleneck? The 90/10 rule
- Common types: CPU, I/O, memory, network
- Tools: cProfile, line_profiler, py-spy
- Demo: Profile slow O(n^2) code, fix to O(n)
- Quick wins checklist

### SUMMARY
- Always profile before optimizing
- Focus on actual bottleneck
- Small changes = big speedups

### CTA
- Next: Hands-on profiling lab"""

        try:
            bullets_area = self.query_one("#bullets-input", TextArea)
            bullets_area.load_text(example_bullets)

            topic_input = self.query_one("#topic-input", Input)
            topic_input.value = "Identifying and Fixing Code Bottlenecks"

            demo_req = self.query_one("#demo-req-input", TextArea)
            demo_req.load_text("""Show:
- Slow Python code with O(n^2) nested loop
- cProfile output highlighting bottleneck
- Optimized O(n) version using dictionary
- Before/after timing comparison

Data:
- users.csv (1,000 users for demo speed)
- transactions.csv (10,000 transactions)""")
        except Exception:
            pass

    def _add_chat_message(self, role: str, content: str):
        """Add message to chat history."""
        self.chat_history.append({"role": role, "content": content})

        try:
            chat_display = self.query_one("#chat-history", Static)
            history_text = ""
            for msg in self.chat_history[-10:]:
                if msg["role"] == "user":
                    prefix = "[bold cyan]You:[/bold cyan]"
                elif msg["role"] == "assistant":
                    prefix = "[bold green]AI:[/bold green]"
                else:
                    prefix = "[bold yellow]System:[/bold yellow]"
                history_text += f"\n{prefix} {msg['content']}\n"

            chat_display.update(history_text)
        except Exception:
            pass

    def _update_preview(self, content: str, tab: str = "script"):
        """Update preview panel."""
        try:
            preview_id = f"#{tab}-preview"
            preview = self.query_one(preview_id, Static)
            preview.update(content)
        except Exception:
            pass

    def _update_status(self):
        """Update status bar based on current artifacts."""
        artifacts = self.ai_actions.current_project.get("artifacts", {})
        try:
            status_bar = self.query_one(StatusBar)
            status_bar.update_status(
                script="narration_script.md" in artifacts,
                tts="narration_tts.txt" in artifacts,
                demo="demo.py" in artifacts or "demo.ipynb" in artifacts or "demo.sh" in artifacts,
                data=len(self.generated_datasets) > 0,
                env=self.current_env.value.title()
            )
        except Exception:
            pass

    def _get_selected_environment(self) -> Environment:
        """Get currently selected environment from radio buttons."""
        try:
            radio_set = self.query_one("#env-radio", RadioSet)
            pressed = radio_set.pressed_button
            if pressed:
                env_map = {
                    "env-jupyter": Environment.JUPYTER,
                    "env-terminal": Environment.TERMINAL,
                    "env-vscode": Environment.VSCODE,
                    "env-ipython": Environment.IPYTHON,
                    "env-pycharm": Environment.PYCHARM,
                }
                return env_map.get(pressed.id, Environment.JUPYTER)
        except Exception:
            pass
        return Environment.JUPYTER

    def _get_demo_type(self) -> DemoType:
        """Get selected demo type."""
        try:
            select = self.query_one("#demo-type-select", Select)
            value = select.value
            if value and value != "auto":
                return DemoType(value)
        except Exception:
            pass
        return None

    def _get_audience_level(self) -> AudienceLevel:
        """Get selected audience level."""
        try:
            select = self.query_one("#audience-select", Select)
            return AudienceLevel(select.value)
        except Exception:
            return AudienceLevel.INTERMEDIATE

    # Button handlers

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "gen-package-btn":
            self._handle_generate_package()
        elif button_id == "check-align-btn":
            self._handle_check_alignment()
        elif button_id == "opt-tts-btn":
            self._handle_optimize_tts()
        elif button_id == "regen-script-btn":
            self._handle_regenerate_script()
        elif button_id == "gen-demo-btn":
            self._handle_generate_demo()
        elif button_id == "gen-data-btn":
            self._handle_generate_data()
        elif button_id == "quality-btn":
            self._handle_quality_check()
        elif button_id == "export-btn":
            self._handle_export()
        elif button_id == "run-demo-btn":
            self._handle_run_demo()
        elif button_id == "send-btn":
            self._handle_chat_send()
        elif button_id == "recommend-env-btn":
            self._handle_recommend_env()
        elif button_id == "analyze-data-btn":
            self._handle_analyze_data()

    @work(thread=True)
    def _handle_recommend_env(self):
        """Get AI environment recommendation."""
        topic = self.query_one("#topic-input", Input).value
        demo_type = self._get_demo_type()
        audience = self._get_audience_level()
        demo_req = self.query_one("#demo-req-input", TextArea).text

        self.call_from_thread(self._add_chat_message, "system", "Analyzing best environment...")

        try:
            result = self.env_recommender.recommend(
                topic=topic,
                demo_type=demo_type,
                audience=audience,
                requirements=demo_req
            )

            recommendation_text = f"""[bold]Recommended:[/bold] [cyan]{result['recommended'].value.title()}[/cyan]
[bold]Confidence:[/bold] {result['confidence']}

[bold]Reason:[/bold]
{result['reason']}

[bold]Alternatives:[/bold] {', '.join(e.value.title() for e in result['alternatives'])}"""

            def update_recommendation():
                try:
                    rec_static = self.query_one("#env-recommendation", Static)
                    rec_static.update(recommendation_text)
                except Exception:
                    pass

            self.call_from_thread(update_recommendation)
            self.call_from_thread(self._add_chat_message, "assistant",
                                  f"Recommended environment: [cyan]{result['recommended'].value.title()}[/cyan]")
        except Exception as e:
            self.call_from_thread(self._add_chat_message, "assistant", f"[red]Error: {e}[/red]")

    @work(thread=True)
    def _handle_analyze_data(self):
        """Analyze requirements and generate datasets."""
        topic = self.query_one("#topic-input", Input).value
        demo_req = self.query_one("#demo-req-input", TextArea).text
        demo_type = self._get_demo_type()
        duration = int(self.query_one("#duration-input", Input).value or "7")

        self.call_from_thread(self._add_chat_message, "system", "Analyzing data requirements...")

        try:
            # Analyze requirements
            configs = self.data_analyzer.analyze_requirements(
                topic=topic,
                demo_requirements=demo_req,
                demo_type=demo_type.value if demo_type else "general",
                duration_minutes=duration
            )

            # Update detected datasets display
            datasets_text = "\n".join([
                f"- [cyan]{c.name}[/cyan]: {c.rows} rows, {len(c.columns)} columns"
                for c in configs
            ])

            def update_detected():
                try:
                    det_static = self.query_one("#detected-datasets", Static)
                    det_static.update(datasets_text)
                except Exception:
                    pass

            self.call_from_thread(update_detected)

            # Generate datasets
            output_dir = Config.OUTPUT_DIR / "data"
            self.generated_datasets = self.data_generator.generate_all(configs, output_dir)

            # Show preview
            preview_text = ""
            for ds in self.generated_datasets:
                preview_text += f"\n### {ds.config.name}\n"
                preview_text += f"File: {ds.config.filename}\n"
                preview_text += f"Rows: {len(ds.dataframe)}\n\n"
                preview_text += ds.preview + "\n"

            self.call_from_thread(self._update_preview, preview_text, "data")
            self.call_from_thread(self._add_chat_message, "assistant",
                                  f"[green]Generated {len(self.generated_datasets)} dataset(s)[/green]")
            self.call_from_thread(self._update_status)

        except Exception as e:
            self.call_from_thread(self._add_chat_message, "assistant", f"[red]Error: {e}[/red]")

    @work(thread=True)
    def _handle_generate_package(self):
        """Generate full package."""
        topic = self.query_one("#topic-input", Input).value
        duration = int(self.query_one("#duration-input", Input).value or "7")
        bullets = self.query_one("#bullets-input", TextArea).text
        demo_req = self.query_one("#demo-req-input", TextArea).text
        self.current_env = self._get_selected_environment()

        self.call_from_thread(self._add_chat_message, "system",
                              f"Generating full package for {self.current_env.value.title()}...")

        result = self.ai_actions.generate_full_package(
            topic=topic,
            bullets=bullets,
            duration=duration,
            demo_requirements=demo_req
        )

        if result.success:
            self.call_from_thread(self._update_preview, result.artifacts.get("narration_script.md", ""), "script")
            self.call_from_thread(self._update_preview, result.artifacts.get("narration_tts.txt", ""), "tts")

            # Generate environment-specific demo
            script = result.artifacts.get("narration_script.md", "")
            demo_content = self._generate_env_demo(script, demo_req)
            self.call_from_thread(self._update_preview, demo_content, "demo")

            self.call_from_thread(self._add_chat_message, "assistant", f"[green]{result.message}[/green]")
        else:
            self.call_from_thread(self._add_chat_message, "assistant", f"[red]Error: {result.message}[/red]")

        self.call_from_thread(self._update_status)

    def _generate_env_demo(self, script: str, demo_req: str) -> str:
        """Generate demo for the selected environment."""
        from src.config import EnvironmentConfig

        config = EnvironmentConfig(
            name=self.current_env.value,
            theme="dark",
            font_size=14
        )

        # Extract code blocks from demo requirements
        code_blocks = [
            {"section": "CONTENT", "code": demo_req, "narration": "Demo code"}
        ]

        if self.current_env == Environment.JUPYTER:
            env = JupyterEnvironment(config)
            demo = env.generate_demo(script, code_blocks)
            self.ai_actions.current_project.setdefault("artifacts", {})["demo.ipynb"] = demo
            return demo
        elif self.current_env == Environment.TERMINAL:
            env = TerminalEnvironment(config)
            demo = env.generate_demo(script, code_blocks)
            self.ai_actions.current_project.setdefault("artifacts", {})["demo.sh"] = demo
            return demo
        else:
            # Default Python demo
            demo = self.ai_actions._generate_demo(script, demo_req, "")
            return demo

    @work(thread=True)
    def _handle_check_alignment(self):
        """Check alignment."""
        self.call_from_thread(self._add_chat_message, "system", "Checking alignment...")
        result = self.ai_actions.check_alignment()
        self.call_from_thread(self._update_preview, result.output, "report")
        self.call_from_thread(self._add_chat_message, "assistant", result.message)

    @work(thread=True)
    def _handle_optimize_tts(self):
        """Optimize TTS."""
        script = self.ai_actions.current_project.get("artifacts", {}).get("narration_script.md", "")
        if script:
            self.call_from_thread(self._add_chat_message, "system", "Optimizing for TTS...")
            tts = self.ai_actions._optimize_tts(script)
            self.ai_actions.current_project["artifacts"]["narration_tts.txt"] = tts
            self.call_from_thread(self._update_preview, tts, "tts")
            self.call_from_thread(self._add_chat_message, "assistant", "[green]TTS optimized[/green]")
        else:
            self.call_from_thread(self._add_chat_message, "assistant", "[red]No script to optimize[/red]")
        self.call_from_thread(self._update_status)

    def _handle_regenerate_script(self):
        """Regenerate script section."""
        self._add_chat_message("assistant", "Use chat to specify which section to regenerate. Example: 'Regenerate the HOOK section with more drama'")

    @work(thread=True)
    def _handle_generate_demo(self):
        """Generate demo only."""
        script = self.ai_actions.current_project.get("artifacts", {}).get("narration_script.md", "")
        demo_req = self.query_one("#demo-req-input", TextArea).text
        self.current_env = self._get_selected_environment()

        if script:
            self.call_from_thread(self._add_chat_message, "system",
                                  f"Generating {self.current_env.value.title()} demo...")
            demo = self._generate_env_demo(script, demo_req)
            self.call_from_thread(self._update_preview, demo, "demo")
            self.call_from_thread(self._add_chat_message, "assistant",
                                  f"[green]{self.current_env.value.title()} demo generated[/green]")
        else:
            self.call_from_thread(self._add_chat_message, "assistant", "[red]Generate script first[/red]")
        self.call_from_thread(self._update_status)

    @work(thread=True)
    def _handle_generate_data(self):
        """Generate data only."""
        demo_req = self.query_one("#demo-req-input", TextArea).text
        self.call_from_thread(self._add_chat_message, "system", "Generating data code...")
        data_code = self.ai_actions._generate_data(demo_req)
        self.ai_actions.current_project.setdefault("artifacts", {})["generate_data.py"] = data_code
        self.call_from_thread(self._update_preview, data_code, "data")
        self.call_from_thread(self._add_chat_message, "assistant", "[green]Data generator created[/green]")
        self.call_from_thread(self._update_status)

    @work(thread=True)
    def _handle_quality_check(self):
        """Run quality check."""
        self.call_from_thread(self._add_chat_message, "system", "Running quality checks...")
        result = self.ai_actions.check_quality()
        self.call_from_thread(self._update_preview, result.output, "report")
        self.call_from_thread(self._add_chat_message, "assistant", result.message)

    def _handle_export(self):
        """Export all files."""
        output_dir = Config.OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        result = self.ai_actions.export_all(str(output_dir))
        self._add_chat_message("assistant", f"[green]{result.message}[/green]")

    def _handle_run_demo(self):
        """Run the demo."""
        output_dir = Config.OUTPUT_DIR

        # First export
        result = self.ai_actions.export_all(str(output_dir))
        if not result.success:
            self._add_chat_message("assistant", "[red]Export failed[/red]")
            return

        # Determine demo file based on environment
        demo_files = {
            Environment.JUPYTER: "demo.ipynb",
            Environment.TERMINAL: "demo.sh",
            Environment.VSCODE: "demo.py",
            Environment.IPYTHON: "demo.py",
            Environment.PYCHARM: "demo.py",
        }

        demo_file = output_dir / demo_files.get(self.current_env, "demo.py")

        if demo_file.exists():
            self._add_chat_message("assistant", f"[green]Exported to {output_dir}[/green]")

            try:
                if self.current_env == Environment.JUPYTER:
                    subprocess.Popen(
                        f'start cmd /k "cd /d {output_dir} && jupyter notebook {demo_file.name}"',
                        shell=True
                    )
                    self._add_chat_message("assistant", "[green]Jupyter notebook launched![/green]")
                elif self.current_env == Environment.TERMINAL:
                    subprocess.Popen(
                        f'start cmd /k "cd /d {output_dir} && bash {demo_file.name}"',
                        shell=True
                    )
                    self._add_chat_message("assistant", "[green]Terminal demo launched![/green]")
                else:
                    subprocess.Popen(
                        f'start cmd /k "cd /d {output_dir} && python {demo_file.name}"',
                        shell=True
                    )
                    self._add_chat_message("assistant", "[green]Demo launched in new terminal![/green]")
            except Exception as e:
                self._add_chat_message("assistant", f"Run manually: cd {output_dir} && python {demo_file.name}")
        else:
            self._add_chat_message("assistant", "[red]No demo found. Generate package first.[/red]")

    @work(thread=True)
    def _handle_chat_send(self):
        """Handle chat message."""
        chat_input = self.query_one("#chat-input", Input)
        user_message = chat_input.value

        if not user_message.strip():
            return

        self.call_from_thread(lambda: setattr(chat_input, 'value', ''))
        self.call_from_thread(self._add_chat_message, "user", user_message)

        # Build context
        artifacts = self.ai_actions.current_project.get("artifacts", {})
        context = f"""Current project:
Topic: {self.ai_actions.current_project.get('topic', 'Not set')}
Environment: {self.current_env.value.title()}
Datasets: {len(self.generated_datasets)} generated

Current artifacts: {', '.join(artifacts.keys()) if artifacts else 'None generated yet'}

Script preview (first 500 chars):
{artifacts.get('narration_script.md', 'Not generated')[:500]}
"""

        # Get AI response
        system = f"{CHAT_ASSISTANT}\n\nContext:\n{context}"
        response = self.ai_chat.chat(user_message, system)
        self.call_from_thread(self._add_chat_message, "assistant", response)

    # Input handlers
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input fields."""
        if event.input.id == "chat-input":
            self._handle_chat_send()

    # Radio button handlers
    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Handle environment radio button changes."""
        if event.radio_set.id == "env-radio":
            self.current_env = self._get_selected_environment()
            self._update_status()

    # Keyboard shortcuts
    def action_generate_package(self):
        self._handle_generate_package()

    def action_run_demo(self):
        self._handle_run_demo()

    def action_export_all(self):
        self._handle_export()


if __name__ == "__main__":
    app = ScreenCastStudio()
    app.run()
