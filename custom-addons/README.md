# Villeside Realty - Odoo Custom Addons

Custom Odoo modules for Villeside Realty LLC (villesiderealty.cassilly.capital)

## Modules

### villeside_flexmls
FlexMLS/Spark API integration for live MLS property listings.
- Connects to FBS Spark API for IDX/VOW data
- Syncs active listings to Odoo website
- Property search with filters (price, beds, baths, location)
- Listing detail pages with photos, maps, and specs
- Automated data refresh via cron jobs

### villeside_leads
Real estate lead capture and CRM pipeline.
- Website lead forms: Buyer Inquiry, Seller Valuation, Investor Analysis
- Auto-creates CRM opportunities from form submissions
- Lead routing and assignment rules
- Email/SMS notifications on new leads
- Integration with Odoo CRM pipeline stages

### villeside_website_theme
Custom Bootstrap-based Odoo website theme for Villeside Realty.
- Navy/gold brand colors
- Louisville-specific imagery and content
- Responsive property listing cards
- Neighborhood pages with market data
- Join the Team recruitment page
- Blog templates for real estate content

### villeside_stripe
Stripe payment integration for real estate transactions.
- Earnest money deposits
- Application fees
- Rental payments
- Invoice payments via Stripe Checkout
- Webhook handling for payment confirmations


### villeside_analytics
Agent performance, market data, and pipeline analytics.
- Agent performance dashboards and KPIs
- Market data reporting and trends
- Pipeline analytics and conversion tracking
- CRM integration for sales metrics

### villeside_commission
Commission split plans, cap tracking, and agent payout management.
- Commission split plan configuration
- Agent cap tracking and thresholds
- Payout calculations and management
- Integration with CRM and accounting
## Tech Stack
- Odoo 19.0 Enterprise
- Python 3.10+
- FlexMLS Spark API (RESO Web API)
- Stripe API
- Bootstrap 5
- PostgreSQL

## Setup
1. Clone into your Odoo addons path
2. Configure Spark API credentials in Settings
3. Configure Stripe keys in Payment Providers
4. Update module list and install

## Repository
`git.bsdyno.com/cassilly-capital/villeside-realty/villeside-odoo-addons`
