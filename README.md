# CloudQA AI Tester

Natural-language browser test automation using Python, Selenium, Groq, and semantic element resolution.

## Features

- Convert natural-language instructions into structured browser test plans
- Execute Selenium actions from validated Pydantic models
- Semantic element resolution without requiring CSS selectors or XPath
- Automatic retries for transient Selenium interaction errors
- Assertions for page content and URLs
- Failure screenshots
- JSON test reports
- CLI execution

## Architecture

```text
Natural Language Test
        |
        v
   Groq Planner
        |
        v
  Pydantic TestPlan
        |
        v
  Locator Engine
        |
        v
 Selenium Executor
        |
        v
 PASS / FAIL Report
```

## Setup

### Requirements

- Python 3.10+
- Google Chrome
- Groq API key

### Installation

```bash
git clone YOUR_REPOSITORY_URL
cd cloudqa-ai-tester

python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Configure environment variables:

```powershell
copy .env.example .env
```

Add your Groq API key to `.env`.

## Usage

Headless:

```bash
python main.py --url https://example.com --test "Verify the page displays Example Domain" --yes
```

Visible browser:

```bash
python main.py --url https://example.com --test "Verify the page displays Example Domain" --headed --yes
```

Interactive plan confirmation:

```bash
python main.py --url https://example.com --test "Verify the page displays Example Domain"
```

## Supported Actions

- CLICK
- TYPE
- SELECT
- ASSERT_TEXT
- ASSERT_URL
- WAIT
- PRESS_ENTER

## Output

- `reports/test_report.json`
- `screenshots/failure_step_*.png`

## Security

- Store credentials in environment variables.
- Never commit `.env`.
- Review generated plans before executing tests against sensitive websites.

## Limitations

Semantic locator resolution can be ambiguous when multiple elements have similar labels. Dynamic websites may require additional waiting strategies or locator refinements.
