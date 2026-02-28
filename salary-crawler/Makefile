PYTHON ?= python3
PYTHONPATH := src
RAW_JSONL := data/raw/jobs_raw.jsonl
CLEAN_CSV := data/clean/jobs_clean.csv
CLEAN_JSON := data/clean/jobs_clean.json
FIGURE_DIR := reports/figures
SUMMARY_MD := reports/summary.md
TARGETS := config/targets.json

.PHONY: crawl clean report all test schedule

crawl:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m zhaopin_salary.cli crawl --targets $(TARGETS) --output $(RAW_JSONL) --max-pages 3

clean:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m zhaopin_salary.cli clean --input $(RAW_JSONL) --csv $(CLEAN_CSV) --json $(CLEAN_JSON)

report:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m zhaopin_salary.cli report --input $(CLEAN_CSV) --figure-dir $(FIGURE_DIR) --summary $(SUMMARY_MD)

all: crawl clean report

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest discover -s tests -p "test_*.py"

schedule:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m zhaopin_salary.cli schedule
