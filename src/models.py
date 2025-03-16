from pydantic import BaseModel, Field
from dataclasses import dataclass
from apify_client import ApifyClient
from typing import Optional, List

@dataclass  
class Deps:
    client: ApifyClient


class ReportInfo(BaseModel):
    company_name: str = Field(..., description="Official name of the company")
    website_url: str = Field(..., description="URL of the company's official website")
    short_description: str = Field(..., description="Brief overview of the company's business and mission")
    market_cap: str = Field(..., description="Market capitalization of the company")
    price: str = Field(..., description="Current price of the company's stock")
    price_change: str = Field(..., description="Percentage change in price over the last 24 hours")
    volume: str = Field(..., description="Volume of the company's stock traded in the last 24 hours")
    volume_change: str = Field(..., description="Percentage change in volume over the last 24 hours")
    report: str = Field(..., description="Markdown market research report for the company")
    

class YahooFinanceSummaryDetail(BaseModel):
    previous_close: float
    open: float
    day_low: float
    day_high: float
    volume: int
    average_volume: int
    market_cap: float
    fifty_two_week_low: float
    fifty_two_week_high: float
    price_to_sales_trailing_12_months: float
    fifty_day_average: float
    two_hundred_day_average: float
    trailing_pe: float
    forward_pe: float
    dividend_rate: float
    dividend_yield: float
    payout_ratio: float
    beta: float

class YahooFinancePrice(BaseModel):
    regular_market_price: float
    regular_market_change: float
    regular_market_change_percent: float
    regular_market_time: str
    regular_market_volume: int
    regular_market_day_high: float
    regular_market_day_low: float
    regular_market_previous_close: float
    regular_market_open: float
    exchange: str
    exchange_name: str
    market_state: str
    quote_type: str
    symbol: str
    short_name: str
    long_name: str
    currency: str
    market_cap: float

class YahooFinanceQuote(BaseModel):
    date: str
    high: float
    volume: int
    open: float
    low: float
    close: float
    adjclose: float

class YahooFinanceNews(BaseModel):
    uuid: str
    title: str
    publisher: str
    link: str
    provider_publish_time: str
    type: str
    related_tickers: list[str]

class YahooFinanceData(BaseModel):
    summary_detail: YahooFinanceSummaryDetail
    price: YahooFinancePrice
    quotes: list[YahooFinanceQuote]
    news: list[YahooFinanceNews]
    ticker: str
    start_date: str
    end_date: str
    
    
# Models for external data sources
class LinkedInData(BaseModel):
    name: Optional[str] = Field(None, description="Company name from LinkedIn")
    description: Optional[str] = Field(None, description="Company description from LinkedIn")
    industry: Optional[str] = Field(None, description="Industry type from LinkedIn")
    employees: Optional[int] = Field(None, description="Number of employees")
    website: Optional[str] = Field(None, description="Company website")
    specialties: List[str] = Field(default_factory=list, description="Company specialties")
    address: Optional[str] = Field(None, description="Company address")


class CompanyLinks(BaseModel):
    """Model for storing company profile URLs"""
    linkedin_url: str = Field(..., description="URL of the company's LinkedIn profile")
    crunchbase_url: str = Field(..., description="URL of the company's Crunchbase profile")
    sector_index: str = Field(..., description="Sector-specific index ticker (e.g., ^XLF for financials)")


class SectorIndex(BaseModel):
    """Model for storing sector index information"""
    ticker: str = Field(..., description="Ticker symbol of the sector-specific index, e.g. ^XLF")
    sector_name: Optional[str] = Field(None, description="Name of the sector, e.g. Financials")
    description: Optional[str] = Field(None, description="Brief description of the sector index")

