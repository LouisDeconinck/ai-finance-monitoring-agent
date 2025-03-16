from apify import Actor
from .models import YahooFinanceData, YahooFinanceSummaryDetail, YahooFinancePrice, YahooFinanceQuote, YahooFinanceNews, LinkedInData
from apify_client import ApifyClient
from typing import List, Optional
from pydantic_ai import RunContext

# Create a global client that will be set during initialization
_client: Optional[ApifyClient] = None

def set_client(client: ApifyClient) -> None:
    """Set the global ApifyClient instance."""
    global _client
    _client = client

async def get_yahoo_finance_data(end_date: str, start_date: str, ticker: str) -> YahooFinanceData:
    """Get Yahoo Finance data for a given ticker and date range.
    
    Args:
        end_date: The end date of the data to retrieve. Format: YYYY-MM-DD
        start_date: The start date of the data to retrieve. Format: YYYY-MM-DD
        ticker: The ticker of the company to retrieve data for
        
    Returns:
        YahooFinanceData object containing the processed data
    """
    if not _client:
        raise ValueError("ApifyClient not initialized. Call set_client first.")
        
    Actor.log.info(f"Getting Yahoo Finance data for: {ticker} ({end_date} - {start_date})")
    run_input = {
        "endDate": end_date,
        "startDate": start_date,
        "ticker": ticker
    }
    run = _client.actor("harvest/yahoo-finance-scraper").call(run_input=run_input, memory_mbytes=128)
    
    # Get the raw items from the dataset
    list_page = _client.dataset(run["defaultDatasetId"]).list_items()
    
    if not list_page.items:
        raise ValueError(f"No data found for ticker {ticker}")
        
    # Get the first item which contains all the data
    data = list_page.items[0]
    
    # Process the data into our models
    summary_detail = YahooFinanceSummaryDetail(
        previous_close=data["results"]["summaryDetail"]["previousClose"],
        open=data["results"]["summaryDetail"]["open"],
        day_low=data["results"]["summaryDetail"]["dayLow"],
        day_high=data["results"]["summaryDetail"]["dayHigh"],
        volume=data["results"]["summaryDetail"]["volume"],
        average_volume=data["results"]["summaryDetail"]["averageVolume"],
        market_cap=data["results"]["summaryDetail"]["marketCap"],
        fifty_two_week_low=data["results"]["summaryDetail"]["fiftyTwoWeekLow"],
        fifty_two_week_high=data["results"]["summaryDetail"]["fiftyTwoWeekHigh"],
        price_to_sales_trailing_12_months=data["results"]["summaryDetail"]["priceToSalesTrailing12Months"],
        fifty_day_average=data["results"]["summaryDetail"]["fiftyDayAverage"],
        two_hundred_day_average=data["results"]["summaryDetail"]["twoHundredDayAverage"],
        trailing_pe=data["results"]["summaryDetail"]["trailingPE"],
        forward_pe=data["results"]["summaryDetail"]["forwardPE"],
        dividend_rate=data["results"]["summaryDetail"]["dividendRate"],
        dividend_yield=data["results"]["summaryDetail"]["dividendYield"],
        payout_ratio=data["results"]["summaryDetail"]["payoutRatio"],
        beta=data["results"]["summaryDetail"]["beta"]
    )
    
    price = YahooFinancePrice(
        regular_market_price=data["results"]["price"]["regularMarketPrice"],
        regular_market_change=data["results"]["price"]["regularMarketChange"],
        regular_market_change_percent=data["results"]["price"]["regularMarketChangePercent"],
        regular_market_time=data["results"]["price"]["regularMarketTime"],
        regular_market_volume=data["results"]["price"]["regularMarketVolume"],
        regular_market_day_high=data["results"]["price"]["regularMarketDayHigh"],
        regular_market_day_low=data["results"]["price"]["regularMarketDayLow"],
        regular_market_previous_close=data["results"]["price"]["regularMarketPreviousClose"],
        regular_market_open=data["results"]["price"]["regularMarketOpen"],
        exchange=data["results"]["price"]["exchange"],
        exchange_name=data["results"]["price"]["exchangeName"],
        market_state=data["results"]["price"]["marketState"],
        quote_type=data["results"]["price"]["quoteType"],
        symbol=data["results"]["price"]["symbol"],
        short_name=data["results"]["price"]["shortName"],
        long_name=data["results"]["price"]["longName"],
        currency=data["results"]["price"]["currency"],
        market_cap=data["results"]["price"]["marketCap"]
    )
    
    quotes = [
        YahooFinanceQuote(
            date=quote["date"],
            high=quote["high"],
            volume=quote["volume"],
            open=quote["open"],
            low=quote["low"],
            close=quote["close"],
            adjclose=quote["adjclose"]
        )
        for quote in data["chart"]["quotes"]
    ]
    
    news = [
        YahooFinanceNews(
            uuid=item["uuid"],
            title=item["title"],
            publisher=item["publisher"],
            link=item["link"],
            provider_publish_time=item["providerPublishTime"],
            type=item["type"],
            related_tickers=item["relatedTickers"]
        )
        for item in data["news"]
    ]
    
    # Create the final data object
    yahoo_data = YahooFinanceData(
        summary_detail=summary_detail,
        price=price,
        quotes=quotes,
        news=news,
        ticker=ticker,
        start_date=start_date,
        end_date=end_date
    )
    
    # Store the data in the key-value store
    try:
        default_store = await Actor.open_key_value_store()
        kv_key = f"yahoo_finance_{ticker}_{start_date}_{end_date}"
        await default_store.set_value(kv_key, yahoo_data.model_dump())
    except Exception as e:
        Actor.log.warning(f"Failed to store Yahoo Finance data: {str(e)}")
    
    Actor.log.info(f"Successfully processed Yahoo Finance data for: {ticker}. Extracted {len(news)} news items and {len(quotes)} quotes.")
    await Actor.charge('tool_result', 1)
    return yahoo_data 

async def get_linkedin_company_profile(
    linkedin_company_url: str
) -> LinkedInData:
    """Get LinkedIn company profile.

    Args:
        linkedin_company_url: The LinkedIn company URL. E.g. https://www.linkedin.com/company/apple/

    Returns:
        A LinkedInData object containing company details from LinkedIn.
    """
    if not _client:
        raise ValueError("ApifyClient not initialized. Call set_client first.")
        
    Actor.log.info(f"Getting LinkedIn company profile for: {linkedin_company_url}")
    run_input = {
        "linkedinUrls": [linkedin_company_url]
    }

    try:
        run = _client.actor("icypeas_official/linkedin-company-scraper").call(run_input=run_input, memory_mbytes=128)
        dataset = _client.dataset(run["defaultDatasetId"]).list_items()

        if dataset.items and len(dataset.items) > 0:
            Actor.log.info(f"LinkedIn company profile retrieved for {linkedin_company_url}")
            item = dataset.items[0]['data'][0]['result']
            
            # Format address if it's a dictionary
            address = item.get("address")
            if isinstance(address, dict):
                address_parts = []
                if address.get("streetAddress"):
                    address_parts.append(address.get("streetAddress"))
                if address.get("addressLocality"):
                    address_parts.append(address.get("addressLocality"))
                if address.get("addressRegion"):
                    address_parts.append(address.get("addressRegion"))
                if address.get("postalCode"):
                    address_parts.append(address.get("postalCode"))
                if address.get("addressCountry"):
                    address_parts.append(address.get("addressCountry"))
                address = ", ".join([part for part in address_parts if part])
            
            # Create and return a LinkedInData model instance
            return LinkedInData(
                name=item.get("name"),
                description=item.get("description"),
                industry=item.get("industry"),
                employees=item.get("numberOfEmployees"),
                website=item.get("website"),
                specialties=[s["value"] for s in item.get("specialties", [])],
                address=address
            )
        await Actor.charge('tool_result', 1)
        return LinkedInData()

    except Exception as e:
        Actor.log.error(f"Error fetching LinkedIn company profile: {str(e)}")
        return LinkedInData() 
    
    
async def search_google(ctx: RunContext, query: str, max_results: int = 1) -> List[str]:
    """Search Google for the given query and return the results as a list of strings. 
    
    Args:
        ctx: The run context containing dependencies
        query: The query to search for. You can use the site: operator to search for a specific site. E.g. "site:linkedin.com {query}"
        max_results: The maximum number of results to return
        
    Returns:
        A list of strings containing the search results
    """
    if not _client:
        raise ValueError("ApifyClient not initialized. Call set_client first.")
        
    max_results = min(max_results, 10)
    Actor.log.info(f"Searching Google for: {query} ({max_results} results)")
    run_input = {
        "query": query,
        "maxResults": max_results,
        "outputFormats": ["markdown"],
    }
    run = _client.actor("apify/rag-web-browser").call(run_input=run_input, memory_mbytes=1024)
    
    # Get the raw items from ListPage and convert to list of strings
    list_page = _client.dataset(run["defaultDatasetId"]).list_items()
    results = []
    
    for item in list_page.items:
        if not isinstance(item, dict):
            continue
            
        # Create a formatted result with the most useful information
        formatted_result = ""
        
        # Add title and URL if available
        if "searchResult" in item and isinstance(item["searchResult"], dict):
            if "title" in item["searchResult"]:
                formatted_result += f"# {item['searchResult']['title']}\n\n"
            if "url" in item["searchResult"]:
                formatted_result += f"URL: {item['searchResult']['url']}\n\n"
            if "description" in item["searchResult"]:
                formatted_result += f"Description: {item['searchResult']['description']}\n\n"
        
        # Add the markdown content (most useful part) if available
        if "markdown" in item and item["markdown"]:
            markdown_content = item["markdown"]
            
            formatted_result += f"Content:\n{markdown_content}\n"
        
        if formatted_result:
            results.append(formatted_result)
            
    Actor.log.info(f"Found {len(results)}/{max_results} search results for: {query}")
    await Actor.charge('tool_result', len(results))
    return results 


async def get_crunchbase_company_details(crunchbase_company_url: str) -> List[str]:
    """Get Crunchbase company details for the given query and return the results as a list of strings.
    
    Args:
        crunchbase_company_url: The Crunchbase company URL. E.g. https://www.crunchbase.com/organization/apple
        
    Returns:
        A list of strings containing the Crunchbase company details
    """
    if not _client:
        raise ValueError("ApifyClient not initialized. Call set_client first.")
        
    Actor.log.info(f"Getting Crunchbase company details for: {crunchbase_company_url}")
    run_input = {
        "crunchbaseUrl": crunchbase_company_url
    }
    run = _client.actor("harvest/crunchbase-company-details-scraper").call(run_input=run_input, memory_mbytes=256)
    
    # Get the raw items from ListPage and convert to list of strings
    list_page = _client.dataset(run["defaultDatasetId"]).list_items()
    
    # Since there will always be only one result, directly return it
    if list_page.items:
        result = list_page.items[0]
        Actor.log.info(f"Retrieved Crunchbase data for: {crunchbase_company_url}")
        await Actor.charge('tool_result', 1)
        return [result]
    else:
        Actor.log.warning(f"No data found for Crunchbase URL: {crunchbase_company_url}")
        await Actor.charge('tool_result', 0)
        return []
