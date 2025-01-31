import json
import requests
import os
from openai import OpenAI
from typing import List, Dict
import logging
import re

class DatabaseAnalyzer:
    def __init__(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize API clients
        self.api_url = "https://centrala.ag3nts.org/apidb"
        self.api_key = "95e20ae1-e5a4-4a45-9350-f0b71ec099ce"
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    def get_table_structure(self) -> str:
        """Get the structure of all relevant tables."""
        self.logger.info("Getting table structure...")
        tables_info = []
        
        # Get structure for each table
        tables = ['users', 'datacenters', 'connections']
        for table in tables:
            structure = self.execute_query(f"DESC {table}")
            sample = self.execute_query(f"SELECT * FROM {table} LIMIT 1")
            
            if 'reply' in structure:
                tables_info.append(f"Table: {table}\nStructure: {json.dumps(structure['reply'], indent=2)}")
                tables_info.append(f"Sample data: {json.dumps(sample['reply'], indent=2)}")
        
        return "\n\n".join(tables_info)

    def get_query_from_llm(self, table_structure: str) -> str:
        """Use OpenAI to generate the SQL query."""
        self.logger.info("Generating SQL query using LLM...")
        prompt = f"""Given these table structures:

{table_structure}

Task: Generate a SQL query to find active datacenter IDs (dc_id) that are managed by inactive employees.
Requirements:
- Find datacenters where is_active = 1
- Manager (from users table) has is_active = 0
- Return only dc_id column
- Use simple SELECT and WHERE conditions
- The query must work with the actual database schema

Return only the SQL query, nothing else."""

        response = self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a SQL expert. Provide only the SQL query without any explanation or formatting."},
                {"role": "user", "content": prompt}
            ]
        )
        
        query = response.choices[0].message.content.strip()
        query = query.replace('```sql', '').replace('```', '').strip()
        self.logger.info(f"Generated query: {query}")
        return query

    def check_for_flag(self, response_data: Dict) -> None:
        """Check for hidden flag in response data."""
        response_str = json.dumps(response_data)
        if "FLG:" in response_str:
            self.logger.info("!!! FOUND FLAG !!!")
            # Szukamy wzorca {{FLG:xxx}} lub FLG:xxx
            flag_matches = re.findall(r'(?:\{\{)?FLG:[\w_-]+(?:\}\})?', response_str)
            if flag_matches:
                self.logger.info(f"Found flags: {flag_matches}")

    def execute_query(self, query: str) -> Dict:
        """Execute a query against the database API."""
        self.logger.info(f"Executing query: {query}")
        payload = {
            "task": "database",
            "apikey": self.api_key,
            "query": query
        }
        response = requests.post(self.api_url, json=payload)
        result = response.json()
        self.check_for_flag(result)  # Sprawdzamy flagę w odpowiedzi
        self.logger.info(f"Query result: {result}")
        return result

    def submit_answer(self, datacenter_ids: List[int]) -> Dict:
        """Submit the answer to the central system."""
        self.logger.info(f"Raw datacenter IDs: {datacenter_ids}")
        
        # Konwertujemy wszystkie ID na liczby całkowite
        answer_array = [int(id) for id in datacenter_ids]
        
        # Tworzymy payload
        payload = {
            "task": "database",
            "apikey": self.api_key,
            "answer": answer_array
        }
        
        # Formatujemy JSON bez spacji
        json_payload = json.dumps(payload, separators=(',', ':'))
        self.logger.info(f"Compact JSON payload: {json_payload}")
        
        # Wysyłamy na właściwy adres raportu
        report_url = "https://centrala.ag3nts.org/report"
        
        response = requests.post(
            report_url,
            data=json_payload,
            headers={'Content-Type': 'application/json'}
        )
        
        result = response.json()
        self.check_for_flag(result)  # Sprawdzamy flagę w odpowiedzi
        self.logger.info(f"Response: {response.text}")
        return result

    def search_for_hidden_flag(self) -> None:
        """Search all tables for hidden flag."""
        self.logger.info("Searching for hidden flag in database...")
        
        # Lista zapytań do przeszukania różnych tabel i kolumn
        search_queries = [
            "SELECT * FROM users WHERE username LIKE '%FLG%' OR lastlog LIKE '%FLG%'",
            "SELECT * FROM datacenters WHERE location LIKE '%FLG%'",
            "SELECT * FROM connections WHERE notes LIKE '%FLG%' OR details LIKE '%FLG%'",
            # Pobierz wszystkie dane z każdej tabeli
            "SELECT * FROM users",
            "SELECT * FROM datacenters",
            "SELECT * FROM connections"
        ]
        
        for query in search_queries:
            self.logger.info(f"Executing search query: {query}")
            result = self.execute_query(query)
            if 'reply' in result:
                # Konwertujemy całą odpowiedź na string i szukamy flagi
                result_str = json.dumps(result['reply'])
                if 'FLG:' in result_str:
                    self.logger.info(f"!!! FOUND FLAG IN QUERY {query} !!!")
                    self.logger.info(f"Result containing flag: {result_str}")

    def solve(self) -> None:
        """Main solving method."""
        try:
            self.logger.info("Starting the analysis...")
            
            # Najpierw szukamy ukrytej flagi
            self.search_for_hidden_flag()
            
            # Get table structures
            table_structure = self.get_table_structure()
            
            # Get SQL query from LLM
            sql_query = self.get_query_from_llm(table_structure)
            
            # Execute the query
            result = self.execute_query(sql_query)
            
            # Extract datacenter IDs
            datacenter_ids = []
            if 'reply' in result and result['reply']:
                for row in result['reply']:
                    if isinstance(row, dict) and 'dc_id' in row:
                        datacenter_ids.append(int(row['dc_id']))
            
            self.logger.info(f"Found datacenter IDs: {datacenter_ids}")
            
            if not datacenter_ids:
                self.logger.warning("No datacenter IDs found!")
                return
            
            # Submit the answer
            response = self.submit_answer(datacenter_ids)
            self.logger.info(f"Submission response: {response}")
            
        except Exception as e:
            self.logger.error(f"An error occurred: {str(e)}", exc_info=True)

def main():
    analyzer = DatabaseAnalyzer()
    analyzer.solve()

if __name__ == "__main__":
    main() 