"""
Configuration for the Poll Results Visualizer.

Central place for paths, colour palette and project-wide constants so every
module shares the same design language.
"""

from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------- #
# Project metadata
# --------------------------------------------------------------------------- #
PROJECT_NAME: str = "Poll Results Visualizer"
PROJECT_AUTHOR: str = "Harsha K S"
PROJECT_VERSION: str = "1.0.0"
PROJECT_LICENSE: str = "MIT"

# --------------------------------------------------------------------------- #
# Project paths
# --------------------------------------------------------------------------- #
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

DATA_DIR: Path = PROJECT_ROOT / "data"
RAW_DATA_DIR: Path = DATA_DIR / "raw"
PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"

OUTPUT_DIR: Path = PROJECT_ROOT / "outputs"
CHARTS_DIR: Path = OUTPUT_DIR / "charts"
REPORTS_DIR: Path = OUTPUT_DIR / "reports"

NOTEBOOK_DIR: Path = PROJECT_ROOT / "notebooks"
IMAGE_DIR: Path = PROJECT_ROOT / "images"

RAW_CSV_PATH: Path = RAW_DATA_DIR / "poll_responses_raw.csv"
CLEAN_CSV_PATH: Path = PROCESSED_DATA_DIR / "poll_responses_clean.csv"
SUMMARY_JSON_PATH: Path = REPORTS_DIR / "analysis_summary.json"
INSIGHTS_MD_PATH: Path = REPORTS_DIR / "insights_report.md"
QUALITY_MD_PATH: Path = REPORTS_DIR / "data_quality_report.md"

# --------------------------------------------------------------------------- #
# Light-mode design system (distinct, high-contrast colours)
# --------------------------------------------------------------------------- #
THEME: dict[str, str] = {
    "background": "#F6F8FC",
    "surface": "#FFFFFF",
    "border": "#E2E8F0",
    "text": "#1E293B",
    "muted": "#64748B",
    "primary": "#4F46E5",  # indigo
    "secondary": "#0EA5E9",  # sky blue
    "accent": "#F59E0B",  # amber
    "success": "#10B981",  # emerald
    "danger": "#EF4444",  # red
    "purple": "#8B5CF6",
    "pink": "#EC4899",
    "teal": "#14B8A6",
    "lime": "#84CC16",
}

# Ordered palette reused by matplotlib, seaborn and plotly so charts match.
CHART_PALETTE: list[str] = [
    "#4F46E5",
    "#0EA5E9",
    "#F59E0B",
    "#10B981",
    "#8B5CF6",
    "#EC4899",
    "#14B8A6",
    "#EF4444",
    "#84CC16",
    "#6366F1",
]

# Matplotlib figure style
FIG_DPI: int = 150
FIG_SIZE_WIDE: tuple[int, int] = (11, 6)
FIG_SIZE_SQUARE: tuple[int, int] = (9, 7)

# --------------------------------------------------------------------------- #
# Poll design (drives the synthetic dataset generator)
# --------------------------------------------------------------------------- #
RANDOM_SEED: int = 42
N_RESPONDENTS: int = 1200
POLL_DAYS: int = 30

REGIONS: list[str] = ["North", "South", "East", "West", "Central"]
REGION_WEIGHTS: list[float] = [0.24, 0.22, 0.18, 0.20, 0.16]

AGE_GROUPS: list[str] = ["18-24", "25-34", "35-44", "45-54", "55+"]
AGE_WEIGHTS: list[float] = [0.30, 0.32, 0.18, 0.12, 0.08]

GENDERS: list[str] = ["Female", "Male", "Non-binary", "Prefer not to say"]
GENDER_WEIGHTS: list[float] = [0.46, 0.44, 0.05, 0.05]

DEVICES: list[str] = ["Mobile", "Desktop", "Tablet"]
DEVICE_WEIGHTS: list[float] = [0.58, 0.32, 0.10]

CHANNELS: list[str] = ["Email", "Social Media", "Campus Outreach", "QR Poster", "Referral"]
CHANNEL_WEIGHTS: list[float] = [0.28, 0.24, 0.20, 0.16, 0.12]

# Each question has an id, prompt, options, baseline weights and an optional
# demographic tilt so that region-wise / age-wise analysis is meaningful.
QUESTIONS: list[dict] = [
    {
        "id": "Q1",
        "prompt": "Which candidate do you support in the student council election?",
        "category": "Election Poll",
        "options": [
            "Candidate A - Aarav",
            "Candidate B - Bianca",
            "Candidate C - Chen",
            "Undecided",
        ],
        "weights": [0.33, 0.28, 0.24, 0.15],
        # (filter column, filter value, multiplier map per option)
        "tilts": [
            ("region", "North", [1.45, 1.00, 0.75, 0.80]),
            ("region", "South", [0.70, 1.40, 1.10, 0.90]),
            ("region", "East", [0.95, 0.85, 1.45, 0.85]),
            ("age_group", "18-24", [1.30, 1.15, 0.90, 1.20]),
            ("age_group", "55+", [0.75, 0.80, 1.25, 1.30]),
        ],
    },
    {
        "id": "Q2",
        "prompt": "Which feature should we prioritise in the next release?",
        "category": "Product Preference",
        "options": [
            "Dark Mode & Accessibility",
            "Faster Search & Filters",
            "Offline Sync",
            "Team Collaboration",
            "Lower Pricing",
        ],
        "weights": [0.22, 0.28, 0.18, 0.17, 0.15],
        "tilts": [
            ("age_group", "18-24", [1.35, 1.00, 1.20, 0.75, 0.85]),
            ("age_group", "55+", [1.45, 1.15, 0.70, 0.70, 1.30]),
            ("device", "Mobile", [1.30, 1.20, 1.10, 0.80, 1.05]),
        ],
    },
    {
        "id": "Q3",
        "prompt": "How satisfied are you with the current service?",
        "category": "Customer Feedback",
        "options": [
            "1 - Very Dissatisfied",
            "2 - Dissatisfied",
            "3 - Neutral",
            "4 - Satisfied",
            "5 - Very Satisfied",
        ],
        "weights": [0.08, 0.13, 0.21, 0.32, 0.26],
        "tilts": [
            ("region", "East", [1.20, 1.15, 1.00, 0.95, 0.75]),
            ("region", "North", [0.70, 0.80, 0.95, 1.15, 1.30]),
            ("channel", "Email", [0.70, 0.80, 0.95, 1.20, 1.25]),
        ],
        "is_scale": True,
    },
    {
        "id": "Q4",
        "prompt": "Which communication channel do you prefer for updates?",
        "category": "Customer Feedback",
        "options": ["WhatsApp / Telegram", "Email Newsletter", "In-App Notifications", "SMS", "Push via Web"],
        "weights": [0.34, 0.22, 0.18, 0.14, 0.12],
        "tilts": [
            ("age_group", "18-24", [1.40, 0.75, 1.20, 0.80, 1.05]),
            ("age_group", "55+", [0.55, 1.50, 0.60, 1.45, 0.70]),
        ],
    },
    {
        "id": "Q5",
        "prompt": "Which product variant would you buy?",
        "category": "Product Preference",
        "options": ["Starter (Free)", "Pro Monthly", "Pro Annual", "Team Plan", "Enterprise"],
        "weights": [0.30, 0.26, 0.20, 0.16, 0.08],
        "tilts": [
            ("age_group", "18-24", [1.45, 1.20, 0.80, 0.65, 0.50]),
            ("region", "North", [1.10, 1.15, 1.05, 1.10, 1.25]),
        ],
    },
]

# Open-ended feedback snippets used to build a text-frequency "word cloud".
OPEN_TEXT_TEMPLATES: list[str] = [
    "loved the new dashboard, very fast and clean",
    "would love dark mode and better keyboard shortcuts",
    "pricing is a bit high for students",
    "the mobile app crashes sometimes on android",
    "great support team, resolved my ticket quickly",
    "please add offline mode for travel",
    "search needs filters and better sorting",
    "love the collaboration features for teams",
    "notifications are too frequent, allow muting",
    "onboarding was simple and well documented",
    "need more integrations with calendar and slack",
    "the reports export should support pdf",
    "overall good experience, keep improving",
    "wish the dashboard loaded faster on slow networks",
    "add multi language support please",
    "excellent design and easy to use interface",
    "student discount would help a lot",
    "the free plan is limited but acceptable",
    "please improve accessibility and screen reader labels",
    "awesome poll feature, more analytics please",
]

# --------------------------------------------------------------------------- #
# Noise / dirty-data injection rates (make the cleaning stage meaningful)
# --------------------------------------------------------------------------- #
DIRTY_DUPLICATE_RATE: float = 0.03
DIRTY_MISSING_RATE: float = 0.04
DIRTY_INVALID_RATE: float = 0.02
DIRTY_CASE_RATE: float = 0.08
DIRTY_WHITESPACE_RATE: float = 0.06
DIRTY_DATE_FORMAT_RATE: float = 0.20

CANONICAL_COLUMNS: list[str] = [
    "respondent_id",
    "response_date",
    "question_id",
    "question",
    "category",
    "option_selected",
    "satisfaction_score",
    "region",
    "age_group",
    "gender",
    "device",
    "channel",
    "open_feedback",
]
