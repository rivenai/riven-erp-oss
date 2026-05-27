#!/bin/bash
# Setup script to create missing __init__.py and __manifest__.py files
# Run from the villeside-odoo-addons root directory

# Module definitions: module_name|model_file|display_name|category|summary|depends
MODULES=(
  "villeside_maintenance|maintenance|Villeside Property Maintenance|Maintenance|Property maintenance requests and work orders|crm,mail,account"
  "villeside_tenant|tenant|Villeside Tenant Management|Property Management|Tenant leases, payments, and screening|crm,mail,account"
  "villeside_analytics|analytics|Villeside Real Estate Analytics|Reporting|Agent performance, market data, pipeline analytics|crm,mail"
  "villeside_vendor|vendor|Villeside Vendor Management|Services|Vendor directory with reviews and ratings|mail"
  "villeside_showing|showing|Villeside Property Showings|Real Estate|Property showings, open houses, and feedback|crm,mail"
  "villeside_document|document|Villeside Document Management|Document Management|Real estate document management with checklists|crm,mail"
  "villeside_website_idx|idx|Villeside Website IDX|Website|IDX/MLS integration, property search, lead capture|crm,website"
)

for entry in "${MODULES[@]}"; do
  IFS='|' read -r mod model name cat summary deps <<< "$entry"
  
  # Create models/__init__.py if missing
  if [ ! -f "$mod/models/__init__.py" ]; then
    echo "from . import $model" > "$mod/models/__init__.py"
    echo "Created $mod/models/__init__.py"
  fi
  
  # Create __init__.py if missing
  if [ ! -f "$mod/__init__.py" ]; then
    echo "from . import models" > "$mod/__init__.py"
    echo "Created $mod/__init__.py"
  fi
  
  # Create __manifest__.py if missing
  if [ ! -f "$mod/__manifest__.py" ]; then
    dep_list=$(echo "$deps" | sed "s/,/', '/g")
    cat > "$mod/__manifest__.py" << EOF
{
    'name': '$name',
    'version': '18.0.1.0.0',
    'category': '$cat',
    'summary': '$summary',
    'author': 'Villeside Realty / Cassilly Capital',
    'website': 'https://villesiderealty.com',
    'depends': ['$dep_list'],
    'data': [],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
EOF
    echo "Created $mod/__manifest__.py"
  fi
done

echo "Module setup complete!"