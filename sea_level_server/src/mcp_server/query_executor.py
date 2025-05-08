"""
Query execution module for ClimateGPT.

This module executes query plans by running SQL against the database
and processing the results.
"""

import time
import logging
from typing import Dict, Any, List

from src.mcp_server.db_access import execute_query
from src.mcp_server.query_utils import clean_sql_query
from src.mcp_server.insight_generator import generate_insights

# Set up logging
logger = logging.getLogger('query_executor')

def execute_plan(steps: List[Dict[str, Any]], original_query: str) -> Dict[str, Any]:
    """
    Execute a query plan consisting of multiple steps.
    
    Args:
        steps: List of execution steps with SQL queries
        original_query: The original user query for context
        
    Returns:
        Dict containing execution results
    """
    results = {}
    final_step = None
    
    try:
        for i, step in enumerate(steps):
            step_start = time.time()
            step_id = step.get("id", f"step{i+1}")
            
            if "sql" not in step:
                logger.error(f"Missing SQL in step {step_id}")
                continue
                
            # Clean the SQL query before executing
            sql_query = clean_sql_query(step["sql"])
            step["sql"] = sql_query  # Update the step with cleaned SQL

            # Log step execution
            logger.info(f"Executing step{i+1}: {step.get('description', 'No description')}")
            logger.info(f"Running SQL: {sql_query[:100]}...")
            
            try:
                df_result = execute_query(sql_query)
                
                # Store the result for this step
                results[step_id] = {
                    "columns": df_result.columns.tolist(),
                    "data": df_result.values.tolist()
                }
                
                # Update the final step
                final_step = step
                logger.info(f"Completed step{i+1}")
                
            except Exception as e:
                logger.error(f"Error executing SQL in step {step_id}: {str(e)}")
                return {"error": f"Database query execution error in step {step_id}: {str(e)}"}
        
        # If we have results and a final step, generate insights
        if final_step and results:
            # Use the result from the final step for insights
            final_step_id = final_step.get("id", list(results.keys())[-1])
            final_result = results[final_step_id]
            
            logger.info("Generating insights from results")
            insights = generate_insights(original_query, final_result, final_step)
            
            return {
                "results": final_result,
                "insights": insights
            }
        else:
            return {"error": "No results were generated from the execution plan"}
            
    except Exception as e:
        logger.error(f"Error in plan execution: {str(e)}")
        return {"error": f"Plan execution error: {str(e)}"}
