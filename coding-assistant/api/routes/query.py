from fastapi import APIRouter
router = APIRouter()
from services.dataset_store import get_schema, validate_sql, execute_sql
from services.llm import run_text_to_sql


def answer_question(question: str) -> dict:
    schema = get_schema()
    sql_query = run_text_to_sql(question, schema)

    try:
        safe_sql = validate_sql(sql_query)
    except ValueError as error:
        return {"error": str(error), "sql_query": sql_query}

    result = execute_sql(safe_sql)

    return {
       "sql_query": safe_sql,
       "columns": result["columns"],
       "rows": result["rows"],
    }


@router.post("/ask")
def ask_query(query: str):
    return answer_question(query)
