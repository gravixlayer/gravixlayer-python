#!/usr/bin/env python3
"""
Data Analyst Agent — OpenAI + GravixLayer SDK

An AI-powered data analyst that uses any OpenAI-compatible LLM to generate
Python code, executes it in a secure GravixLayer Agent Runtime, and
iteratively analyzes a dataset to produce insights and charts.

Dataset: Seaborn Diamonds (53,940 diamonds with price, carat, cut, color, clarity)
Source:  https://github.com/mwaskom/seaborn-data

Usage:
    export OPENAI_API_KEY="your-api-key"
    export GRAVIXLAYER_API_KEY="your-gravixlayer-api-key"
    python data_analyst_agent.py
"""

import os
import re
import sys
import time
from dataclasses import dataclass, field

from openai import OpenAI
from gravixlayer.examples_env import python_runtime_template
from gravixlayer.types.runtime import Runtime


# ---------------------------------------------------------------------------
# Execution timing tracker
# ---------------------------------------------------------------------------

@dataclass
class ExecTiming:
    step: int
    round: int
    code_len: int
    exec_ms: float
    label: str = ""


@dataclass
class TimingTracker:
    exec_timings: list[ExecTiming] = field(default_factory=list)
    llm_timings: list[float] = field(default_factory=list)
    analysis_start: float = 0.0
    analysis_end: float = 0.0

    def record_exec(self, step: int, round_: int, code_len: int, exec_ms: float, label: str = ""):
        self.exec_timings.append(ExecTiming(step, round_, code_len, exec_ms, label))

    def record_llm(self, ms: float):
        self.llm_timings.append(ms)

    def print_summary(self):
        total_analysis = (self.analysis_end - self.analysis_start) * 1000
        total_exec = sum(t.exec_ms for t in self.exec_timings)
        total_llm = sum(self.llm_timings)
        overhead = total_analysis - total_exec - total_llm

        print(f"\n{'='*70}")
        print("  EXECUTION TIMING SUMMARY")
        print(f"{'='*70}")
        print(f"  Total analysis time:    {total_analysis:>10.1f} ms")
        print(f"  Total code execution:   {total_exec:>10.1f} ms  ({total_exec/total_analysis*100:.1f}%)")
        print(f"  Total LLM inference:    {total_llm:>10.1f} ms  ({total_llm/total_analysis*100:.1f}%)")
        print(f"  Overhead (network/etc): {overhead:>10.1f} ms  ({overhead/total_analysis*100:.1f}%)")
        print(f"{'─'*70}")
        print(f"  {'Step':>4}  {'Rnd':>3}  {'Code Len':>8}  {'Exec (ms)':>10}  Label")
        print(f"  {'─'*4}  {'─'*3}  {'─'*8}  {'─'*10}  {'─'*30}")
        for t in self.exec_timings:
            print(f"  {t.step:>4}  {t.round:>3}  {t.code_len:>8}  {t.exec_ms:>10.1f}  {t.label}")
        print(f"{'─'*70}")

        if self.exec_timings:
            times = [t.exec_ms for t in self.exec_timings]
            print(f"  Code exec min/avg/max: {min(times):.1f} / {sum(times)/len(times):.1f} / {max(times):.1f} ms")
        if self.llm_timings:
            print(f"  LLM call  min/avg/max: {min(self.llm_timings):.1f} / {sum(self.llm_timings)/len(self.llm_timings):.1f} / {max(self.llm_timings):.1f} ms")
        print(f"{'='*70}")


tracker = TimingTracker()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATASET_URL = (
    "https://raw.githubusercontent.com/mwaskom/seaborn-data/"
    "master/diamonds.csv"
)
DATASET_PATH = "/workspace/diamonds.csv"
CHARTS_DIR = "/workspace/charts"
LOCAL_CHARTS_DIR = "charts"

ANALYSIS_STEPS = [
    (
        "Load the dataset and print a concise overview: shape, column names with "
        "dtypes, missing-value counts, and descriptive statistics for the numeric "
        "columns (carat, depth, table, price, x, y, z). Also print the unique "
        "values of the categorical columns (cut, color, clarity)."
    ),
    (
        "Create a box plot of diamond price grouped by cut quality (Fair, Good, "
        "Very Good, Premium, Ideal). Order cuts from Fair to Ideal on the x-axis. "
        "Use seaborn, add a title, and save to /workspace/charts/price_by_cut.png"
    ),
    (
        "Create a scatter plot of carat (x-axis) vs price (y-axis), colored by "
        "cut quality. Use alpha=0.3 for transparency. Add a title, legend, and "
        "save to /workspace/charts/carat_vs_price.png"
    ),
    (
        "Create a bar chart showing the average price for each combination of "
        "color (D-J) and clarity (IF, VVS1, VVS2, VS1, VS2, SI1, SI2, I1). "
        "Group bars by color, use clarity as the hue. Add a title, legend, and "
        "save to /workspace/charts/price_by_color_clarity.png"
    ),
    (
        "Summarize the key insights: how does cut, carat, color, and clarity "
        "each affect price? Which combination produces the highest average price? "
        "Are there any surprising patterns? Keep it to 5-8 bullet points."
    ),
]

SYSTEM_PROMPT_TEMPLATE = """You are an expert data analyst. You write Python code that runs in a secure Agent Runtime.

Dataset: /workspace/diamonds.csv — 53,940 diamonds with columns:
{columns}

IMPORTANT: Each code block runs in ISOLATED execution — variables do NOT persist.
Re-import libraries and re-load the CSV in every code block.

Respond with Python code inside a ```python block.

Rules:
1. Import libraries and load CSV at the top of every code block.
2. Use print() to display results.
3. Save charts with plt.savefig(), then plt.close(). No plt.show().
4. Use plt.tight_layout() and figsize=(12, 8).
5. Add titles, axis labels, and legends to all charts.
6. Use the exact column names listed above.
"""

STDERR_FILTERS = [
    "UserWarning", "Matplotlib", "FutureWarning",
    "/tmp", "main.py:", "DtypeWarning",
]


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def execute_code_in_runtime(runtime: Runtime, code: str) -> tuple[str, float]:
    """Execute Python code in the Agent Runtime and return (output, elapsed_ms)."""
    t0 = time.perf_counter()
    try:
        result = runtime.run_code(code)
    except Exception as exc:
        elapsed = (time.perf_counter() - t0) * 1000
        return f"[runtime error]: {exc}", elapsed
    elapsed = (time.perf_counter() - t0) * 1000

    parts = []
    if result.stdout and result.stdout.strip():
        parts.append(result.stdout.strip())
    if result.stderr and result.stderr.strip():
        error_lines = [
            line for line in result.stderr.strip().split("\n")
            if not any(f in line for f in STDERR_FILTERS)
        ]
        if error_lines:
            parts.append(f"[stderr]: {chr(10).join(error_lines)}")

    output = "\n".join(parts) if parts else "Code executed successfully (no output)."
    return output, elapsed


def extract_code_block(text: str) -> str | None:
    """Extract the first Python code block from an LLM response."""
    match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else None


def discover_columns(runtime: Runtime) -> str:
    """Read column names from the dataset so the LLM gets exact names."""
    result = runtime.run_code(
        "import pandas as pd\n"
        f"df = pd.read_csv('{DATASET_PATH}', nrows=1)\n"
        "print(', '.join(df.columns.tolist()))"
    )
    return result.stdout.strip() if result.stdout else ""


# ---------------------------------------------------------------------------
# Analysis loop
# ---------------------------------------------------------------------------


def run_analysis(openai_client: OpenAI, runtime: Runtime) -> None:
    """Run each analysis step, executing LLM-generated code in the runtime."""
    model = os.environ.get("OPENAI_MODEL", "gpt-4o")
    tracker.analysis_start = time.perf_counter()

    print("\nDiscovering dataset columns...")
    columns = discover_columns(runtime)
    print(f"  Columns: {columns}")

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(columns=columns)
    messages = [{"role": "system", "content": system_prompt}]

    for i, question in enumerate(ANALYSIS_STEPS, 1):
        print(f"\n{'#'*70}")
        print(f"  STEP {i}/{len(ANALYSIS_STEPS)}")
        print(f"  {question[:80]}{'...' if len(question) > 80 else ''}")
        print(f"{'#'*70}")

        messages.append({"role": "user", "content": question})

        for round_num in range(5):
            llm_t0 = time.perf_counter()
            response = openai_client.chat.completions.create(
                model=model,
                messages=messages,
            )
            llm_elapsed = (time.perf_counter() - llm_t0) * 1000
            tracker.record_llm(llm_elapsed)
            print(f"  [LLM] {llm_elapsed:.1f} ms")

            reply = response.choices[0].message.content or ""
            messages.append({"role": "assistant", "content": reply})

            code = extract_code_block(reply)
            if not code:
                # No code block → final text answer for this step
                print(f"\n{'='*60}")
                print(reply)
                print(f"{'='*60}")
                break

            print(f"\n{'='*60}")
            print("EXECUTING:")
            print(f"{'='*60}")
            print(code if len(code) <= 600 else code[:600] + "\n... (truncated)")
            print(f"{'='*60}")

            output, exec_ms = execute_code_in_runtime(runtime, code)

            # Classify the execution by what it does
            label = ""
            if "savefig" in code:
                label = "chart-generation"
            elif "pd.read_csv" in code and "describe" in code:
                label = "data-load+describe"
            elif "pd.read_csv" in code:
                label = "data-load"
            elif "print" in code:
                label = "compute+print"
            tracker.record_exec(i, round_num + 1, len(code), exec_ms, label)

            print(f"\n  [EXEC] {exec_ms:.1f} ms | code={len(code)} chars | {label}")
            print(f"\nOUTPUT:")
            print(f"{'-'*60}")
            print(output[:2000] if len(output) > 2000 else output)
            print(f"{'-'*60}")

            messages.append({
                "role": "user",
                "content": (
                    f"Code output:\n{output}\n\n"
                    "Provide your analysis. If more code is needed, "
                    "include it in a ```python block."
                ),
            })
        else:
            print(f"\n  [Reached max rounds for step {i}]")


# ---------------------------------------------------------------------------
# Chart download
# ---------------------------------------------------------------------------


def download_charts(runtime: Runtime, local_dir: str = LOCAL_CHARTS_DIR) -> None:
    """Download generated charts from the Agent Runtime to the local machine."""
    os.makedirs(local_dir, exist_ok=True)

    try:
        files = runtime.file.list(CHARTS_DIR).files
        chart_files = [f for f in files if f.name.endswith(".png")]

        if not chart_files:
            print("\nNo charts were generated.")
            return

        print(f"\nDownloading {len(chart_files)} chart(s) to ./{local_dir}/")
        for fi in chart_files:
            remote_path = f"{CHARTS_DIR}/{fi.name}"
            data = runtime.file.download_file(remote_path)
            local_path = os.path.join(local_dir, fi.name)
            with open(local_path, "wb") as f:
                f.write(data)
            print(f"  {local_path} ({len(data):,} bytes)")
    except Exception as e:
        print(f"\nFailed to download charts: {e}")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main():
    openai_key = os.environ.get("OPENAI_API_KEY")
    gravix_key = os.environ.get("GRAVIXLAYER_API_KEY")

    if not openai_key:
        print("Error: OPENAI_API_KEY environment variable is required.")
        sys.exit(1)
    if not gravix_key:
        print("Error: GRAVIXLAYER_API_KEY environment variable is required.")
        sys.exit(1)

    openai_client = OpenAI(
        api_key=openai_key,
        base_url=os.environ.get(
            "OPENAI_API_BASE_URL", "https://api.openai.com/v1"
        ),
    )

    print("Creating Agent Runtime...")

    with Runtime.create(
        template=python_runtime_template("python-3.14-base-medium"),
        timeout=int(os.getenv("GRAVIXLAYER_TIMEOUT", "600")),
    ) as runtime:
        print(f"Runtime ready: {runtime.runtime_id}")
        print(f"  CPU: {runtime.cpu_count}, Memory: {runtime.memory_mb}MB")

        # Install packages
        print("\nInstalling analysis packages...")
        install = runtime.run_cmd(
            "pip",
            args=["install", "pandas", "matplotlib", "seaborn", "numpy", "--quiet"],
        )
        if install.exit_code != 0:
            print(f"Package install failed: {install.stderr}")
            sys.exit(1)
        print("Packages installed.")

        # Download dataset
        print("\nDownloading dataset...")
        dl = runtime.run_code(
            f"import urllib.request, os\n"
            f"os.makedirs('/workspace', exist_ok=True)\n"
            f"urllib.request.urlretrieve('{DATASET_URL}', '{DATASET_PATH}')\n"
            f"size = os.path.getsize('{DATASET_PATH}')\n"
            f"print(f'Downloaded {{size:,}} bytes')"
        )
        if dl.stderr and "Error" in dl.stderr:
            print(f"Download failed: {dl.stderr}")
            sys.exit(1)
        print(dl.stdout.strip() if dl.stdout else "Dataset ready.")

        # Prepare runtime — ensure charts output directory exists
        runtime.file.create_directory(CHARTS_DIR, recursive=True)
        runtime.run_code("import matplotlib; matplotlib.use('Agg')")

        # Run analysis
        run_analysis(openai_client, runtime)
        tracker.analysis_end = time.perf_counter()

        # Download charts
        download_charts(runtime)

        # Print timing summary
        tracker.print_summary()

        print("\nDone. Runtime will be terminated automatically.")


if __name__ == "__main__":
    main()
