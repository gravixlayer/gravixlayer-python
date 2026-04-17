# Data Analyst Agent

An AI-powered data analyst that generates Python code using an LLM and executes it safely in an **isolated Gravix Layer Agent Runtime**. The agent iteratively analyzes a dataset, produces insights, and generates charts — all without running any code on your local machine.

Works with **OpenAI** out of the box. Also compatible with any OpenAI-compatible provider (Groq, Together AI, OpenRouter, etc.) by setting environment variables.

## How It Works

```
Question  ──>  LLM generates Python code
                     │
                     v
          Gravix Layer Agent Runtime executes code securely
                     │
                     v
          Output returned to LLM for interpretation
                     │
                     v
          Final analysis + charts downloaded locally
```

1. A secure, isolated Agent Runtime is created via the Gravix Layer SDK
2. The dataset is downloaded and packages are installed **inside the runtime**
3. For each analysis step the LLM writes Python code
4. The agent extracts the code, executes it via `runtime.run_code()`, and feeds the output back
5. The LLM interprets results or writes follow-up code (up to 5 rounds per step)
6. Charts are saved in the runtime and downloaded to your machine via `download_file()`

All code execution happens in the Gravix Layer runtime — nothing runs locally.

## Dataset

**Seaborn Diamonds** — 53,940 diamonds with 10 columns:

| Column | Description |
|--------|-------------|
| carat | Weight of the diamond |
| cut | Quality of the cut (Fair, Good, Very Good, Premium, Ideal) |
| color | Diamond color from D (best) to J (worst) |
| clarity | Clarity grade (IF, VVS1, VVS2, VS1, VS2, SI1, SI2, I1) |
| depth | Total depth percentage |
| table | Width of the top facet |
| price | Price in USD |
| x, y, z | Dimensions in mm |

Source: [seaborn-data/diamonds.csv](https://github.com/mwaskom/seaborn-data)

## Quick Start

```bash
cd examples/agents/python/data-analyst-agent
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Set your API keys:

Get a Gravix Layer API key at [gravixlayer.ai](https://gravixlayer.ai).

```bash
export OPENAI_API_KEY="your-openai-api-key"
export GRAVIXLAYER_API_KEY="your-gravixlayer-api-key"
```

Run:

```bash
python data_analyst_agent.py
```

### Using with Other Providers

This agent works with any OpenAI-compatible API. Set the base URL and model:

**Groq:**
```bash
export OPENAI_API_BASE_URL="https://api.groq.com/openai/v1"
export OPENAI_MODEL="llama-3.3-70b-versatile"
```

**Together AI:**
```bash
export OPENAI_API_BASE_URL="https://api.together.xyz/v1"
export OPENAI_MODEL="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"
```

**OpenRouter:**
```bash
export OPENAI_API_BASE_URL="https://openrouter.ai/api/v1"
export OPENAI_MODEL="meta-llama/llama-3.3-70b-instruct"
```

## Analysis Steps

| Step | What it does | Output |
|------|-------------|--------|
| 1 | Dataset overview (shape, dtypes, stats, unique values) | Text |
| 2 | Price distribution by cut quality | `charts/price_by_cut.png` |
| 3 | Carat vs price scatter colored by cut | `charts/carat_vs_price.png` |
| 4 | Average price by color and clarity | `charts/price_by_color_clarity.png` |
| 5 | Key insights summary | Text |

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | API key (OpenAI or compatible provider) |
| `GRAVIXLAYER_API_KEY` | Yes | — | Gravix Layer API key |
| `OPENAI_API_BASE_URL` | No | `https://api.openai.com/v1` | API base URL |
| `OPENAI_MODEL` | No | `gpt-4o` | Model name |
| `GRAVIXLAYER_TEMPLATE` | No | `python-3.14-base-medium` | Runtime template |
| `GRAVIXLAYER_TIMEOUT` | No | `600` | Runtime timeout in seconds |

## Project Structure

```
data-analyst-agent/
  data_analyst_agent.py   # Agent script
  requirements.txt        # Dependencies
  README.md
  charts/                 # Generated charts (created on run)
```
