from apify import Actor
from apify_client import ApifyClient
import os
from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext, Tool
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.settings import ModelSettings
from datetime import datetime, timedelta
import math
import json
import asyncio

from .prompts import FINANCE_WRITER_SYSTEM_PROMPT, COMPANY_FINDER_SYSTEM_PROMPT
from .models import ReportInfo, CompanyLinks
from .tools import get_yahoo_finance_data, search_google, get_linkedin_company_profile, get_crunchbase_company_details, set_client

load_dotenv()

apify_api_key = os.getenv("APIFY_API_KEY")
client = ApifyClient(apify_api_key)
set_client(client)  # Set the global client in tools.py

api_key = os.getenv("GEMINI_API_KEY")
model = GeminiModel('gemini-2.0-flash', provider='google-gla', api_key=api_key)
finance_writer = Agent(
    model,
    system_prompt = FINANCE_WRITER_SYSTEM_PROMPT,
    result_type=ReportInfo,
    model_settings=ModelSettings(temperature=0),
)

# Create an agent for finding company URLs and sector index
company_finder = Agent(
    model,
    system_prompt = COMPANY_FINDER_SYSTEM_PROMPT,
    result_type=CompanyLinks,
    model_settings=ModelSettings(temperature=0),
    tools=[Tool(search_google)],
)

# Register the search_google tool for the company_finder agent
@company_finder.tool()
async def search_company_info(ctx: RunContext, query: str) -> str:
    """Search Google for company information"""
    results = await search_google(ctx=ctx, query=query, max_results=3)
    return json.dumps(results)

async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() 
        
        await Actor.charge('init', 1)
        
        company_ticker = actor_input.get("company_ticker")
        past_days = actor_input.get("past_days", 30)  # Default to 30 days
        
        # Calculate proper date range using past dates
        now = datetime.now()
        end_date = now.strftime("%Y-%m-%d")
        start_date = (now - timedelta(days=past_days)).strftime("%Y-%m-%d")
        
        Actor.log.info(f"Date range: {start_date} to {end_date} ({past_days} days)")
        
        # Step 1: Find company profiles and sector index in one call
        Actor.log.info(f"Finding company profiles and sector index for {company_ticker}")
        
        company_info_result = await company_finder.run(
            f"Find the LinkedIn company profile URL, Crunchbase URL, and sector-specific index ticker for {company_ticker}"
        )
        
        # Charge for token usage
        usage = company_info_result.usage()
        await Actor.charge(event_name='1k-llm-tokens', count=math.ceil(usage.total_tokens / 1000))
        
        # Get the LinkedIn and Crunchbase URLs
        linkedin_url = company_info_result.data.linkedin_url
        crunchbase_url = company_info_result.data.crunchbase_url
        
        # Get the sector index ticker (default to ^GSPC if not found)
        sector_index = company_info_result.data.sector_index
        
        Actor.log.info(f"Found LinkedIn URL: {linkedin_url}")
        Actor.log.info(f"Found Crunchbase URL: {crunchbase_url}")
        Actor.log.info(f"Found sector index: {sector_index}")
        
        # Step 2: Fetch all data in parallel
        Actor.log.info(f"Fetching all data in parallel for {company_ticker}")
        
        # Create tasks for all data fetching operations
        tasks = [
            # Yahoo Finance data for company
            get_yahoo_finance_data(
                end_date=end_date,
                start_date=start_date,
                ticker=company_ticker
            ),
            # Yahoo Finance data for S&P 500
            get_yahoo_finance_data(
                end_date=end_date,
                start_date=start_date,
                ticker="^GSPC"
            )
        ]
        
        # Add sector index task if available
        if sector_index:
            tasks.append(
                get_yahoo_finance_data(
                    end_date=end_date,
                    start_date=start_date,
                    ticker=sector_index
                )
            )
        
        # Add LinkedIn and Crunchbase tasks if URLs are available
        linkedin_task = None
        crunchbase_task = None
        
        if linkedin_url:
            linkedin_task = get_linkedin_company_profile(
                linkedin_company_url=linkedin_url
            )
            tasks.append(linkedin_task)
        
        if crunchbase_url:
            crunchbase_task = get_crunchbase_company_details(
                crunchbase_company_url=crunchbase_url
            )
            tasks.append(crunchbase_task)
        
        # Run all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Extract results, handling potential exceptions
        company_data = None
        sp500_data = None
        sector_data = None
        linkedin_data = None
        crunchbase_data = None
        
        # Process results and handle any exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                Actor.log.error(f"Error in task {i}: {str(result)}")
                continue
                
            if i == 0:
                company_data = result
            elif i == 1:
                sp500_data = result
            elif i == 2:
                sector_data = result
            elif i == 3 and linkedin_task:
                linkedin_data = result
            elif i == 3 and crunchbase_task and not linkedin_task:
                crunchbase_data = result
            elif i == 4 and linkedin_task and crunchbase_task:
                crunchbase_data = result
        
        # Check if we have company data (the absolute minimum required)
        if not company_data:
            Actor.log.error("Missing company data, cannot generate report")
            return
            
        # Use empty data objects if indices data is missing
        if not sp500_data:
            Actor.log.warning("Missing S&P 500 data, using default values")
            sp500_data = await get_yahoo_finance_data(
                end_date=end_date,
                start_date=start_date,
                ticker="^GSPC"
            )
            
        if not sector_data:
            Actor.log.warning(f"Missing sector index data for {sector_index}, using default values")
            sector_data = await get_yahoo_finance_data(
                end_date=end_date,
                start_date=start_date,
                ticker=sector_index
            )
        
        # Step 3: Generate the report using all collected data
        # Prepare additional context for the finance writer
        additional_context = "\n\nS&P 500 Comparison Data:\n"
        additional_context += sp500_data.model_dump_json()
        
        additional_context += f"\n\nSector Index ({sector_index}) Comparison Data:\n"
        additional_context += sector_data.model_dump_json()
        
        if linkedin_data:
            additional_context += f"\n\nLinkedIn Company Data:\n{linkedin_data.model_dump_json()}"
        
        if crunchbase_data:
            additional_context += f"\n\nCrunchbase Company Data:\n{json.dumps(crunchbase_data)}"
        
        # Generate the comprehensive market report
        Actor.log.info(f"Generating comprehensive market report for {company_ticker}")
        result = await finance_writer.run(
            f'Generate a market report for "{company_ticker}" based on the following data:\n\n'
            f'Yahoo Finance Data:\n{company_data.model_dump_json()}'
            f'{additional_context}'
        )  
        
        usage = result.usage()
        await Actor.charge(event_name='1k-llm-tokens', count=math.ceil(usage.total_tokens / 1000))
        
        # Store the markdown report in the key-value store
        try:
            default_store = await Actor.open_key_value_store()
            report_key = f"market_report_{company_ticker}_{start_date}_{end_date}.md"
            await default_store.set_value(
                report_key, 
                result.data.report, 
                content_type="text/markdown"
            )
        except Exception as e:
            Actor.log.warning(f"Failed to store market report: {str(e)}")
        
        # Combine all data with the report
        output_data = {
            **company_data.model_dump(),
            "report": result.data.report,
        }
        
        # Add index data if available
        if sp500_data:
            output_data["sp500_data"] = sp500_data.model_dump()
            
        if sector_data:
            output_data["sector_data"] = sector_data.model_dump()
        
        # Add LinkedIn data if available
        if linkedin_data:
            output_data["linkedin_data"] = linkedin_data.model_dump()
            
        # Add Crunchbase data if available
        if crunchbase_data:
            output_data["crunchbase_data"] = crunchbase_data
        
        await Actor.push_data(output_data)