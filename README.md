# Olist E-Commerce — Project B

An Information Technology course project that transforms Olist's public e-commerce dataset into a PostgreSQL relational database and presents its results through an interactive dashboard.

**Authors:** Beñat Ilzarbe Daza and Nora Cepas Zapico.

## Overview

The project includes:

- SQL-based profiling of the original data.
- Relational database design and implementation with integrity constraints.
- Python data loading within a single transaction.
- A cleaning log recording the rules applied and affected row counts.
- Ten analytical queries and a data modification transaction.
- An interactive dashboard with charts and parameterized SQL filters.

Data analysis, aggregation and joins are performed in SQL. Python handles data loading, query execution and visualization.

## Technologies

- PostgreSQL
- Python
- psycopg2
- Streamlit
- Plotly

## Repository Structure

```text
app/
    app.py                 # Interactive dashboard
    db.py                  # Database connection and query execution
    queries.py             # Parameterized dashboard queries
etl/
    download_data.py       # CSV download and extraction
    load_raw.py            # Raw data loading for profiling
    load.py                # Data cleaning and final database loading
sql/
    raw_schema.sql         # Raw data schema
    profiling.sql          # Data profiling queries
    schema.sql             # Final tables and constraints
    queries.sql            # Project queries
docs/
    cleaning_log.md        # Cleaning rules and row counts
.env.example               # Connection configuration template
.gitignore
requirements.txt
README.md
```

The `data/` directory is created locally and is excluded from the repository.

## Dataset

This project uses the **Brazilian E-Commerce Public Dataset by Olist**, available on Kaggle:

[Olist Dataset on Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)

It includes customers, orders, products, sellers, payments, reviews, geolocation records and product category translations.

The data remains subject to the license and terms published by its original source.

## Setup

Run all commands from the project's root directory. The examples below use Windows PowerShell.

### 1. Set Up Python

Install Python and PostgreSQL. The database commands also require `psql` to be available in your terminal.

Create a virtual environment and install the application dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The following commands use the virtual environment's Python executable directly, so activation is not required.

### 2. Configure the Database Connection

Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

Edit `.env` with your local PostgreSQL settings:

```dotenv
PGHOST=localhost
PGPORT=5432
PGDATABASE=olist
PGUSER=postgres
PGPASSWORD=your_password_here
```

The Python scripts read this file automatically. Do not commit `.env` to the repository.

### 3. Download the Dataset

To download the dataset automatically:

```powershell
.\.venv\Scripts\python.exe -m pip install kagglehub
.\.venv\Scripts\python.exe etl/download_data.py
```

`kagglehub` is an additional dependency required for automatic downloading.

Alternatively, download the dataset ZIP from Kaggle and run:

```powershell
.\.venv\Scripts\python.exe etl/download_data.py --zip "C:\path\archive.zip"
```

Both methods place the CSV files in `data/raw/`.

### 4. Create the Database

Create an empty database named `olist` using pgAdmin or the following command:

```powershell
psql -h localhost -p 5432 -U postgres -d postgres -c "CREATE DATABASE olist;"
```

The following `psql` commands use the connection values from `.env.example`. Adjust them if you use a different host, port, username or database name.

`psql` may prompt for your password; it does not automatically read the project's `.env` file.

### 5. Profile the Raw Data

Create the raw schema, load the original CSV files and run the profiling queries:

```powershell
psql -h localhost -p 5432 -U postgres -d olist -v ON_ERROR_STOP=1 -f sql/raw_schema.sql
.\.venv\Scripts\python.exe etl/load_raw.py
psql -h localhost -p 5432 -U postgres -d olist -v ON_ERROR_STOP=1 -f sql/profiling.sql
```

The `raw` schema is used to examine the original data before transformation.

**Warning:** `raw_schema.sql` drops and recreates the `raw` schema. Do not repeat the raw loading step on tables that already contain data.

### 6. Create the Final Schema

```powershell
psql -h localhost -p 5432 -U postgres -d olist -v ON_ERROR_STOP=1 -f sql/schema.sql
```

**Warning:** this script drops and recreates the final model's tables. Run it only against the database intended for this project.

### 7. Demonstrate Transaction Rollback

With the final tables empty, run:

```powershell
.\.venv\Scripts\python.exe etl/load.py --simulate-error
```

The script loads the dataset and then attempts to insert a review with an invalid score. The resulting constraint violation rolls back the entire load and displays the row counts afterwards.

This command intentionally exits with an error. The final tables should remain empty.

### 8. Load the Data

After the rollback demonstration, run the normal load:

```powershell
.\.venv\Scripts\python.exe etl/load.py
```

The entire load is committed in a single transaction. If an error occurs, all changes made by that transaction are rolled back.

The script generates `docs/cleaning_log.md`, documenting the cleaning rules and row counts.

### 9. Start the Dashboard

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/app.py
```

Open the address displayed by Streamlit in your browser.

## Dashboard

The application presents results covering:

- Revenue by product category.
- Monthly revenue and growth.
- Delivery times by state.
- Delivery delays and customer satisfaction.
- Payment methods.
- Customer purchase frequency.
- Leading sellers by revenue within a state.
- Seller–customer distance and shipping costs.

Filter values are passed to PostgreSQL as SQL parameters. The dashboard uses a read-only database connection.

## SQL Queries

`sql/queries.sql` contains the project queries, identified by question and author.

The query set includes:

- JOINs.
- GROUP BY and HAVING.
- Subqueries.
- Window functions.
- Common Table Expressions using WITH.
- INSERT, UPDATE and DELETE statements within a transaction.

The queries can be reviewed and executed in pgAdmin against the project database.

## Data Cleaning and Integrity

The loading process:

- Preserves missing values as `NULL`.
- Removes exact duplicate geolocation records.
- Separates customer identity from order-associated customer identifiers.
- Preserves missing category translations as `NULL`.
- Corrects original column names containing `lenght`.

Tables and constraints are created before loading through `sql/schema.sql`. The ETL inserts data into the existing schema.

## Excluded Files

The following files and directories should not be committed:

- Original datasets in `data/`.
- Credentials stored in `.env`.
- Virtual environments such as `.venv/`.
- `__pycache__/` directories and `.pyc` files.
- Windows metadata files such as `desktop.ini`.

The PDF report, presentation slides and team contribution log are separate project submission materials.
