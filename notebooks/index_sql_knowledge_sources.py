"""
Creates an IndexedSqlKnowledgeSource in Azure AI Search for every SQL table.

FDIC tables   → rich text content (NAME, CITY, STALP, ZIP)
FRED tables   → date column only (value cols are float, not indexable as text)
               Note: for querying FRED numeric values, use the SQL service directly.

Run: python notebooks/index_sql_knowledge_sources.py
"""

import os
from dotenv import load_dotenv
load_dotenv()

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    AzureOpenAIVectorizerParameters,
    ContentColumnMapping,
    EmbeddingColumnMapping,
    IndexedSqlKnowledgeSource,
    IndexedSqlKnowledgeSourceParameters,
)
from azure.search.documents.knowledgebases.models import (
    KnowledgeSourceAzureOpenAIVectorizer,
    KnowledgeSourceIngestionParameters,
)

# ── credentials — loaded from .env, no hardcoded fallbacks ────────────────────
SEARCH_URL      = os.environ["SEARCH_SERVICE_URL"]
SEARCH_API_KEY  = os.environ["SEARCH_SERVICE_API_KEY"]
FOUNDRY_ENDPOINT= os.environ["FOUNDRY_PROJECT_ENDPOINT"]
FOUNDRY_API_KEY = os.environ["FOUNDRY_MODEL_API_KEY"]
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-small")

SQL_CONNECTION  = os.environ["SQL_CONNECTION_STRING"]

# ── table definitions ──────────────────────────────────────────────────────────
# content_cols: (column_name, Edm_type) — varchar columns only
# embed_col   : column whose text will be vectorised
TABLE_CONFIGS = {
    "fdic_institutions": {
        "description": "FDIC bank institutions — name, state, assets, deposits",
        "content_cols": [("NAME", "Edm.String"), ("STALP", "Edm.String")],
        "embed_col": "NAME",
    },
    "fdic_locations": {
        "description": "FDIC bank branch locations — name, city, state, ZIP",
        "content_cols": [
            ("NAME", "Edm.String"),
            ("CITY", "Edm.String"),
            ("STALP", "Edm.String"),
            ("ZIP", "Edm.String"),
        ],
        "embed_col": "NAME",
    },
    "fdic_financials": {
        "description": "FDIC bank financial reports — name, report ID, ROA, ROE",
        "content_cols": [("NAME", "Edm.String"), ("ID", "Edm.String")],
        "embed_col": "NAME",
    },
    # FRED time-series — only OBSERVATION_DATE is varchar; numeric values are float
    # These are indexed by date; use the SQL service to query actual values.
    "fred_fedfunds":      {"description": "Federal Funds Rate time series",                   "content_cols": [("OBSERVATION_DATE", "Edm.String")], "embed_col": "OBSERVATION_DATE"},
    "fred_dgs10":         {"description": "10-Year Treasury Constant Maturity Rate",          "content_cols": [("OBSERVATION_DATE", "Edm.String")], "embed_col": "OBSERVATION_DATE"},
    "fred_cpi":           {"description": "Consumer Price Index (CPIAUCSL) time series",      "content_cols": [("OBSERVATION_DATE", "Edm.String")], "embed_col": "OBSERVATION_DATE"},
    "fred_unemployment":  {"description": "Unemployment Rate (UNRATE) time series",           "content_cols": [("OBSERVATION_DATE", "Edm.String")], "embed_col": "OBSERVATION_DATE"},
    "fred_gdp":           {"description": "US GDP time series",                               "content_cols": [("OBSERVATION_DATE", "Edm.String")], "embed_col": "OBSERVATION_DATE"},
    "fred_bank_credit":   {"description": "Bank Credit of All Commercial Banks time series",  "content_cols": [("OBSERVATION_DATE", "Edm.String")], "embed_col": "OBSERVATION_DATE"},
    "fred_mortgage":      {"description": "30-Year Fixed Rate Mortgage Average time series",  "content_cols": [("OBSERVATION_DATE", "Edm.String")], "embed_col": "OBSERVATION_DATE"},
    "fred_delinquency":   {"description": "Delinquency Rate on Consumer Loans time series",   "content_cols": [("OBSERVATION_DATE", "Edm.String")], "embed_col": "OBSERVATION_DATE"},
    "fred_health_spending":{"description": "Health Care Expenditures time series",            "content_cols": [("OBSERVATION_DATE", "Edm.String")], "embed_col": "OBSERVATION_DATE"},
    "fred_exchange":      {"description": "US/Euro Exchange Rate (DEXUSEU) time series",      "content_cols": [("OBSERVATION_DATE", "Edm.String")], "embed_col": "OBSERVATION_DATE"},
}


def create_knowledge_source(
    client: SearchIndexClient,
    table_name: str,
    config: dict,
) -> None:
    embedding_params = AzureOpenAIVectorizerParameters(
        resource_url=FOUNDRY_ENDPOINT,
        deployment_name=EMBEDDING_MODEL,
        model_name=EMBEDDING_MODEL,
        api_key=FOUNDRY_API_KEY,
    )

    ingestion_params = KnowledgeSourceIngestionParameters(
        content_extraction_mode="minimal",
        embedding_model=KnowledgeSourceAzureOpenAIVectorizer(
            azure_open_ai_parameters=embedding_params
        ),
    )

    knowledge_source = IndexedSqlKnowledgeSource(
        name=f"ks-{table_name}",
        description=config["description"],
        indexed_sql_parameters=IndexedSqlKnowledgeSourceParameters(
            connection_string=SQL_CONNECTION,
            table_or_view=f"dbo.{table_name}",
            content_columns=[
                ContentColumnMapping(
                    name=col_name.lower(),
                    source_field=col_name,
                    search_field_type=edm_type,
                )
                for col_name, edm_type in config["content_cols"]
            ],
            embedding_columns=[
                EmbeddingColumnMapping(
                    name=f"{config['embed_col'].lower()}_vector",
                    source_field=config["embed_col"],
                )
            ],
            ingestion_parameters=ingestion_params,
        ),
    )

    client.create_or_update_knowledge_source(knowledge_source=knowledge_source)
    print(f"  OK  ks-{table_name}")


def main():
    index_client = SearchIndexClient(
        endpoint=SEARCH_URL,
        credential=AzureKeyCredential(SEARCH_API_KEY),
    )

    print(f"Creating {len(TABLE_CONFIGS)} knowledge sources...\n")
    errors = []
    for table_name, config in TABLE_CONFIGS.items():
        try:
            create_knowledge_source(index_client, table_name, config)
        except Exception as e:
            print(f"  FAIL  ks-{table_name}: {e}")
            errors.append(table_name)

    print(f"\nDone. {len(TABLE_CONFIGS) - len(errors)} created, {len(errors)} failed.")
    if errors:
        print(f"Failed tables: {errors}")


if __name__ == "__main__":
    main()
