# 7alelhaLak | حللهالك
## Your AI Business Copilot

**Turn business data into smarter decisions and actions.**

7alelhaLak is an AI-powered business analytics platform designed to help small and medium-sized business owners understand their data, discover problems and opportunities, and make better decisions without requiring advanced data-analysis skills.

Developed for the **CREATIVA × Replit vibe-coding hackathon**.

> **Current status:** Initial repository scaffold. The features described below are planned for the MVP and must not be treated as implemented until verified in the code.

---

## 1. The Problem

Small businesses, including retail shops, restaurants, and e-commerce stores, collect sales, product, customer, and inventory data but often lack the tools or expertise to interpret it.

Business owners need answers to questions such as:

- Why did sales decrease this month?
- Which products generate the most profit?
- Which products sell frequently but have weak profit margins?
- Are there products with declining sales or low stock?
- What actions could improve business performance?
- What might happen if prices or inventory levels change?

Traditional dashboards display numbers and charts, but business owners may still need an analyst to explain the results and determine the next steps.

**The core problem:** Businesses have data, but they do not always have clear answers about what is happening, why it may be happening, and what they should do next.

## 2. Our Solution

7alelhaLak combines data analytics with an AI Business Analyst.

Users upload business data in CSV or Excel format. The application validates the data, calculates business metrics, visualizes performance, identifies notable patterns, and lets users ask questions in Arabic or English.

The AI interprets calculated metrics and supporting evidence to provide understandable explanations and practical recommendations.

Our goal is to move beyond reporting what happened toward helping business owners understand their results and choose their next actions.

## 3. MVP Features

### 3.1 Data Upload and Validation

- Accept CSV and Excel files.
- Inspect column names and data types.
- Map common column names to a supported schema where possible.
- Detect missing required fields, invalid values, and unusable datasets.
- Display understandable validation errors instead of crashing.
- Analyze uploaded datasets without requiring database persistence.

### 3.2 Interactive Business Dashboard

Display relevant metrics and charts based on available data:

- Total revenue.
- Total profit and profit margin, when cost data is available.
- Units sold.
- Sales trends over time.
- Best-selling products by quantity or revenue.
- Most profitable products.
- Product-level performance comparisons.
- Inventory warnings when appropriate inventory data is available.

### 3.3 AI Business Analyst

Users can ask questions in Arabic or English, such as:

- "Why did sales decrease?"
- "Which product generates the most profit?"
- "What are the biggest problems in my business?"
- "What should I investigate first?"
- "ليه المبيعات قلت الشهر ده؟"
- "إيه أكتر منتج بيحقق ربح؟"

AI responses should distinguish between:

- **Finding:** What the data shows.
- **Evidence:** Metrics and comparisons supporting the finding.
- **Possible explanation:** A hypothesis that may explain the result.
- **Recommendation:** A practical next step.
- **Limitation:** What the available data cannot establish.

### 3.4 Automatic Insights and Recommendations

Identify useful patterns, including:

- Significant increases or decreases in revenue.
- Products with declining sales.
- High-revenue products with weak profit margins.
- Products that contribute significantly to total profit.
- Potential inventory problems when inventory data exists.

Recommendations must be relevant to the evidence and must not present unsupported assumptions as facts.

## 4. Features Outside the Initial MVP

Do not implement these until the core workflow works reliably:

- User authentication and account management.
- Multi-tenant data isolation.
- Persistent database storage.
- Complex joins across multiple uploaded files.
- Predictive forecasting and additional ML pipelines.
- What-if simulation.
- Automated marketing campaigns.
- n8n integrations and scheduled workflows.
- Multi-agent AI architectures.
- Production-scale infrastructure.

These are possible future extensions, not initial requirements.

## 5. Technology Stack

| Component | Technology | Responsibility |
|---|---|---|
| UI | Streamlit | Upload, dashboard, chat, insights |
| Data processing | Python and Pandas | Validation, aggregation, KPI calculations |
| Charts | Plotly | Interactive visualizations |
| Excel support | OpenPyXL | Reading `.xlsx` files |
| AI | LLM API and provider SDK | Question answering and recommendations |
| Version control | Git and GitHub | Collaboration and code history |
| Development and demo | Replit | Hackathon development support and demonstration |

The specific LLM provider and model have not been finalized. Confirm the choice before adding provider-specific dependencies.

The initial architecture favors a single Streamlit application without a separate backend service or database unless a concrete requirement justifies the added complexity.

## 6. Project Structure

```text
7alelhaLak/
├── app.py
├── analytics.py
├── data_loader.py
├── dashboard.py
├── ai_analyst.py
├── insights.py
├── requirements.txt
├── .gitignore
├── README.md
└── sample_data/
    └── sales.csv
```
File Responsibilities
FileResponsibility
app.pyStreamlit entry point and application integration
data_loader.pyFile parsing, schema mapping, and validation
analytics.pyDeterministic KPIs, trends, and product calculations
dashboard.pyKPI cards, charts, tables, and visual presentation
ai_analyst.pyLLM integration and business question answering
insights.pyInsight generation and business recommendations
requirements.txtPython dependencies
sample_data/sales.csvFictional development and demonstration dataset
This is the intended separation of responsibilities. Adjust it only when there is a concrete reason; avoid unnecessary restructuring during the hackathon.

## 7. Initial Data Schema
The demonstration dataset uses these columns:
ColumnTypePurpose
dateDateTransaction or sales date
productStringProduct name or identifier
quantityNumericUnits sold
unit_priceNumericSelling price per unit
unit_costNumericCost per unit
The included sample dataset is fictional and intended for development and demonstration only.
KPI Definitions
For each valid transaction:
- Revenue = quantity * unit_price
- Cost = quantity * unit_cost
- Profit = revenue - cost
For the complete dataset:
- Total revenue: Sum of transaction revenue.
- Total cost: Sum of transaction cost.
- Total profit: Total revenue minus total cost.
- Profit margin: Total profit divided by total revenue, multiplied by 100, when revenue is nonzero.
- Units sold: Sum of quantity.
- Best-selling product: Product with the highest aggregated quantity sold.
- Most profitable product: Product with the highest aggregated profit.
These definitions assume valid sales transactions and meaningful prices and costs. Returns, discounts, taxes, shipping, and other accounting adjustments must be handled explicitly if present.
Do not calculate profit when required cost information is unavailable. Show it as unavailable rather than inventing a value.
Sales history alone cannot establish current inventory levels or confirm stockouts. Inventory analysis requires appropriate inventory data.

## 8. Architecture and Data Flow
```
User uploads CSV or Excel
          |
          v
    Data validation
          |
          v
  Normalized DataFrame
          |
          v
  Deterministic analytics
          |
          +---------------------+
          |                     |
          v                     v
Interactive dashboard      Computed metrics
                                |
                                v
                           LLM analysis
                                |
                                v
                     Evidence and recommendations
```

## Core Engineering Principle
Python is responsible for numerical correctness; the LLM is responsible for interpretation and explanation.
The LLM must not independently invent or recalculate financial totals when authoritative calculated values are available.
Provide only the relevant metrics and supporting product-level or time-series summaries needed to answer a question. Avoid sending the entire dataset to the LLM by default.


## 9. Team Responsibilities
This is a two-person hackathon project.

Abanoub — Product, Analytics, Dashboard, and Integration
Primary responsibilities:
- Data ingestion and validation.
- Pandas calculations and KPI definitions.
- Dashboard and interactive charts.
- Application entry point and integration.
- End-to-end testing and demo readiness.
Primary files:
- app.py
- data_loader.py
- analytics.py
- dashboard.py

Mohamed — AI and Business Insights
Primary responsibilities:
- LLM provider integration.
- Business question answering.
- AI interpretation of calculated metrics.
- Automatic insights and recommendations.
- Response validation and graceful API failure handling.
Primary files:
- ai_analyst.py
- insights.py

Both developers must coordinate changes to shared contracts and dependencies.

## 10. Shared Interface Contract
Agree on function signatures and data structures before integrating independently developed components.
Proposed interfaces:
# analytics.pydef analyze_sales(df) -> dict:    ...# insights.pydef generate_insights(metrics: dict) -> dict:    ...# ai_analyst.pydef answer_business_question(    question: str,    metrics: dict,    language: str = "auto",) -> dict:    ...



These are proposed interfaces, not implemented functions.
The metrics dictionary should contain clearly defined calculated values, relevant product-level summaries, trend information, and data-quality warnings. Its exact keys and types must be agreed upon by both developers.
AI responses should use a predictable structure containing findings, evidence, recommendations, and limitations. Validate the response before displaying it.

## 11. Git and Collaboration Rules
GitHub is the shared source of truth for code.
- Use separate feature branches for parallel development.
- Keep commits small and focused.
- Push working changes frequently.
- Integrate and test components early.
- Coordinate modifications to app.py, requirements.txt, and shared interfaces.
- Do not overwrite another developer's changes without coordination.
- Never commit API keys, credentials, .env files, or private business data.
- Inspect the actual code before claiming a feature is implemented.
- Avoid unnecessary dependencies and architectural changes.
- Prioritize a complete, reliable demo over unfinished features.

## 12. Instructions for AI Coding Assistants
Any AI model or coding agent working on this repository must:
1. Read this README and inspect the actual repository before making changes.
2. Distinguish planned features from implemented and tested functionality.
3. Respect file responsibilities and agreed interfaces.
4. Keep financial calculations deterministic and testable.
5. Never fabricate business metrics, evidence, or causal explanations.
6. Validate uploads and handle empty datasets, missing columns, invalid values, and zero denominators.
7. Handle LLM timeouts, API errors, malformed responses, and missing configuration gracefully.
8. Never hardcode API keys or expose secrets in logs or responses.
9. Validate AI-generated content before rendering it.
10. Avoid unnecessary services, dependencies, databases, and architectural complexity.
11. Do not modify unrelated files or overwrite another developer's work.
12. Do not claim tests passed unless they were actually executed and their results inspected.
13. Prefer the smallest reliable implementation that advances the MVP.
Before implementing a feature, inspect the current code and its dependencies. Make focused changes, validate the result, and report the files changed and tests actually performed.

## 13. Running the Application
The repository currently contains the initial project scaffold. The application entry point and feature modules must be implemented before the complete MVP can run.

Create and activate a virtual environment:
python -m venv .venv
.\.venv\Scripts\Activate.ps1


Install dependencies:
python -m pip install -r requirements.txt


After implementing the Streamlit entry point:
python -m streamlit run app.py


Configure any required LLM API key through local environment configuration or Replit Secrets. Never commit the actual secret to GitHub.

## 14. Security, Privacy, and Reliability
Even for a hackathon prototype:
- Treat uploaded files as untrusted input.
- Validate file types, required columns, data types, and file sizes.
- Never execute uploaded content as code.
- Avoid logging raw customer records or sensitive business information.
- Never expose API keys in frontend code or error messages.
- Validate LLM responses before rendering them.
- Distinguish observed data from hypotheses.
- Handle invalid files and API failures without crashing the application.
- Do not imply that recommendations guarantee business outcomes.
The prototype demonstrates business analytics and decision support; it does not replace professional accounting or guarantee business results.

## 15. Judge-Facing Demo
The intended demonstration flow is:
1. Upload a sample business sales dataset.
2. View revenue, profit, sales trends, and product performance.
3. Ask a business question in Arabic or English.
4. Review the evidence behind the AI answer.
5. Receive a practical recommendation based on the available data.
Core value proposition: 7alelhaLak transforms business data into understandable findings and actionable decisions.
Vision
Build an AI Business Copilot that helps business owners understand what happened, investigate why it may have happened, explore their options, and decide what to do next.
