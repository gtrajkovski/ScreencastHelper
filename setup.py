"""Setup configuration for ScreenCast Studio."""

from setuptools import setup, find_packages

setup(
    name="screencast-studio",
    version="0.1.0",
    description="AI-powered screencast production assistant",
    author="ScreenCast Studio Team",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.9",
    install_requires=[
        "anthropic>=0.18.0",
        "rich>=13.0.0",
        "typer>=0.9.0",
        "pyyaml>=6.0",
        "jinja2>=3.1.0",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "ruff>=0.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "screencast-studio=ui.cli:main",
        ],
    },
)
