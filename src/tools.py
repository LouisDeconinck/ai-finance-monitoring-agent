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
        end_date: The end date in YYYY-MM-DD format
        start_date: The start date in YYYY-MM-DD format
        ticker: The ticker symbol to get data for
        
    Returns:
        A YahooFinanceData object containing the data
    """
    if not _client:
        raise ValueError("ApifyClient not initialized. Call set_client first.")
        
    Actor.log.info(f"Getting Yahoo Finance data for: {ticker} ({start_date} to {end_date})")
    
    # Check if ticker is an index (starts with ^)
    is_index = ticker.startswith("^")
    
    run_input = {
        "endDate": end_date,
        "startDate": start_date,
        "ticker": ticker
    }
    
    try:
        run = _client.actor("harvest/yahoo-finance-scraper").call(run_input=run_input, memory_mbytes=128)
        list_page = _client.dataset(run["defaultDatasetId"]).list_items()
        if not list_page.items:
            raise ValueError(f"No data found for {ticker}")
        data = list_page.items[0]
        
        # Process the data into our models
        summary_detail_data = data["results"]["summaryDetail"]
        
        # Use default values for fields that might be missing in indices
        summary_detail = YahooFinanceSummaryDetail(
            previous_close=summary_detail_data.get("previousClose", 0.0),
            open=summary_detail_data.get("open", 0.0),
            day_low=summary_detail_data.get("dayLow", 0.0),
            day_high=summary_detail_data.get("dayHigh", 0.0),
            volume=summary_detail_data.get("volume", 0),
            average_volume=summary_detail_data.get("averageVolume", 0),
            market_cap=summary_detail_data.get("marketCap", 0.0) if not is_index else 0.0,
            fifty_two_week_low=summary_detail_data.get("fiftyTwoWeekLow", 0.0),
            fifty_two_week_high=summary_detail_data.get("fiftyTwoWeekHigh", 0.0),
            price_to_sales_trailing_12_months=summary_detail_data.get("priceToSalesTrailing12Months", 0.0) if not is_index else 0.0,
            fifty_day_average=summary_detail_data.get("fiftyDayAverage", 0.0),
            two_hundred_day_average=summary_detail_data.get("twoHundredDayAverage", 0.0),
            trailing_pe=summary_detail_data.get("trailingPE", 0.0) if not is_index else 0.0,
            forward_pe=summary_detail_data.get("forwardPE", 0.0) if not is_index else 0.0,
            dividend_rate=summary_detail_data.get("dividendRate", 0.0),
            dividend_yield=summary_detail_data.get("dividendYield", 0.0),
            payout_ratio=summary_detail_data.get("payoutRatio", 0.0) if not is_index else 0.0,
            beta=summary_detail_data.get("beta", 0.0) if not is_index else 0.0
        )
        
        price_data = data["results"]["price"]
        price = YahooFinancePrice(
            regular_market_price=price_data.get("regularMarketPrice", 0.0),
            regular_market_change=price_data.get("regularMarketChange", 0.0),
            regular_market_change_percent=price_data.get("regularMarketChangePercent", 0.0),
            regular_market_time=price_data.get("regularMarketTime", ""),
            regular_market_volume=price_data.get("regularMarketVolume", 0),
            regular_market_day_high=price_data.get("regularMarketDayHigh", 0.0),
            regular_market_day_low=price_data.get("regularMarketDayLow", 0.0),
            regular_market_previous_close=price_data.get("regularMarketPreviousClose", 0.0),
            regular_market_open=price_data.get("regularMarketOpen", 0.0),
            exchange=price_data.get("exchange", ""),
            exchange_name=price_data.get("exchangeName", ""),
            market_state=price_data.get("marketState", ""),
            quote_type=price_data.get("quoteType", ""),
            symbol=price_data.get("symbol", ticker),
            short_name=price_data.get("shortName", ""),
            long_name=price_data.get("longName", ""),
            currency=price_data.get("currency", "USD"),
            market_cap=price_data.get("marketCap", 0.0) if not is_index else 0.0
        )
        
        quotes = []
        for quote_data in data["chart"]["quotes"]:
            quotes.append(YahooFinanceQuote(
                date=quote_data.get("date", ""),
                high=quote_data.get("high", 0.0),
                volume=quote_data.get("volume", 0),
                open=quote_data.get("open", 0.0),
                low=quote_data.get("low", 0.0),
                close=quote_data.get("close", 0.0),
                adjclose=quote_data.get("adjclose", 0.0)
            ))
        
        news = []
        for news_item in data.get("news", []):
            news.append(YahooFinanceNews(
                uuid=news_item.get("uuid", ""),
                title=news_item.get("title", ""),
                publisher=news_item.get("publisher", ""),
                link=news_item.get("link", ""),
                provider_publish_time=news_item.get("providerPublishTime", ""),
                type=news_item.get("type", ""),
                related_tickers=news_item.get("relatedTickers", [])
            ))
        
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
        
    except Exception as e:
        Actor.log.error(f"Error getting Yahoo Finance data for {ticker}: {str(e)}")
        # Initialize with default values instead of empty constructor
        default_summary_detail = YahooFinanceSummaryDetail(
            previous_close=0.0,
            open=0.0,
            day_low=0.0,
            day_high=0.0,
            volume=0,
            average_volume=0,
            market_cap=0.0,
            fifty_two_week_low=0.0,
            fifty_two_week_high=0.0,
            price_to_sales_trailing_12_months=0.0,
            fifty_day_average=0.0,
            two_hundred_day_average=0.0,
            trailing_pe=0.0,
            forward_pe=0.0,
            dividend_rate=0.0,
            dividend_yield=0.0,
            payout_ratio=0.0,
            beta=0.0
        )
        
        default_price = YahooFinancePrice(
            regular_market_price=0.0,
            regular_market_change=0.0,
            regular_market_change_percent=0.0,
            regular_market_time="",
            regular_market_volume=0,
            regular_market_day_high=0.0,
            regular_market_day_low=0.0,
            regular_market_previous_close=0.0,
            regular_market_open=0.0,
            exchange="",
            exchange_name="",
            market_state="",
            quote_type="",
            symbol=ticker,
            short_name=f"Default ({ticker})",
            long_name=f"Default Index ({ticker})",
            currency="USD",
            market_cap=0.0
        )
        
        return YahooFinanceData(
            summary_detail=default_summary_detail,
            price=default_price,
            quotes=[],
            news=[],
            ticker=ticker,
            start_date=start_date,
            end_date=end_date
        )

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
