# Guide: Adapting the ClimateGPT Emissions Server for a Different SQLite Database

This guide explains how to adapt the ClimateGPT emissions server to work with a completely different SQLite database schema. It uses specific examples from the original code to show exactly what needs to be modified.

## Prerequisites

- Python 3.8 or higher
- A working copy of the ClimateGPT emissions server code
- Your SQLite database (.db file) with a different schema
- Your database schema documentation

## Step 1: Replace the Database File

First, replace the existing database file with yours:

```bash
# Back up the original database (optional)
cp src/database/ClimateGPT.db src/database/ClimateGPT.db.backup

# Copy your database to the expected location
cp /path/to/your_database.db src/database/ClimateGPT.db
```

Alternatively, you can update the `DB_PATH` in `config.py` to point to your database location:

```python
# Original in config.py
DB_PATH = os.environ.get("CLIMATE_SERVER_DB_PATH", os.path.join(BASE_DIR, "src/database/ClimateGPT.db"))

# Modified to use your database
DB_PATH = os.environ.get("CLIMATE_SERVER_DB_PATH", os.path.join(BASE_DIR, "path/to/your_database.db"))
```

## Step 2: Update Database Access Layer

The file `src/mcp_server/db_access.py` contains the core database interaction logic. Here are the key parts that need modification:

### 1. Update Query Validation

The emissions server validates queries to prevent dangerous operations:

```python
# Original code in db_access.py
def validate_query(sql_query: str) -> None:
    """Validate a SQL query for safety."""
    sql_query_upper = sql_query.upper()
    
    # List of dangerous SQL commands that should not be allowed
    dangerous_commands = [
        'DROP ', 'DELETE ', 'UPDATE ', 'INSERT ', 'ALTER ', 'CREATE ', 
        'TRUNCATE ', 'GRANT ', 'REVOKE ', 'ATTACH ', 'DETACH '
    ]
    
    # Check for dangerous commands
    for cmd in dangerous_commands:
        if cmd in sql_query_upper:
            logger.warning(f"Dangerous SQL command detected: {sql_query}")
            raise ValueError(f"Dangerous SQL command detected: {cmd.strip()}")
```

This doesn't need substantial modification unless you want to allow certain operations.

### 2. Update Table Statistics Function

The `get_table_stats()` function queries the database structure. Modify it to match your tables:

```python
# Original in db_access.py
def get_table_stats() -> Dict[str, Any]:
    """Get basic statistics about the database tables."""
    stats = {}
    conn = None
    
    try:
        conn = sqlite3.connect(DB_PATH, timeout=DB_CONNECTION_TIMEOUT)
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            
            # Skip SQLite internal tables
            if table_name.startswith('sqlite_'):
                continue
                
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            row_count = cursor.fetchone()[0]
            
            # Get column count
            cursor.execute(f"PRAGMA table_info({table_name});")
            column_count = len(cursor.fetchall())
            
            # Store basic table stats
            stats[table_name] = {
                "rows": row_count,
                "columns": column_count
            }
            
            # For emissions table, get year range
            if table_name == "Emissions":
                try:
                    cursor.execute("SELECT MIN(year), MAX(year) FROM Emissions;")
                    min_year, max_year = cursor.fetchone()
                    stats[table_name]["year_range"] = (min_year, max_year)
                except sqlite3.Error as e:
                    logger.warning(f"Error getting year range: {str(e)}")
```

Modify this to use your main table names and important date/time ranges:

```python
# Modified for your database
def get_table_stats() -> Dict[str, Any]:
    """Get basic statistics about the database tables."""
    stats = {}
    conn = None
    
    try:
        conn = sqlite3.connect(DB_PATH, timeout=DB_CONNECTION_TIMEOUT)
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            
            # Skip SQLite internal tables
            if table_name.startswith('sqlite_'):
                continue
                
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            row_count = cursor.fetchone()[0]
            
            # Get column count
            cursor.execute(f"PRAGMA table_info({table_name});")
            column_count = len(cursor.fetchall())
            
            # Store basic table stats
            stats[table_name] = {
                "rows": row_count,
                "columns": column_count
            }
            
            # For your main table, get date range
            # (Replace "YourMainTable" and "date_column" with your actual values)
            if table_name == "YourMainTable":
                try:
                    cursor.execute("SELECT MIN(date_column), MAX(date_column) FROM YourMainTable;")
                    min_date, max_date = cursor.fetchone()
                    stats[table_name]["date_range"] = (min_date, max_date)
                except sqlite3.Error as e:
                    logger.warning(f"Error getting date range: {str(e)}")
```

## Step 3: Update Schema Tools

The file `src/mcp_server/schema_tools.py` handles schema information. Here's what to modify:

### Example from schema_tools.py:

```python
# Original function in schema_tools.py
def _load_schema() -> Dict[str, Any]:
    """Load the database schema once at initialization."""
    global _SCHEMA, _RELATIONSHIPS, _COLUMN_MAP
    
    logger.info("Loading database schema (one-time initialization)")
    conn = None
    try:
        # Connect to database with timeout
        conn = sqlite3.connect(DB_PATH, timeout=DB_CONNECTION_TIMEOUT)
        cursor = conn.cursor()

        # Get table names and schema definitions
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        schema = {"tables": []}
        relationships = {}
        column_map = {}

        for table_name, create_sql in tables:
            # Skip SQLite internal tables
            if table_name.startswith('sqlite_'):
                continue
                
            # Extract column names and types
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns_info = cursor.fetchall()

            columns = [
                {
                    "name": col[1],  # col[1] = column name
                    "type": col[2],  # col[2] = column type
                    "nullable": not col[3],  # col[3] = NOT NULL constraint
                    "pk": col[5] > 0  # col[5] = primary key
                } for col in columns_info
            ]

            # Get foreign key information
            cursor.execute(f"PRAGMA foreign_key_list({table_name});")
            fk_info = cursor.fetchall()
            
            foreign_keys = []
            for fk in fk_info:
                foreign_keys.append({
                    "from_column": fk[3],  # local column
                    "to_table": fk[2],  # referenced table
                    "to_column": fk[4]  # referenced column
                })

            schema["tables"].append({
                "name": table_name,
                "columns": columns,
                "foreign_keys": foreign_keys
            })
            
            # Store relationships for this table
            relationships[table_name] = foreign_keys
            
            # Build the column map for typo correction
            for column in columns:
                col_name = column["name"]
                # Add the standard column name
                column_map[f"{table_name}.{col_name}"] = f"{table_name}.{col_name}"
                # Add common abbreviations and aliases
                if table_name == "Greenhouse_Gases":
                    column_map[f"gg.{col_name}"] = f"gg.{col_name}"
                    # ...more alias handling
```

You need to update the table-specific aliases at the end of this function to match your tables. For example:

```python
# Modified for your database
# Add common abbreviations and aliases
if table_name == "YourProductsTable":
    column_map[f"p.{col_name}"] = f"p.{col_name}"
    # Handle "name" vs your specific column name
    if col_name == "product_name":
        column_map["p.name"] = "p.product_name"
elif table_name == "YourCustomersTable":
    column_map[f"c.{col_name}"] = f"c.{col_name}"
    # Handle column name variants
    if col_name == "customer_name":
        column_map["c.name"] = "c.customer_name"
# Add sections for your other main tables
```

## Step 4: Update Query Classifier

The file `src/mcp_server/query_classifier.py` contains the schema description used for SQL generation. This is the most important part to update:

### 1. Replace Schema Description

```python
# Original schema description in query_classifier.py
schema_info = """
DATABASE SCHEMA:

Table: Greenhouse_Gases
  - ghg_id (INTEGER PRIMARY KEY): Unique identifier for greenhouse gas
  - ghg_name (TEXT): Name of the greenhouse gas (e.g., Carbon Dioxide, Methane, Nitrous Oxide)
  - ghg_category (TEXT): Category of the greenhouse gas (e.g., CO2, CH4, N2O)
  Sample data: 
  [
    {"ghg_id": 1, "ghg_name": "Carbon Dioxide", "ghg_category": "CO2"},
    {"ghg_id": 2, "ghg_name": "Nitrous Oxide", "ghg_category": "N2O"},
    {"ghg_id": 3, "ghg_name": "Methane", "ghg_category": "CH4"}
  ]

Table: Sectors
  - sector_id (INTEGER PRIMARY KEY): Unique identifier for the sector
  - sector (TEXT): Name of the sector (e.g., Agriculture, Energy, Transportation)
  - subsector (TEXT): Subsector name
  ...

RELATIONSHIPS:
- Emissions.ghg_id → Greenhouse_Gases.ghg_id
- Emissions.sector_id → Sectors.sector_id
- Emissions.fuel_id → Fuels.fuel_id
- Emissions.geo_id → Geography.geo_id
"""
```

Replace this with a description of your schema:

```python
# Modified for your database
schema_info = """
DATABASE SCHEMA:

Table: YourMainTable
  - id (INTEGER PRIMARY KEY): Unique identifier
  - date_column (TEXT): Date of the record
  - value_column (REAL): Main value or measurement
  - category_id (INTEGER): Foreign key to YourCategoriesTable
  Sample data: 
  [
    {"id": 1, "date_column": "2023-01-15", "value_column": 42.5, "category_id": 2},
    {"id": 2, "date_column": "2023-02-20", "value_column": 37.8, "category_id": 1}
  ]

Table: YourCategoriesTable
  - category_id (INTEGER PRIMARY KEY): Unique identifier for category
  - category_name (TEXT): Name of the category
  - category_type (TEXT): Type of category
  Sample data:
  [
    {"category_id": 1, "category_name": "Type A", "category_type": "Major"},
    {"category_id": 2, "category_name": "Type B", "category_type": "Minor"}
  ]

... add all your tables here ...

RELATIONSHIPS:
- YourMainTable.category_id → YourCategoriesTable.category_id
... add all your relationships here ...
"""
```

### 2. Update SQL Function Guidance

```python
# Original SQLite guidance in query_classifier.py
sqlite_guidance = """
IMPORTANT SQLITE FUNCTION LIMITATIONS AND ALTERNATIVES:

1. Percentiles:
   - SQLite does NOT support PERCENTILE_CONT or PERCENTILE_DISC.
   - Use this pattern:
     SELECT emissions
     FROM (SELECT emissions FROM Emissions ORDER BY emissions)
     LIMIT 1 OFFSET (
       SELECT CAST(COUNT(*) * 0.25 AS INT) FROM Emissions
     );
"""
```

Update this section with any specific SQL patterns for your database:

```python
# Modified for your database functions and patterns
sqlite_guidance = """
IMPORTANT SQLITE FUNCTION LIMITATIONS AND ALTERNATIVES:

1. Working with dates in your database:
   - Use SQLite date functions for your date_column
   - Example for extracting year: strftime('%Y', date_column)
   - Example for filtering by date range: 
     WHERE date_column BETWEEN '2022-01-01' AND '2022-12-31'

2. Calculating with your value_column:
   - For running averages: AVG(value_column) OVER (ORDER BY date_column ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
   - For growth rates: (value_column - LAG(value_column) OVER (ORDER BY date_column)) / LAG(value_column) OVER (ORDER BY date_column)
"""
```

### 3. Update Sample Queries

```python
# Original sample queries in query_classifier.py
sample_queries = """
# 1. Query for total CO2 emissions by year
SELECT e.year, SUM(e.emissions) as total_emissions 
FROM Emissions e 
JOIN Greenhouse_Gases gg ON e.ghg_id = gg.ghg_id 
WHERE gg.ghg_name = 'Carbon Dioxide' 
GROUP BY e.year 
ORDER BY e.year;
"""
```

Replace with sample queries for your database:

```python
# Modified sample queries for your database
sample_queries = """
# 1. Query for total values by date
SELECT strftime('%Y-%m', m.date_column) as month, SUM(m.value_column) as total_value 
FROM YourMainTable m 
JOIN YourCategoriesTable c ON m.category_id = c.category_id 
WHERE c.category_name = 'Type A' 
GROUP BY month 
ORDER BY month;

# 2. Compare values between categories
SELECT c.category_name, AVG(m.value_column) as average_value 
FROM YourMainTable m 
JOIN YourCategoriesTable c ON m.category_id = c.category_id 
WHERE m.date_column BETWEEN '2022-01-01' AND '2022-12-31'
GROUP BY c.category_name;
"""
```

## Step 5: Update Forecast Execution

In `src/utils/forecast_executor.py`, modify the SQL query that retrieves time series data:

```python
# Original forecast query builder
def build_forecast_query(forecast_params: Dict[str, Any]) -> str:
    """Build an SQL query to retrieve historical data with more features."""
    region = forecast_params.get('region')
    emission_type = forecast_params.get('emission_type')
    
    # Enhanced query with more predictive features
    sql = """
    SELECT 
        e.year, 
        SUM(e.emissions) as total_emissions,
        
        -- Energy sector emissions by key categories
        SUM(CASE WHEN s.sector = 'Energy' AND s.subsector = 'Fossil Fuel Combustion' 
            THEN e.emissions ELSE 0 END) as fossil_fuel_emissions
    FROM Emissions e
    JOIN Sectors s ON e.sector_id = s.sector_id
    JOIN Fuels f ON e.fuel_id = f.fuel_id
    JOIN Greenhouse_Gases gg ON e.ghg_id = gg.ghg_id
    """
```

Replace with a query that works for your time series data:

```python
# Modified for your database
def build_forecast_query(forecast_params: Dict[str, Any]) -> str:
    """Build an SQL query to retrieve time series data from your database."""
    category = forecast_params.get('category')
    value_type = forecast_params.get('value_type')
    
    # Query adapted for your database schema
    sql = """
    SELECT 
        strftime('%Y-%m-%d', m.date_column) as date, 
        SUM(m.value_column) as total_value,
        
        -- Add derived metrics relevant to your data
        AVG(m.value_column) OVER (ORDER BY m.date_column ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as moving_avg,
        MAX(m.value_column) OVER (PARTITION BY strftime('%Y-%m', m.date_column)) as monthly_max
    FROM YourMainTable m
    JOIN YourCategoriesTable c ON m.category_id = c.category_id
    """
    
    # Add conditional joins and where clauses
    where_clauses = []
    
    if category:
        where_clauses.append(f"c.category_name = '{category}'")
    
    if value_type:
        where_clauses.append(f"m.value_type = '{value_type}'")
    
    # Add where clauses
    if where_clauses:
        sql += "\nWHERE " + " AND ".join(where_clauses)
    
    # Finish the query with grouping by date
    sql += """
    GROUP BY date
    ORDER BY date
    """
    
    return sql
```

## Step 6: Update Visualization Field Recognition

In `src/utils/visualization.py`, update the field detection logic:

```python
# Original code looking for climate-specific fields
def determine_visualization_type(columns: List[str], data: List[List[Any]], query: str = "") -> str:
    """Determine the most appropriate visualization type for climate data."""
    # Look for specific column patterns from our schema
    has_year = any('year' in col.lower() for col in columns)
    has_emissions = any('emissions' in col.lower() for col in columns)
    has_region = any(col in ['region_name', 'geo_ref', 'state'] for col in columns_lower)
    has_ghg = any(col in ['ghg_name', 'ghg_category'] for col in columns_lower)
```

Replace with fields relevant to your data:

```python
# Modified for your database schema
def determine_visualization_type(columns: List[str], data: List[List[Any]], query: str = "") -> str:
    """Determine the most appropriate visualization type for your data."""
    # Convert column names to lowercase for easier comparison
    columns_lower = [col.lower() for col in columns]
    
    # Look for specific column patterns from your schema
    has_date = any('date' in col.lower() for col in columns)
    has_value = any('value' in col.lower() for col in columns)
    has_category = any(col in ['category_name', 'category_type'] for col in columns_lower)
    has_region = any(col in ['region', 'location', 'area'] for col in columns_lower)
```

## Step 7: Update server_registry.json

Update the server registry to reflect your database:

```json
{
  "your_custom_server": {
    "url": "http://127.0.0.1:8000",
    "description": "Your custom data server",
    "capabilities": ["database_queries", "visualization", "forecasting"],
    "keywords": [
      "your", "relevant", "keywords"
    ],
    "schema": {
      "tables": ["YourMainTable", "YourCategoriesTable"],
      "time_range": "YOUR-DATA-RANGE" 
    },
    "timeout": 600
  }
}
```

## Step 8: Update the CLI to Test Your Server

1. Start the server:
```bash
python start_server.py
```

2. Test database connectivity directly:
```bash
sqlite3 src/database/YourDatabase.db "SELECT * FROM YourMainTable LIMIT 5;"
```

3. In a new terminal, start the CLI:
```bash
cd /path/to/climate_client
python start_client.py
```

4. Use the CLI to test queries against your new database:
```
help
stats
Show total value_column by month
What was the trend in category Type A values from 2020 to 2022?
```

## Common Issues and Solutions

### SQL Generation Failures

If you see errors like "Table not found" or "Column not found":

1. Check `query_classifier.py` to ensure your schema description is accurate
2. Verify the table and column aliases in `schema_tools.py` 
3. Look for hardcoded table/column names in `query_utils.py`

### Visualization Issues

If visualizations fail to generate:

1. Check `visualization.py` to ensure your data types are recognized
2. Update visualization templates in `visualization_templates.py` to use your field names
3. Test with simpler queries first to identify the exact issue

### Forecasting Issues

If forecasting fails:

1. Ensure your time series data is in a format compatible with the forecasting module
2. Update `forecast_detector.py` to recognize your date formats and fields
3. Check if your data has enough historical points for forecasting to work

By following this guide, you should be able to successfully adapt the ClimateGPT emissions server to work with your custom SQLite database. Remember to thoroughly test each component after modification to ensure everything works together correctly.