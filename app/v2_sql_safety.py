"""
Enhanced SQL safety validation for PATAS v2.

Validates that SQL rules are safe SELECT queries only,
and detects dangerous patterns like "match everything".

SAFETY CONSTRAINTS:
- Only SELECT queries over whitelisted tables/columns
- No UPDATE/DELETE/INSERT/ALTER, no semicolons, no subqueries
- "Match-everything" rules are detected and rejected
- Coverage limits (>80% of all messages = red flag)
"""
import re
import logging
from typing import Tuple, Optional, List, Set
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

try:
    import sqlparse
    from sqlparse import tokens as sqlparse_tokens
    SQLPARSE_AVAILABLE = True
except ImportError:
    SQLPARSE_AVAILABLE = False
    sqlparse_tokens = None

logger = logging.getLogger(__name__)

if not SQLPARSE_AVAILABLE:
    logger.warning("sqlparse not available, falling back to regex-based validation")

# Whitelisted tables (only these tables can be queried)
ALLOWED_TABLES = {"messages", "reports"}  # Add more as needed

# Whitelisted columns (only these columns can be selected/referenced)
ALLOWED_COLUMNS = {
    "id", "text", "is_spam", "timestamp", "language", 
    "sender", "source", "country", "has_media",
    "label_spam", "label_not_spam", "message_content",
    "created_at", "updated_at",
}

# Maximum allowed coverage (if rule matches >80% of messages, reject it)
MAX_COVERAGE_THRESHOLD = 0.80  # 80%


class SQLSafetyError(Exception):
    """Raised when SQL validation fails."""
    pass


def validate_sql_rule(sql_expression: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that SQL expression is a safe SELECT query.
    
    SAFETY CHECKS:
    1. Only SELECT queries (no UPDATE/DELETE/INSERT/ALTER)
    2. Only whitelisted tables and columns
    3. No semicolons (prevents command chaining)
    4. No subqueries (prevents complex injection)
    5. No "match everything" patterns (WHERE 1=1, empty WHERE, etc.)
    
    Args:
        sql_expression: SQL query to validate
    
    Returns:
        (is_valid, error_message)
    """
    sql_upper = sql_expression.upper().strip()
    
    # 1. Must start with SELECT or WITH (CTE)
    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        return False, "SQL must be a SELECT query (starts with SELECT or WITH)"
    
    # 2. Disallow dangerous operations
    dangerous_keywords = [
        "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE",
        "TRUNCATE", "EXEC", "EXECUTE", "CALL", "MERGE", "REPLACE",
    ]
    for keyword in dangerous_keywords:
        # Check for keyword as a standalone word (not part of another word)
        pattern = r"\b" + keyword + r"\b"
        if re.search(pattern, sql_upper):
            return False, f"Dangerous SQL keyword detected: {keyword}"
    
    # 3. Disallow semicolons (prevents command chaining)
    if ";" in sql_expression:
        return False, "Semicolons are not allowed (prevents command chaining)"
    
    # 4. Disallow subqueries (prevents complex injection)
    # Use sqlparse if available for more accurate detection
    if SQLPARSE_AVAILABLE:
        if _has_subqueries(sql_expression):
            return False, "Subqueries are not allowed (prevents complex SQL injection)"
    else:
        # Fallback to regex heuristic
        subquery_pattern = r"\(\s*SELECT\s+"
        if re.search(subquery_pattern, sql_upper, re.DOTALL):
            return False, "Subqueries are not allowed (prevents complex SQL injection)"
    
    # 5. Disallow UNION SELECT (potential injection)
    if re.search(r"\bUNION\s+SELECT\b", sql_upper):
        return False, "UNION SELECT is not allowed (potential SQL injection)"
    
    # 6. Check for SQL injection patterns
    injection_patterns = [
        r"';?\s*(?:--|#|/\*|\*/)",
        r"';?\s*OR\s+1\s*=\s*1",
        r"';?\s*AND\s+1\s*=\s*1",
        r"';?\s*OR\s+'[^']*'\s*=\s*'[^']*'",
    ]
    for pattern in injection_patterns:
        if re.search(pattern, sql_expression, re.IGNORECASE):
            return False, f"Potential SQL injection pattern detected: {pattern}"
    
    # 7. Check for whitelisted tables
    table_check = _check_whitelisted_tables(sql_expression)
    if not table_check[0]:
        return False, table_check[1]
    
    # 8. Check for whitelisted columns
    column_check = _check_whitelisted_columns(sql_expression)
    if not column_check[0]:
        return False, column_check[1]
    
    # 9. Check for "match everything" patterns
    if _is_match_everything(sql_expression):
        return False, "SQL rule matches everything (too broad, would block all messages)"
    
    return True, None


def _check_whitelisted_tables(sql_expression: str) -> Tuple[bool, Optional[str]]:
    """
    Check that only whitelisted tables are referenced.
    
    Returns:
        (is_valid, error_message)
    """
    if SQLPARSE_AVAILABLE:
        tables = _extract_tables_sqlparse(sql_expression)
    else:
        # Fallback to regex
        sql_upper = sql_expression.upper()
        tables = re.findall(r"FROM\s+(\w+)", sql_upper)
    
    for table in tables:
        table_lower = table.lower()
        if table_lower not in ALLOWED_TABLES:
            return False, f"Table '{table}' is not whitelisted. Allowed tables: {', '.join(ALLOWED_TABLES)}"
    
    return True, None


def _check_whitelisted_columns(sql_expression: str) -> Tuple[bool, Optional[str]]:
    """
    Check that only whitelisted columns are referenced.
    
    Uses sqlparse if available for accurate column extraction.
    
    Returns:
        (is_valid, error_message)
    """
    if SQLPARSE_AVAILABLE:
        try:
            return _check_whitelisted_columns_sqlparse(sql_expression)
        except Exception as e:
            logger.warning(f"Error checking columns with sqlparse: {e}, falling back to regex")
    
    # Fallback to regex
    return _check_whitelisted_columns_regex(sql_expression)


def _check_whitelisted_columns_sqlparse(sql_expression: str) -> Tuple[bool, Optional[str]]:
    """
    Check whitelisted columns using sqlparse.
    
    Returns:
        (is_valid, error_message)
    """
    parsed = sqlparse.parse(sql_expression)
    if not parsed:
        return True, None  # Empty query is valid
    
    for statement in parsed:
        # Extract columns from SELECT clause
        select_columns = _extract_select_columns_sqlparse(statement)
        for col in select_columns:
            if col == "*":
                continue  # SELECT * is allowed
            col_lower = col.lower()
            # Skip SQL keywords and functions
            if col_lower in {"as", "distinct", "count", "sum", "avg", "max", "min", "lower", "upper"}:
                continue
            if col_lower not in ALLOWED_COLUMNS:
                # Check if it's a function call like LOWER(text)
                if "(" in col:
                    # Extract column from function call
                    func_col = col.split("(")[1].split(")")[0].strip()
                    func_col = func_col.split(".")[-1]  # Remove table prefix
                    if func_col.lower() not in ALLOWED_COLUMNS:
                        return False, f"Column '{col}' is not whitelisted. Allowed columns: {', '.join(sorted(ALLOWED_COLUMNS))}"
                else:
                    return False, f"Column '{col}' is not whitelisted. Allowed columns: {', '.join(sorted(ALLOWED_COLUMNS))}"
        
        # Extract columns from WHERE clause
        where_columns = _extract_where_columns_sqlparse(statement)
        for col_ref in where_columns:
            col_lower = col_ref.lower()
            # Skip SQL keywords
            sql_keywords = {
                "and", "or", "not", "like", "regexp", "in", "is", "null", "true", "false",
                "where", "select", "from", "between", "exists"
            }
            if col_lower in sql_keywords:
                continue
            # Skip function names
            functions = {"lower", "upper", "count", "sum", "avg", "max", "min", "length", "substr", "trim"}
            if col_lower in functions:
                continue
            # Check if it's a whitelisted column
            if col_lower not in ALLOWED_COLUMNS:
                # Allow table.column patterns if table is whitelisted
                if "." in col_ref:
                    parts = col_ref.split(".", 1)
                    if len(parts) == 2:
                        table, col = parts
                        if table.lower() in ALLOWED_TABLES and col.lower() in ALLOWED_COLUMNS:
                            continue
                return False, f"Column '{col_ref}' in WHERE clause is not whitelisted. Allowed columns: {', '.join(sorted(ALLOWED_COLUMNS))}"
    
    return True, None


def _extract_select_columns_sqlparse(statement) -> List[str]:
    """Extract column names from SELECT clause using sqlparse."""
    columns = []
    in_select = False
    select_tokens = []
    
    for token in statement.flatten():
        if token.ttype is sqlparse_tokens.Keyword and token.value.upper() == "SELECT":
            in_select = True
            continue
        elif in_select:
            if token.ttype is sqlparse_tokens.Keyword and token.value.upper() == "FROM":
                break
            if token.ttype is None and token.value.strip():
                select_tokens.append(token.value.strip())
    
    # Parse column list
    for token_str in select_tokens:
        # Split by comma
        for col in token_str.split(","):
            col = col.strip()
            if not col:
                continue
            # Remove aliases (AS alias)
            col = re.sub(r"\s+AS\s+\w+", "", col, flags=re.IGNORECASE)
            # Remove table prefix
            col = col.split(".")[-1]
            # Extract column name (handle function calls)
            if "(" in col:
                # Function call like LOWER(text) -> extract 'text'
                func_match = re.search(r"\(([^)]+)\)", col)
                if func_match:
                    col = func_match.group(1).strip()
                    col = col.split(".")[-1]
            if col and col not in columns:
                columns.append(col)
    
    return columns


def _extract_where_columns_sqlparse(statement) -> List[str]:
    """Extract column names from WHERE clause using sqlparse.
    
    Improved to handle:
    - CASE WHEN expressions
    - COALESCE, NULLIF, and other functions
    - Nested conditions
    - Table.column references
    """
    columns = []
    in_where = False
    where_tokens = []
    
    for token in statement.flatten():
        if token.ttype is sqlparse_tokens.Keyword and token.value.upper() == "WHERE":
            in_where = True
            continue
        elif in_where:
            if token.ttype is sqlparse_tokens.Keyword and token.value.upper() in ("ORDER", "GROUP", "LIMIT", "HAVING"):
                break
            if token.ttype is None and token.value.strip():
                where_tokens.append(token.value.strip())
    
    # Extract column references from WHERE clause
    where_clause = " ".join(where_tokens)
    
    # SQL keywords and functions to skip
    sql_keywords = {
        "and", "or", "not", "like", "regexp", "in", "is", "null", "true", "false",
        "where", "select", "from", "between", "exists", "case", "when", "then",
        "else", "end", "coalesce", "nullif", "ifnull", "if", "as"
    }
    sql_functions = {
        "lower", "upper", "count", "sum", "avg", "max", "min", "length", "substr",
        "trim", "ltrim", "rtrim", "replace", "coalesce", "nullif", "ifnull", "abs",
        "round", "cast", "convert"
    }
    
    # Pattern 1: Simple column references: column_name, column_name =, column_name LIKE
    # Match: column_name followed by operator or function
    simple_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:[=<>!]|LIKE|REGEXP|IN|IS|BETWEEN)'
    simple_matches = re.findall(simple_pattern, where_clause, re.IGNORECASE)
    for match in simple_matches:
        if match.lower() not in sql_keywords and match.lower() not in sql_functions:
            columns.append(match)
    
    # Pattern 2: Table.column references
    table_column_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\.\s*([a-zA-Z_][a-zA-Z0-9_]*)'
    table_column_matches = re.findall(table_column_pattern, where_clause, re.IGNORECASE)
    for table, col in table_column_matches:
        if col.lower() not in sql_keywords:
            columns.append(f"{table}.{col}")
    
    # Pattern 3: Function calls: LOWER(column), COALESCE(column1, column2), etc.
    # Extract column from function calls like: FUNCTION(column) or FUNCTION(table.column)
    function_pattern = r'\b(?:' + '|'.join(sql_functions) + r')\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)'
    function_matches = re.findall(function_pattern, where_clause, re.IGNORECASE)
    for match in function_matches:
        if match.lower() not in sql_keywords:
            columns.append(match)
    
    # Pattern 4: CASE WHEN expressions: CASE WHEN column THEN ... END
    case_pattern = r'CASE\s+(?:WHEN\s+)?([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)'
    case_matches = re.findall(case_pattern, where_clause, re.IGNORECASE)
    for match in case_matches:
        if match.lower() not in sql_keywords:
            columns.append(match)
    
    # Pattern 5: Column references in parentheses (for grouping)
    paren_pattern = r'\(\s*([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)\s*\)'
    paren_matches = re.findall(paren_pattern, where_clause, re.IGNORECASE)
    for match in paren_matches:
        if match.lower() not in sql_keywords and match.lower() not in sql_functions:
            columns.append(match)
    
    return list(set(columns))  # Remove duplicates


def _check_whitelisted_columns_regex(sql_expression: str) -> Tuple[bool, Optional[str]]:
    """
    Check whitelisted columns using regex (fallback).
    
    Returns:
        (is_valid, error_message)
    """
    sql_upper = sql_expression.upper()
    
    # Check SELECT columns
    select_match = re.search(r"SELECT\s+(.+?)\s+FROM", sql_upper, re.DOTALL)
    if select_match:
        columns_str = select_match.group(1)
        # Allow SELECT * for now (will be checked in WHERE clause)
        if "*" not in columns_str:
            # Extract column names (simple heuristic)
            columns = re.findall(r"\b(\w+)\b", columns_str)
            for col in columns:
                col_lower = col.lower()
                # Skip SQL keywords
                if col_lower in {"as", "distinct", "count", "sum", "avg", "max", "min"}:
                    continue
                if col_lower not in ALLOWED_COLUMNS and col_lower not in {"id", "is_spam"}:
                    # Allow common patterns like LOWER(text), COUNT(*), etc.
                    if not re.match(r"^(lower|upper|count|sum|avg|max|min)\s*\(", col_lower):
                        return False, f"Column '{col}' is not whitelisted. Allowed columns: {', '.join(sorted(ALLOWED_COLUMNS))}"
    
    # Check WHERE clause columns (more important for safety)
    where_match = re.search(r"WHERE\s+(.+?)(?:\s+ORDER|\s+GROUP|\s+LIMIT|$)", sql_upper, re.DOTALL | re.IGNORECASE)
    if where_match:
        where_clause = where_match.group(1)
        # Extract column references (simple heuristic)
        # Look for patterns like "column_name", "table.column", "LOWER(column)"
        column_refs = re.findall(r"(?:^|\s|\(|,)(\w+)(?:\s*=|\.|\)|,|$)", where_clause, re.IGNORECASE)
        for col_ref in column_refs:
            col_lower = col_ref.lower()
            # Skip SQL keywords and operators
            if col_lower in {"and", "or", "not", "like", "regexp", "in", "is", "null", "true", "false", "where", "select", "from"}:
                continue
            # Skip function names
            if col_lower in {"lower", "upper", "count", "sum", "avg", "max", "min", "length", "substr"}:
                continue
            # Check if it's a whitelisted column
            if col_lower not in ALLOWED_COLUMNS:
                # Allow table.column patterns if table is whitelisted
                if "." in col_ref:
                    table, col = col_ref.split(".", 1)
                    if table.lower() in ALLOWED_TABLES and col.lower() in ALLOWED_COLUMNS:
                        continue
                return False, f"Column '{col_ref}' in WHERE clause is not whitelisted. Allowed columns: {', '.join(sorted(ALLOWED_COLUMNS))}"
    
    return True, None


def _is_match_everything(sql_expression: str) -> bool:
    """
    Detect if SQL rule would match everything (too broad).
    
    Patterns that indicate "match everything":
    - WHERE 1=1
    - WHERE TRUE
    - WHERE condition OR TRUE
    - Empty WHERE clause (SELECT * FROM messages;)
    - WHERE condition that's always true
    """
    sql_upper = sql_expression.upper()
    
    # Check for explicit "match everything" patterns
    match_everything_patterns = [
        r"WHERE\s+1\s*=\s*1\b",
        r"WHERE\s+TRUE\b",
        r"WHERE\s+1\s*=\s*1\s*;",
        r"WHERE\s+TRUE\s*;",
        r"WHERE\s+.*\s+OR\s+TRUE\b",
        r"WHERE\s+.*\s+OR\s+1\s*=\s*1\b",
    ]
    
    for pattern in match_everything_patterns:
        if re.search(pattern, sql_upper):
            return True
    
    # Check if WHERE clause is missing (SELECT * FROM messages without WHERE)
    # This is dangerous as it would match everything
    if "FROM" in sql_upper and "WHERE" not in sql_upper:
        # But allow if it's just a comment or explanation
        # Check if there's actual SELECT * FROM table without WHERE
        select_from_pattern = r"SELECT\s+.*\s+FROM\s+\w+\s*(?:ORDER|GROUP|LIMIT|$)"
        if re.search(select_from_pattern, sql_upper, re.IGNORECASE):
            return True
    
    return False


async def check_rule_coverage(
    db: AsyncSession,
    sql_expression: str,
    table_name: str = "messages",
    max_coverage: float = MAX_COVERAGE_THRESHOLD,
) -> Tuple[bool, Optional[str], float]:
    """
    Check if rule matches too many messages (coverage check).
    
    If a rule matches >80% of all messages, it's too broad and should be rejected.
    
    Args:
        db: Database session
        sql_expression: SQL rule to check
        table_name: Table name
        max_coverage: Maximum allowed coverage (default 0.80 = 80%)
    
    Returns:
        (is_valid, error_message, coverage_ratio)
    """
    try:
        # Validate SQL first
        is_valid, error = validate_sql_rule(sql_expression)
        if not is_valid:
            return False, error, 0.0
        
        # Get total message count
        total_count_result = await db.execute(text(f"SELECT COUNT(*) as total FROM {table_name}"))
        total_count = total_count_result.scalar() or 0
        
        if total_count == 0:
            return True, None, 0.0
        
        # Get match count
        sanitized = sanitize_sql_for_evaluation(sql_expression, table_name)
        # Replace SELECT columns with COUNT(*)
        sanitized_upper = sanitized.upper()
        if "SELECT" in sanitized_upper:
            # Replace SELECT ... with SELECT COUNT(*)
            sanitized = re.sub(
                r"SELECT\s+.*?\s+FROM",
                "SELECT COUNT(*) as match_count FROM",
                sanitized,
                flags=re.IGNORECASE | re.DOTALL,
                count=1
            )
            # Remove ORDER BY, LIMIT, etc. (not needed for count)
            sanitized = re.sub(r"\s+ORDER\s+BY.*", "", sanitized, flags=re.IGNORECASE)
            sanitized = re.sub(r"\s+LIMIT\s+\d+", "", sanitized, flags=re.IGNORECASE)
        
        match_count_result = await db.execute(text(sanitized))
        match_count = match_count_result.scalar() or 0
        
        coverage = match_count / total_count if total_count > 0 else 0.0
        
        if coverage > max_coverage:
            return False, f"Rule matches {coverage:.1%} of all messages (>{max_coverage:.1%} threshold, too broad)", coverage
        
        return True, None, coverage
        
    except (ValueError, AttributeError) as e:
        # Handle data/calculation errors
        logger.error(f"Coverage check failed (data error): {e}", exc_info=True)
        return False, f"Coverage check error (data): {str(e)}", 0.0
    except Exception as e:
        # Catch-all for database errors, SQL execution errors, etc.
        logger.error(f"Coverage check failed (unexpected error): {e}", exc_info=True)
        return False, f"Coverage check error: {str(e)}", 0.0


def sanitize_sql_for_evaluation(sql_expression: str, table_name: str = "messages") -> str:
    """
    Sanitize SQL expression for safe evaluation.
    
    Ensures:
    - Only SELECT queries
    - References correct table name
    - Returns message IDs for evaluation
    
    Uses sqlparse if available for accurate table name replacement.
    
    Args:
        sql_expression: Original SQL expression
        table_name: Target table name (default: "messages")
    
    Returns:
        Sanitized SQL expression
    """
    # Validate first
    is_valid, error = validate_sql_rule(sql_expression)
    if not is_valid:
        raise SQLSafetyError(f"SQL validation failed: {error}")
    
    if SQLPARSE_AVAILABLE:
        try:
            return _sanitize_sql_sqlparse(sql_expression, table_name)
        except Exception as e:
            logger.warning(f"Error sanitizing SQL with sqlparse: {e}, falling back to regex")
    
    # Fallback to regex-based replacement
    sql_upper = sql_expression.upper()
    
    # If SQL references a different table, replace it
    if "FROM" in sql_upper:
        # Simple replacement: FROM <old_table> -> FROM messages
        # But be careful not to replace table names in comments
        lines = sql_expression.split("\n")
        sanitized_lines = []
        for line in lines:
            if line.strip().startswith("--"):
                # Keep comments as-is
                sanitized_lines.append(line)
            else:
                # Replace table name in FROM clause (simple heuristic)
                if "FROM" in line.upper():
                    # Try to replace common table names
                    line = re.sub(
                        r"FROM\s+(\w+)\s*",
                        f"FROM {table_name} ",
                        line,
                        flags=re.IGNORECASE,
                        count=1
                    )
                sanitized_lines.append(line)
        return "\n".join(sanitized_lines)
    
    return sql_expression


def _sanitize_sql_sqlparse(sql_expression: str, table_name: str) -> str:
    """
    Sanitize SQL using sqlparse for accurate table name replacement.
    
    Args:
        sql_expression: Original SQL expression
        table_name: Target table name
    
    Returns:
        Sanitized SQL expression
    """
    parsed = sqlparse.parse(sql_expression)
    if not parsed:
        return sql_expression
    
    # Reconstruct SQL with replaced table name
    result_parts = []
    
    for statement in parsed:
        tokens = list(statement.flatten())
        in_from = False
        table_replaced = False
        
        for i, token in enumerate(tokens):
            if token.ttype is sqlparse_tokens.Keyword and token.value.upper() == "FROM":
                in_from = True
                result_parts.append(token.value)
                continue
            elif in_from and not table_replaced:
                if token.ttype is None and token.value.strip():
                    # This is the table name
                    result_parts.append(f" {table_name}")
                    table_replaced = True
                    in_from = False
                    continue
            elif in_from:
                # Skip until we find table name or next keyword
                if token.ttype is sqlparse_tokens.Keyword:
                    in_from = False
                    result_parts.append(token.value)
                continue
            
            result_parts.append(token.value if token.value else "")
    
    return "".join(result_parts)


async def test_sql_on_sample(
    db: AsyncSession,
    sql_expression: str,
    table_name: str = "messages",
    limit: int = 10,
) -> Tuple[bool, Optional[str], int]:
    """
    Test SQL expression on a small sample of data.
    
    Args:
        db: Database session
        sql_expression: SQL to test
        table_name: Table name
        limit: Maximum number of rows to return
    
    Returns:
        (is_valid, error_message, row_count)
    """
    try:
        # Validate SQL first
        is_valid, error = validate_sql_rule(sql_expression)
        if not is_valid:
            return False, error, 0
        
        # Sanitize SQL
        sanitized = sanitize_sql_for_evaluation(sql_expression, table_name)
        
        # Add LIMIT for safety
        if "LIMIT" not in sanitized.upper():
            # Try to add LIMIT before semicolon or at the end
            if sanitized.rstrip().endswith(";"):
                sanitized = sanitized.rstrip()[:-1] + f" LIMIT {limit};"
            else:
                sanitized = sanitized.rstrip() + f" LIMIT {limit}"
        
        # Execute query
        result = await db.execute(text(sanitized))
        rows = result.fetchall()
        
        return True, None, len(rows)
        
    except (ValueError, AttributeError) as e:
        # Handle data/calculation errors
        logger.error(f"SQL test execution failed (data error): {e}", exc_info=True)
        return False, f"SQL test error (data): {str(e)}", 0
    except Exception as e:
        # Catch-all for database errors, SQL execution errors, etc.
        logger.error(f"SQL test execution failed (unexpected error): {e}", exc_info=True)
        return False, str(e), 0


def _has_subqueries(sql_expression: str) -> bool:
    """
    Check if SQL contains subqueries using sqlparse.
    
    Returns:
        True if subqueries are found
    """
    if not SQLPARSE_AVAILABLE:
        return False
    
    try:
        parsed = sqlparse.parse(sql_expression)
        if not parsed:
            return False
        
        for statement in parsed:
            # Walk through tokens to find subqueries
            for token in statement.flatten():
                if token.ttype is None and token.is_group:
                    # Check if this group contains a SELECT statement
                    if _contains_select_in_group(token):
                        return True
        return False
    except Exception as e:
        logger.warning(f"Error parsing SQL for subquery detection: {e}, falling back to regex")
        # Fallback to regex
        subquery_pattern = r"\(\s*SELECT\s+"
        return bool(re.search(subquery_pattern, sql_expression.upper(), re.DOTALL))


def _contains_select_in_group(token) -> bool:
    """Recursively check if a token group contains a SELECT statement."""
    if not SQLPARSE_AVAILABLE or not token.is_group:
        return False
    
    # Check if this group starts with SELECT
    tokens = list(token.flatten())
    found_select = False
    for t in tokens:
        if t.ttype is sqlparse_tokens.Keyword and t.value.upper() == "SELECT":
            found_select = True
        elif found_select and t.ttype is sqlparse_tokens.Keyword and t.value.upper() in ("FROM", "WHERE"):
            # Found SELECT ... FROM/WHERE pattern, this is a subquery
            return True
    
    return False


def _extract_tables_sqlparse(sql_expression: str) -> List[str]:
    """
    Extract table names from SQL using sqlparse.
    
    Returns:
        List of table names
    """
    if not SQLPARSE_AVAILABLE:
        return []
    
    try:
        parsed = sqlparse.parse(sql_expression)
        if not parsed:
            return []
        
        tables = []
        for statement in parsed:
            # Find FROM tokens
            from_seen = False
            for token in statement.flatten():
                if token.ttype is sqlparse_tokens.Keyword and token.value.upper() == "FROM":
                    from_seen = True
                elif from_seen and token.ttype is None:
                    # This is likely a table name
                    table_name = token.value.strip().split()[0]  # Get first word (handle aliases)
                    if table_name and table_name not in tables:
                        tables.append(table_name)
                    from_seen = False
        
        return tables
    except Exception as e:
        logger.warning(f"Error extracting tables with sqlparse: {e}, falling back to regex")
        # Fallback to regex
        sql_upper = sql_expression.upper()
        return re.findall(r"FROM\s+(\w+)", sql_upper)


async def check_sql_performance(
    db: AsyncSession,
    sql_expression: str,
    table_name: str = "messages",
    max_operations: int = 1000,
) -> Tuple[bool, Optional[str], int]:
    """
    Check SQL query performance using EXPLAIN QUERY PLAN.
    
    Args:
        db: Database session
        sql_expression: SQL query to check
        table_name: Table name
        max_operations: Maximum allowed operations (default: 1000)
    
    Returns:
        (is_valid, error_message, operation_count)
    """
    try:
        # Validate SQL first
        is_valid, error = validate_sql_rule(sql_expression)
        if not is_valid:
            return False, error, 0
        
        # Sanitize SQL for evaluation
        sanitized = sanitize_sql_for_evaluation(sql_expression, table_name)
        
        # Use EXPLAIN QUERY PLAN to estimate cost
        # SQLite-specific, but gives good estimate
        explain_sql = f"EXPLAIN QUERY PLAN {sanitized}"
        
        try:
            result = await db.execute(text(explain_sql))
            rows = result.fetchall()
            
            # Count operations (simplified: count rows in EXPLAIN output)
            # In SQLite, more rows = more operations
            operation_count = len(rows)
            
            # Also check for expensive operations (SCAN TABLE, SORT, etc.)
            explain_text = "\n".join([str(row) for row in rows])
            expensive_ops = ["SCAN TABLE", "SORT", "TEMPORARY", "SUBQUERY"]
            expensive_count = sum(1 for op in expensive_ops if op in explain_text.upper())
            
            # Weight expensive operations more
            total_cost = operation_count + (expensive_count * 10)
            
            if total_cost > max_operations:
                return False, f"SQL query too expensive (estimated {total_cost} operations, max {max_operations})", total_cost
            
            return True, None, total_cost
            
        except Exception as e:
            # If EXPLAIN fails, log warning but don't reject (might be DB-specific)
            logger.warning(f"Could not check SQL performance: {e}")
            return True, None, 0  # Allow query if we can't check performance
            
    except Exception as e:
        logger.error(f"SQL performance check failed: {e}", exc_info=True)
        return False, f"Performance check error: {str(e)}", 0


def extract_select_columns(sql_expression: str) -> List[str]:
    """
    Extract column names from SELECT statement.
    
    Uses sqlparse if available, otherwise falls back to regex.
    
    Returns:
        List of column names or ["*"] if SELECT *
    """
    if SQLPARSE_AVAILABLE:
        try:
            parsed = sqlparse.parse(sql_expression)
            if not parsed:
                return []
            
            columns = []
            for statement in parsed:
                # Find SELECT token and extract columns
                select_seen = False
                for token in statement.flatten():
                    if token.ttype is sqlparse_tokens.Keyword and token.value.upper() == "SELECT":
                        select_seen = True
                    elif select_seen:
                        if token.ttype is sqlparse_tokens.Keyword and token.value.upper() == "FROM":
                            break
                        elif token.ttype is None and token.value.strip():
                            # Extract column name
                            col = token.value.strip()
                            # Remove aliases and table prefixes
                            col = re.sub(r"\s+AS\s+\w+", "", col, flags=re.IGNORECASE)
                            col = col.split(".")[-1].split()[0]  # Get column name part
                            if col == "*":
                                return ["*"]
                            if col and col not in columns:
                                columns.append(col)
            
            return columns if columns else []
        except Exception as e:
            logger.warning(f"Error extracting columns with sqlparse: {e}, falling back to regex")
    
    # Fallback to regex
    sql_upper = sql_expression.upper()
    
    # Find SELECT ... FROM
    match = re.search(r"SELECT\s+(.+?)\s+FROM", sql_upper, re.DOTALL)
    if not match:
        return []
    
    columns_str = match.group(1).strip()
    
    # If SELECT *, return ["*"]
    if columns_str == "*":
        return ["*"]
    
    # Split by comma and extract column names
    columns = []
    for col in columns_str.split(","):
        col = col.strip()
        # Remove aliases (AS alias)
        col = re.sub(r"\s+AS\s+\w+", "", col, flags=re.IGNORECASE)
        # Remove table prefixes (table.column -> column)
        col = col.split(".")[-1]
        columns.append(col)
    
    return columns

