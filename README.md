# app-hackathon26

Brief description of what this project does and why it exists.

## Features

- Dynamic wanted description extraction: Automatically parses FBI suspect descriptions and highlights key allegations by extracting sentences containing terms such as wanted, alleged, and charged, while preventing duplicate clues from overlapping keywords in the same sentence.

## Requirements

- Python 3.14.7

## Installation

Clone the repository:

```bash
git clone https://github.com/karl-johansson1/app-hackathon26.git
cd app-hackathon26
```

Create and activate a virtual environment:

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the application:

```bash
python test.py
```

## Project Structure

```text
app-hackathon26/
├── .venv/
├── test.py
└── README.md
```

## Development

Run tests:

```bash
pytest
```

Format code:

```bash
black .
