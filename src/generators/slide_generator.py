"""Generate presentation slides in PNG and SVG formats."""

import matplotlib
matplotlib.use("Agg")  # Headless rendering — must be set before pyplot import

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class SlideSpec:
    """Design specification for a single slide."""
    slide_type: str  # title, objective, ivq, takeaways, cta, concept
    title: str
    content: List[str] = field(default_factory=list)
    subtitle: Optional[str] = None
    image_path: Optional[Path] = None


class SlideGenerator:
    """Generate presentation slides with Coursera branding."""

    COLORS = {
        "primary_blue": "#2A73CC",
        "dark_blue": "#1F5FAA",
        "muted_blue": "#A8C4EB",
        "muted_dark": "#8CA9D5",
        "light_bg": "#F0F4F8",
        "white": "#FFFFFF",
        "dark_text": "#1A4480",
        "body_text": "#333333",
    }

    # 1920x1080 at 100 DPI
    WIDTH = 19.20
    HEIGHT = 10.80
    DPI = 100

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "png").mkdir(exist_ok=True)
        (self.output_dir / "svg").mkdir(exist_ok=True)

    def generate_all_slides(self, specs: List[SlideSpec]) -> List[Path]:
        """Generate all slides from specs, returning list of output paths."""
        paths: List[Path] = []
        for i, spec in enumerate(specs, 1):
            filename = f"slide_{i:02d}_{spec.slide_type}"
            paths.extend(self._generate_slide(spec, filename))
        return paths

    def _generate_slide(self, spec: SlideSpec, filename: str) -> List[Path]:
        """Generate a single slide in both PNG and SVG."""
        fig, ax = plt.subplots(figsize=(self.WIDTH, self.HEIGHT), dpi=self.DPI)
        ax.set_xlim(0, 192)
        ax.set_ylim(0, 108)
        ax.axis("off")
        fig.patch.set_facecolor(self.COLORS["white"])

        renderers = {
            "title": self._render_title_slide,
            "objective": self._render_objective_slide,
            "ivq": self._render_ivq_slide,
            "takeaways": self._render_takeaways_slide,
            "cta": self._render_cta_slide,
            "concept": self._render_concept_slide,
        }

        renderer = renderers.get(spec.slide_type, self._render_concept_slide)
        renderer(ax, spec)

        png_path = self.output_dir / "png" / f"{filename}.png"
        svg_path = self.output_dir / "svg" / f"{filename}.svg"

        fig.savefig(
            png_path, dpi=self.DPI, facecolor=self.COLORS["white"],
            bbox_inches="tight", pad_inches=0,
        )
        fig.savefig(
            svg_path, format="svg", facecolor=self.COLORS["white"],
            bbox_inches="tight", pad_inches=0,
        )
        plt.close(fig)

        return [png_path, svg_path]

    def _render_title_slide(self, ax, spec: SlideSpec):
        """Render title slide with video name and subtitle."""
        header = FancyBboxPatch(
            (0, 85), 192, 23,
            facecolor=self.COLORS["primary_blue"], edgecolor="none",
        )
        ax.add_patch(header)

        ax.text(
            96, 55, spec.title, fontsize=36, fontweight="bold",
            color=self.COLORS["dark_text"], ha="center", va="center",
            fontfamily="sans-serif",
        )

        if spec.subtitle:
            ax.text(
                96, 40, spec.subtitle, fontsize=20,
                color=self.COLORS["body_text"], ha="center", va="center",
                fontfamily="sans-serif",
            )

    def _render_objective_slide(self, ax, spec: SlideSpec):
        """Render learning objectives slide."""
        ax.text(
            96, 90, "Learning Goals", fontsize=28, fontweight="bold",
            color=self.COLORS["dark_text"], ha="center", fontfamily="sans-serif",
        )

        ax.plot(
            [40, 152], [82, 82],
            color=self.COLORS["primary_blue"], linewidth=3,
        )

        ax.text(
            20, 72, "By the end of this video, you'll be able to:",
            fontsize=18, color=self.COLORS["body_text"], fontfamily="sans-serif",
        )

        y_pos = 60
        for obj in spec.content[:4]:
            circle = plt.Circle((25, y_pos), 3, color=self.COLORS["primary_blue"])
            ax.add_patch(circle)
            ax.text(
                32, y_pos, obj, fontsize=16,
                color=self.COLORS["body_text"], va="center",
                fontfamily="sans-serif",
            )
            y_pos -= 14

    def _render_ivq_slide(self, ax, spec: SlideSpec):
        """Render In-Video Question slide."""
        header = FancyBboxPatch(
            (0, 90), 192, 18,
            facecolor=self.COLORS["primary_blue"], edgecolor="none",
        )
        ax.add_patch(header)
        ax.text(
            96, 99, "Check Your Understanding", fontsize=24, fontweight="bold",
            color="white", ha="center", fontfamily="sans-serif",
        )

        ax.text(
            96, 75, spec.title, fontsize=20,
            color=self.COLORS["dark_text"], ha="center",
            fontfamily="sans-serif",
        )

        y_pos = 58
        letters = ["A", "B", "C", "D"]
        for letter, option in zip(letters, spec.content[:4]):
            box = FancyBboxPatch(
                (20, y_pos - 5), 152, 12,
                facecolor=self.COLORS["light_bg"],
                edgecolor=self.COLORS["muted_blue"],
                boxstyle="round,pad=0.02", linewidth=2,
            )
            ax.add_patch(box)
            ax.text(
                25, y_pos, f"{letter})", fontsize=14, fontweight="bold",
                color=self.COLORS["primary_blue"], va="center",
                fontfamily="sans-serif",
            )
            ax.text(
                35, y_pos, option, fontsize=14,
                color=self.COLORS["body_text"], va="center",
                fontfamily="sans-serif",
            )
            y_pos -= 14

    def _render_takeaways_slide(self, ax, spec: SlideSpec):
        """Render key takeaways slide."""
        ax.text(
            96, 95, "Key Takeaways", fontsize=28, fontweight="bold",
            color=self.COLORS["dark_text"], ha="center", fontfamily="sans-serif",
        )

        ax.plot(
            [40, 152], [87, 87],
            color=self.COLORS["primary_blue"], linewidth=3,
        )

        y_pos = 72
        for takeaway in spec.content[:6]:
            ax.text(
                20, y_pos, "\u2713", fontsize=18,
                color=self.COLORS["primary_blue"], va="center",
            )
            ax.text(
                30, y_pos, takeaway, fontsize=16,
                color=self.COLORS["body_text"], va="center",
                fontfamily="sans-serif",
            )
            y_pos -= 12

    def _render_cta_slide(self, ax, spec: SlideSpec):
        """Render call-to-action slide."""
        fig = ax.get_figure()
        fig.patch.set_facecolor(self.COLORS["primary_blue"])

        ax.text(
            96, 60, spec.title, fontsize=32, fontweight="bold",
            color="white", ha="center", fontfamily="sans-serif",
        )

        if spec.content:
            ax.text(
                96, 45, spec.content[0], fontsize=20,
                color="white", ha="center", fontfamily="sans-serif", alpha=0.9,
            )

    def _render_concept_slide(self, ax, spec: SlideSpec):
        """Render generic concept slide with title and bullets."""
        ax.text(
            96, 95, spec.title, fontsize=26, fontweight="bold",
            color=self.COLORS["dark_text"], ha="center", fontfamily="sans-serif",
        )

        y_pos = 75
        for item in spec.content:
            ax.text(
                20, y_pos, f"\u2022 {item}", fontsize=16,
                color=self.COLORS["body_text"], fontfamily="sans-serif",
            )
            y_pos -= 12


def generate_slides_from_script(script, output_dir: Path) -> List[Path]:
    """Generate all slides needed for a video script.

    Args:
        script: An ImportedScript instance.
        output_dir: Directory where slides will be saved.

    Returns:
        List of generated file paths (PNG and SVG pairs).
    """
    generator = SlideGenerator(output_dir)
    specs: List[SlideSpec] = []

    # Title slide
    specs.append(SlideSpec(
        slide_type="title",
        title=script.title,
        subtitle="Course Module",
    ))

    # Objective slide
    for section in script.sections:
        if section["type"] == "OBJECTIVE":
            objectives = [
                line.strip().lstrip("-*\u2022 ")
                for line in section["text"].split("\n")
                if line.strip() and line.strip()[0] in ("-", "\u2022", "*")
            ]
            if objectives:
                specs.append(SlideSpec(
                    slide_type="objective",
                    title="Learning Goals",
                    content=objectives,
                ))
            break

    # IVQ slide
    if script.ivq:
        option_texts = [
            opt["text"] for opt in script.ivq.get("options", [])
        ]
        specs.append(SlideSpec(
            slide_type="ivq",
            title=script.ivq.get("question", ""),
            content=option_texts,
        ))

    # Summary / takeaways slide
    for section in script.sections:
        if section["type"] == "SUMMARY":
            takeaways = [
                line.strip()
                for line in section["text"].split("\n")
                if line.strip() and len(line.strip()) > 10
            ][:6]
            if takeaways:
                specs.append(SlideSpec(
                    slide_type="takeaways",
                    title="Key Takeaways",
                    content=takeaways,
                ))
            break

    # CTA slide
    for section in script.sections:
        if section["type"] == "CALL TO ACTION":
            specs.append(SlideSpec(
                slide_type="cta",
                title="Next Steps",
                content=[section["text"][:100]],
            ))
            break

    return generator.generate_all_slides(specs)
