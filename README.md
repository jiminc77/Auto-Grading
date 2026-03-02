# Auto-Grading Pipeline

This repository helps you grade homework in 3 steps:

1. Prepare assignment files (`problems`, `rubrics`)
2. Generate grading prompts (and review them) or make it manually
3. Run grading for all students

## 1) Get the code (first time)

```bash
git clone https://github.com/jiminc77/Auto-Grading.git
cd Auto-Grading
```

## 2) Update code later (already cloned)

From the project root:

```bash
cd Auto-Grading
git pull origin main
```

## 3) Environment setup (Windows / macOS / Linux)

### Windows (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Set Gemini API key (current terminal only):

```powershell
$env:GOOGLE_API_KEY="YOUR_API_KEY_HERE"
```

If PowerShell blocks activation, run once in the same terminal and retry:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Install PDF tools for auto PDF report:

1. Install Pandoc: [pandoc.org/installing.html](https://pandoc.org/installing.html)
2. Install MiKTeX (includes `xelatex`): [miktex.org/download](https://miktex.org/download)
3. Reopen terminal, then check:

```powershell
pandoc --version
xelatex --version
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
export GOOGLE_API_KEY="YOUR_API_KEY_HERE"
```

PDF tools:

```bash
# macOS
brew install pandoc
brew install --cask mactex-no-gui

# Ubuntu/Debian example
sudo apt-get update
sudo apt-get install -y pandoc texlive-xetex
```

## 4) Folder structure

At repository root:

1. `grading_pipeline/` (shared grading code)
2. `run_grading_pipeline.py` (main runner)
3. `create_homework.py` (interactive HW folder creator)
4. `HW2/`, `HW3/`, ... (homework-specific data)

Inside each `HWn/`:

1. `assignment/problems/`
2. `assignment/rubrics/`
3. `assignment/prompts/`
4. `submissions/`
5. `results/`
6. `assignment_config.json`

## 5) Create a new homework (HW3, HW4, ...)

```bash
python create_homework.py
```

The script asks for homework number and creates:

- `HWn/assignment`
- `HWn/submissions`
- `HWn/results`
- `HWn/assignment_config.json`

## 6) File naming rules (important)

Use exact names so auto-discovery works:

1. Problems: `problem_pN.ipynb` (or `.md`, `.txt`)
2. Rubrics: `rubric_pN.md` (or `.txt`)
3. Prompts: generated as `prompt_pN.md`

If naming is wrong, pipeline stops with an error.

## 7) Grading workflow (per homework)

Example: grading `HW3`.

### Step A. Put files in place

1. Put problems into `HW3/assignment/problems/`
2. Put rubrics into `HW3/assignment/rubrics/`
3. Put student submissions into `HW3/submissions/{student_name}/...`

### Step B. Generate prompts (optional, manual review required)

```bash
python run_grading_pipeline.py --config HW3/assignment_config.json --generate-prompts
```

Review prompt files in:

`HW3/assignment/prompts/`

### Step C. Run grading

```bash
python run_grading_pipeline.py --config HW3/assignment_config.json
```

If prompts are missing, grading will stop and ask you to generate prompts first.

Resume behavior:

1. Completed students are skipped automatically on next run.
2. Students that failed mid-run (or had grading errors) are re-graded on next run.
3. Checkpoints are stored in `HW3/results/checkpoints/`.

## 8) Outputs

For `HW3`:

1. Markdown report: `HW3/results/Grading_Report_YYYYMMDD_HHMMSS.md`
2. JSON snapshot: `HW3/results/Grading_Report_YYYYMMDD_HHMMSS.json`
3. PDF report (auto): `HW3/results/Grading_Report_YYYYMMDD_HHMMSS.pdf`
4. Artifacts: `HW3/results/artifacts/{student_name}/...`
5. Student checkpoints: `HW3/results/checkpoints/{student_name}.json`

PDF is generated automatically at the end of grading (if `report_pdf.enabled=true`).
If PDF generation fails, markdown/json are still saved.

## 9) PDF style settings

You can control PDF formatting in `HWn/assignment_config.json`:

```json
"report_pdf": {
  "enabled": true,
  "pdf_engine": "xelatex",
  "paper_size": "letterpaper",
  "margin": "0.85in",
  "font_size": "10pt",
  "line_spacing": 1.12
}
```

The pipeline also applies line-wrap settings for long code/text to reduce clipping.

## 10) Model fallback on 503 (high demand)

If `gemini-3.1-pro-preview` returns temporary `503 UNAVAILABLE`, grading now retries and can automatically switch to fallback models.

Set fallback models in `HWn/assignment_config.json`:

```json
"models": {
  "split_model": "gemini-3-flash-preview",
  "grade_model": "gemini-3.1-pro-preview",
  "prompt_model": "gemini-3.1-pro-preview",
  "grade_fallback_models": ["gemini-3-flash", "gemini-3-flash-preview"]
}
```

## 11) Common errors

1. `GOOGLE_API_KEY is not set`
- Windows PowerShell: `$env:GOOGLE_API_KEY="YOUR_API_KEY_HERE"`
- macOS/Linux: `export GOOGLE_API_KEY="YOUR_API_KEY_HERE"`

2. Gemini quota/auth errors
- Check API key validity and billing/quota on your Gemini project.

3. Empty model response
- Retry once; if repeated, lower input size or check API availability.

4. PDF generation failed
- Install `pandoc` and a LaTeX engine (`xelatex` recommended).
- Or set `"report_pdf": { "enabled": false }` in config.

5. `503 UNAVAILABLE` from Gemini
- Usually temporary high demand on model side.
- Pipeline retries automatically and can switch to `grade_fallback_models`.
