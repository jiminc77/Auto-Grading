# Auto-Grading Pipeline (MECE6313)

This repository helps you grade homework with Gemini in 3 steps:

1. Prepare assignment files (`problems`, `rubrics`)
2. Generate grading prompts (and review them)
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

## 3) Python environment setup (one time)

Create and use a local virtual environment only for this project:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Set Gemini API key:

```bash
export GOOGLE_API_KEY="YOUR_API_KEY_HERE"
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
python3 create_homework.py
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

### Step B. Generate prompts (manual review required)

```bash
python3 run_grading_pipeline.py --config HW3/assignment_config.json --generate-prompts
```

Review prompt files in:

`HW3/assignment/prompts/`

### Step C. Run grading

```bash
python3 run_grading_pipeline.py --config HW3/assignment_config.json
```

If prompts are missing, grading will stop and ask you to generate prompts first.

## 8) Outputs

For `HW3`:

1. Markdown report: `HW3/results/Grading_Report_YYYYMMDD_HHMMSS.md`
2. JSON snapshot: `HW3/results/Grading_Report_YYYYMMDD_HHMMSS.json`
3. Artifacts: `HW3/results/artifacts/{student_name}/...`

## 9) Model/temperature control

In `HWn/assignment_config.json` you can set different temperatures by stage:

1. `prompt_generation.temperature` (prompt writing)
2. `split.temperature` (submission-to-problem split)
3. `grading.temperature` (final grading)

Default idea:

- prompt generation: `1.0`
- split: `0.5`
- grading: `0.1`

## 10) Common errors

1. `GOOGLE_API_KEY is not set`
- Run: `export GOOGLE_API_KEY="YOUR_API_KEY_HERE"`

2. Gemini quota/auth errors
- Check API key validity and billing/quota on your Gemini project.

3. Empty model response
- Retry once; if repeated, lower input size or check API availability.
