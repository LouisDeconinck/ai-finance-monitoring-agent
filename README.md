A powerful AI-driven financial research and monitoring tool built on the Apify platform. This agent automatically generates comprehensive financial analysis reports for publicly traded companies by aggregating data from multiple sources and using AI to synthesize insights.

## Overview

The AI Finance Monitoring Agent collects data from various financial and business intelligence sources to create detailed financial analysis reports for any publicly traded company. It leverages AI to transform raw financial data into actionable investment insights, comparative market analysis, and performance evaluations.

## Features

- **Automated Financial Research**: Generate comprehensive market reports for any publicly traded company using just the ticker symbol
- **Multi-Source Data Aggregation**: Collects and synthesizes data from:
  - Yahoo Finance (stock prices, market metrics, financial ratios)
  - LinkedIn company profiles (company information, employee count, specialties)
  - Crunchbase (funding information, investors, business details)
  - Sector-specific index data for comparative analysis
  - S&P 500 benchmark data
- **Comparative Market Analysis**: Automatically compares company performance against sector indices and the S&P 500
- **AI-Powered Report Generation**: Uses Google's Gemini 2.0 Flash model to synthesize collected data into readable, insightful reports
- **Historical Analysis**: Analyze performance over customizable timeframes (1-365 days)
- **Exportable Results**: Reports generated in Markdown format for easy integration into research workflows

## Input

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `company_ticker` | String | Stock ticker symbol of the company to analyze | Required |
| `past_days` | Integer | Number of past days to analyze (1-365) | 7 |

Example input:
```json
{
  "company_ticker": "AAPL",
  "past_days": 30
}
```

## How It Works

1. **Data Collection**: The agent collects financial data from Yahoo Finance, LinkedIn, and Crunchbase for the specified company
2. **Index Analysis**: Retrieves relevant sector index data and S&P 500 data for comparative analysis
3. **AI Processing**: Utilizes Gemini 2.0 Flash to analyze the collected data and generate insights
4. **Report Generation**: Creates a detailed markdown report with financial analysis, market trends, and comparative performance
5. **Storage**: Saves the report to the Apify key-value store and pushes structured data to the dataset

## Output Format

The agent produces two outputs:

1. **Markdown Report**: A comprehensive financial analysis report saved in the key-value store
2. **Structured Data**: A JSON object with all collected and analyzed data pushed to the dataset

## Dependencies

- `apify` & `apify-client`: For integration with the Apify platform
- `pydantic-ai`: For AI model integration and structured data handling
- `python-dotenv`: For environment variable management
- `pydantic`: For data validation and settings management

## License

This project is licensed under the MIT License.