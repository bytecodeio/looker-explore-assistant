#!/usr/bin/env python3
"""
Populate vector database with comprehensive sample dimension values.

This creates a realistic dataset of dimension values that would commonly
appear in e-commerce, SaaS, and business analytics scenarios.
"""

import json
import logging
from typing import List, Dict, Any
from server import add_dimension_values, get_collection_stats, initialize_vector_db, clear_collection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_comprehensive_dimension_data() -> List[Dict[str, Any]]:
    """Generate comprehensive dimension value dataset for vector search"""
    
    dimension_data = []
    
    # E-commerce Product Categories
    ecommerce_categories = [
        "Electronics", "Computers", "Laptops", "Smartphones", "Tablets", "Gaming",
        "Clothing", "Fashion", "Shoes", "Accessories", "Jewelry",
        "Home & Garden", "Furniture", "Kitchen", "Appliances", "Decor",
        "Sports", "Fitness", "Outdoor", "Athletic", "Recreation",
        "Books", "Media", "Entertainment", "Movies", "Music",
        "Beauty", "Health", "Personal Care", "Skincare", "Cosmetics",
        "Automotive", "Tools", "Industrial", "Construction", "Hardware"
    ]
    
    for category in ecommerce_categories:
        dimension_data.append({
            "value": category,
            "field_reference": "ecommerce.order_items.product_category",
            "explore_key": "ecommerce:order_items",
            "field_type": "dimension",
            "description": f"Product category: {category}"
        })
    
    # Geographic Locations
    locations = [
        # US States
        "California", "New York", "Texas", "Florida", "Illinois", "Pennsylvania",
        "Ohio", "Georgia", "North Carolina", "Michigan", "Washington", "Arizona",
        "Massachusetts", "Tennessee", "Indiana", "Missouri", "Maryland", "Wisconsin",
        "Colorado", "Minnesota", "Louisiana", "Alabama", "Kentucky", "Oregon",
        
        # Major Cities
        "New York City", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia",
        "San Antonio", "San Diego", "Dallas", "San Jose", "Austin", "Jacksonville",
        "San Francisco", "Columbus", "Fort Worth", "Indianapolis", "Charlotte",
        "Seattle", "Denver", "Washington DC", "Boston", "Nashville", "Detroit",
        "Portland", "Las Vegas", "Memphis", "Louisville", "Baltimore", "Milwaukee",
        "Albuquerque", "Tucson", "Fresno", "Sacramento", "Kansas City", "Mesa",
        
        # Countries
        "United States", "Canada", "United Kingdom", "Germany", "France", "Italy",
        "Spain", "Australia", "Japan", "China", "India", "Brazil", "Mexico",
        "Netherlands", "Sweden", "Norway", "Denmark", "Belgium", "Switzerland"
    ]
    
    for location in locations:
        # Add as customer city
        dimension_data.append({
            "value": location,
            "field_reference": "sales.customers.city",
            "explore_key": "sales:customers",
            "field_type": "dimension",
            "description": f"Customer location: {location}"
        })
        
        # Add as shipping region for some
        if location in ["California", "New York", "Texas", "United States", "Canada", "United Kingdom"]:
            dimension_data.append({
                "value": location,
                "field_reference": "fulfillment.orders.shipping_region",
                "explore_key": "fulfillment:orders",
                "field_type": "dimension",
                "description": f"Shipping region: {location}"
            })
    
    # Time Periods
    time_periods = [
        # Quarters
        "Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024",
        "Q1 2023", "Q2 2023", "Q3 2023", "Q4 2023",
        "Q1", "Q2", "Q3", "Q4",
        "First Quarter", "Second Quarter", "Third Quarter", "Fourth Quarter",
        
        # Months
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        
        # Years
        "2024", "2023", "2022", "2021", "2020", "2019",
        
        # Relative periods
        "This Month", "Last Month", "This Quarter", "Last Quarter",
        "This Year", "Last Year", "YTD", "Year to Date"
    ]
    
    for period in time_periods:
        dimension_data.append({
            "value": period,
            "field_reference": "common.dates.period",
            "explore_key": "analytics:time_series",
            "field_type": "dimension",
            "description": f"Time period: {period}"
        })
    
    # Business/Job Titles
    job_titles = [
        "Manager", "Director", "Vice President", "Senior Manager", "Team Lead",
        "Executive", "CEO", "CTO", "CFO", "COO", "President",
        "Sales Manager", "Marketing Manager", "Product Manager", "Engineering Manager",
        "Operations Manager", "Finance Manager", "HR Manager",
        "Analyst", "Senior Analyst", "Data Analyst", "Business Analyst",
        "Developer", "Senior Developer", "Software Engineer", "DevOps Engineer",
        "Designer", "UI Designer", "UX Designer", "Graphic Designer",
        "Consultant", "Senior Consultant", "Principal", "Partner",
        "Coordinator", "Administrator", "Specialist", "Associate"
    ]
    
    for title in job_titles:
        dimension_data.append({
            "value": title,
            "field_reference": "hr.employees.job_title",
            "explore_key": "hr:employees",
            "field_type": "dimension",
            "description": f"Employee job title: {title}"
        })
    
    # Customer Segments/Tiers
    segments = [
        "Enterprise", "Corporate", "Business", "Professional", "Standard", "Basic",
        "Premium", "Gold", "Silver", "Bronze", "Platinum", "Diamond",
        "VIP", "Elite", "Pro", "Plus", "Free", "Trial",
        "Large", "Medium", "Small", "Startup", "SMB", "Mid-Market"
    ]
    
    for segment in segments:
        dimension_data.append({
            "value": segment,
            "field_reference": "customers.accounts.tier",
            "explore_key": "customers:accounts",
            "field_type": "dimension",
            "description": f"Customer tier: {segment}"
        })
        
        # Also add as subscription tier
        dimension_data.append({
            "value": segment,
            "field_reference": "subscriptions.plans.tier",
            "explore_key": "subscriptions:plans",
            "field_type": "dimension",
            "description": f"Subscription tier: {segment}"
        })
    
    # Status Values
    status_values = [
        "Active", "Inactive", "Pending", "Complete", "In Progress", "Cancelled",
        "Approved", "Rejected", "Draft", "Published", "Archived", "Deleted",
        "New", "Open", "Closed", "Resolved", "Escalated", "On Hold",
        "Shipped", "Delivered", "Processing", "Returned", "Refunded",
        "Paid", "Unpaid", "Overdue", "Partial", "Failed", "Success"
    ]
    
    for status in status_values:
        dimension_data.append({
            "value": status,
            "field_reference": "orders.transactions.status",
            "explore_key": "orders:transactions",
            "field_type": "dimension",
            "description": f"Transaction status: {status}"
        })
    
    # Industries
    industries = [
        "Technology", "Software", "Hardware", "Internet", "Telecommunications",
        "Financial Services", "Banking", "Insurance", "Investment",
        "Healthcare", "Medical", "Pharmaceutical", "Biotechnology",
        "Retail", "E-commerce", "Consumer Goods", "Fashion", "Automotive",
        "Manufacturing", "Industrial", "Construction", "Real Estate",
        "Education", "Government", "Non-profit", "Media", "Entertainment",
        "Energy", "Utilities", "Transportation", "Logistics", "Travel",
        "Food & Beverage", "Agriculture", "Mining", "Consulting", "Legal"
    ]
    
    for industry in industries:
        dimension_data.append({
            "value": industry,
            "field_reference": "companies.profiles.industry",
            "explore_key": "companies:profiles",
            "field_type": "dimension",
            "description": f"Company industry: {industry}"
        })
    
    # Channel/Source Types
    channels = [
        "Direct", "Organic Search", "Paid Search", "Social Media", "Email",
        "Referral", "Display", "Affiliate", "Partnership", "Events",
        "Content Marketing", "SEO", "SEM", "PPC", "Facebook", "Google",
        "LinkedIn", "Twitter", "Instagram", "YouTube", "TikTok",
        "Mobile App", "Website", "In-Store", "Phone", "Chat", "Support"
    ]
    
    for channel in channels:
        dimension_data.append({
            "value": channel,
            "field_reference": "marketing.campaigns.channel",
            "explore_key": "marketing:campaigns",
            "field_type": "dimension",
            "description": f"Marketing channel: {channel}"
        })
    
    logger.info(f"Generated {len(dimension_data)} comprehensive dimension value records")
    return dimension_data

def populate_comprehensive_vector_db():
    """Populate vector database with comprehensive dimension value dataset"""
    try:
        # Initialize vector database
        logger.info("🔧 Initializing vector database...")
        initialize_vector_db()
        
        # Clear existing data for fresh start
        logger.info("🧹 Clearing existing data...")
        clear_result = clear_collection()
        logger.info(f"Clear result: {clear_result}")
        
        # Generate comprehensive dataset
        logger.info("📝 Generating comprehensive dimension dataset...")
        dimension_data = get_comprehensive_dimension_data()
        
        # Add to vector database in batches
        batch_size = 100
        total_added = 0
        
        for i in range(0, len(dimension_data), batch_size):
            batch = dimension_data[i:i + batch_size]
            logger.info(f"📥 Adding batch {i//batch_size + 1} ({len(batch)} records)...")
            
            result = add_dimension_values(batch)
            
            if "status" in result and result["status"] == "success":
                added_count = result.get("added_count", 0)
                total_added += added_count
                logger.info(f"✅ Successfully added {added_count} records")
            else:
                logger.error(f"❌ Failed to add batch: {result}")
        
        # Get final stats
        final_stats = get_collection_stats()
        logger.info(f"Final vector DB stats: {final_stats}")
        
        logger.info(f"""
🎉 Comprehensive population complete!
📊 Total dimension values added: {total_added}
🔍 Total values in vector DB: {final_stats.get('total_values', 0)}
🚀 Vector database is ready for semantic search!

Test some searches:
• "electronics" → should find Electronics, Computers, Gaming, etc.
• "california" → should find California locations  
• "manager" → should find Manager, Sales Manager, etc.
• "enterprise" → should find Enterprise tier/segment
• "q4" → should find Q4 2024, Fourth Quarter, etc.

Run: python test_server.py
        """)
        
    except Exception as e:
        logger.error(f"Failed to populate comprehensive vector database: {e}")
        raise

if __name__ == "__main__":
    populate_comprehensive_vector_db()