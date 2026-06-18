# Impact Radar

Impact Radar is a Software Change Impact Analysis Platform designed to help developers and testers understand the consequences of modifying a software module before deployment.

## Features

* Project Management
* Module Dependency Mapping
* ZIP Project Upload
* Python Dependency Scanning
* Impact Analysis
* Risk Assessment
* Dependency Graph Visualization
* Impact Report Generation

## Technology Stack

* Python
* Streamlit
* Graphviz
* JSON

## Installation

```bash
git clone <repository-url>
cd impact_radar_ui

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

streamlit run app4.py
```

## How It Works

1. Create or import a project.
2. Define module dependencies.
3. Select a changed module.
4. Run impact analysis.
5. View affected modules and risk level.
6. Generate impact reports.

## Risk Levels

| Impact Ratio | Risk Level |
| ------------ | ---------- |
| < 25%        | LOW        |
| 25% - 49%    | MEDIUM     |
| >= 50%       | HIGH       |

## Future Enhancements

* Java Support
* Spring Boot Analysis
* PDF Reports
* Git Integration
* Historical Reports
* AI-Based Risk Prediction

## Author

Joanna
