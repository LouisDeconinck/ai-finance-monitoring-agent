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

# Create an agent for finding company URLs
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
        past_days = actor_input.get("past_days")
        
        today = datetime.now().strftime("%Y-%m-%d")
        relative_date_ago = (datetime.now() - timedelta(days=past_days)).strftime("%Y-%m-%d")
        
        # First fetch the Yahoo Finance data
        yahoo_data = await get_yahoo_finance_data(
            end_date=today,
            start_date=relative_date_ago,
            ticker=company_ticker
        )
        
        # Find LinkedIn and Crunchbase URLs
        Actor.log.info(f"Finding company profiles for {company_ticker}")
        company_urls_result = await company_finder.run(
            f"Find the LinkedIn company profile URL and Crunchbase URL for {company_ticker}"
        )
        
        urls_usage = company_urls_result.usage()
        await Actor.charge(event_name='1k-llm-tokens', count=math.ceil(urls_usage.total_tokens / 1000))
        
        # Fetch LinkedIn company profile
        linkedin_data = None
        if company_urls_result.data.linkedin_url:
            Actor.log.info(f"Found LinkedIn URL: {company_urls_result.data.linkedin_url}")
            linkedin_data = await get_linkedin_company_profile(
                linkedin_company_url=company_urls_result.data.linkedin_url
            )
        
        # Fetch Crunchbase company details
        crunchbase_data = None
        if company_urls_result.data.crunchbase_url:
            Actor.log.info(f"Found Crunchbase URL: {company_urls_result.data.crunchbase_url}")
            crunchbase_data = await get_crunchbase_company_details(
                crunchbase_company_url=company_urls_result.data.crunchbase_url
            )
        
        # Prepare additional context for the finance writer
        additional_context = ""
        
        if linkedin_data:
            additional_context += f"\n\nLinkedIn Company Data:\n{linkedin_data.model_dump_json()}"
        
        if crunchbase_data:
            additional_context += f"\n\nCrunchbase Company Data:\n{json.dumps(crunchbase_data)}"
        
        # Then use the agent to generate the report using all collected data
        result = await finance_writer.run(
            f'Generate a market report for "{company_ticker}" based on the following data:\n\n'
            f'Yahoo Finance Data:\n{yahoo_data.model_dump_json()}'
            f'{additional_context}'
        )  
        
        usage = result.usage()
        await Actor.charge(event_name='1k-llm-tokens', count=math.ceil(usage.total_tokens / 1000))
        
        # Store the markdown report in the key-value store
        try:
            default_store = await Actor.open_key_value_store()
            report_key = f"market_report_{company_ticker}_{relative_date_ago}_{today}.md"
            await default_store.set_value(
                report_key, 
                result.data.report, 
                content_type="text/markdown"
            )
        except Exception as e:
            Actor.log.warning(f"Failed to store market report: {str(e)}")
        
        # Combine all data with the report
        output_data = {
            **yahoo_data.model_dump(),
            "report": result.data.report,
        }
        
        # Add LinkedIn data if available
        if linkedin_data:
            output_data["linkedin_data"] = linkedin_data.model_dump()
            
        # Add Crunchbase data if available
        if crunchbase_data:
            output_data["crunchbase_data"] = crunchbase_data
        
        await Actor.push_data(output_data)