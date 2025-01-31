import requests
import json
import logging
from typing import List, Dict
from datetime import datetime
from neo4j import GraphDatabase
import mysql.connector
from collections import defaultdict
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class PathFinderAI:
    def __init__(self):
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'path_finder_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # API configuration
        self.api_key = "95e20ae1-e5a4-4a45-9350-f0b71ec099ce"
        self.base_url = "https://centrala.ag3nts.org"
        self.report_url = f"{self.base_url}/report"
        
        # Neo4j configuration - hardcoded credentials
        self.neo4j_uri = "neo4j://localhost:7687"
        self.neo4j_user = "neo4j"
        self.neo4j_password = "Password3"
        
        # Initialize Neo4j driver
        self.driver = GraphDatabase.driver(
            self.neo4j_uri,
            auth=(self.neo4j_user, self.neo4j_password)
        )
        
        # Test connection
        try:
            with self.driver.session() as session:
                result = session.run("RETURN 1 as test")
                self.logger.info("Successfully connected to Neo4j")
        except Exception as e:
            self.logger.error(f"Failed to connect to Neo4j: {str(e)}")
            raise
        
        # MySQL configuration
        self.mysql_config = {
            'host': 'localhost',
            'user': 'your_username',  # Change this
            'password': 'your_password',  # Change this
            'database': 'your_database'  # Change this
        }

    def get_mysql_data(self) -> tuple[Dict[int, str], List[tuple[int, int]]]:
        """Fetch data from API and return users and connections."""
        try:
            # Get users - this will give us ID and name mapping
            users_query = "SELECT id, username FROM users"
            users_result = self.execute_query(users_query)
            users = {
                int(row['id']): row['username'].upper() 
                for row in users_result.get('reply', [])
            }
            self.logger.info(f"Retrieved {len(users)} users")
            
            # Get connections - this gives us who knows whom
            connections_query = "SELECT user1_id, user2_id FROM connections"
            connections_result = self.execute_query(connections_query)
            connections = [
                (int(row['user1_id']), int(row['user2_id'])) 
                for row in connections_result.get('reply', [])
            ]
            self.logger.info(f"Retrieved {len(connections)} connections")
            
            # Save data to files for reference
            with open('users.json', 'w') as f:
                json.dump(users, f, indent=2)
            with open('connections.json', 'w') as f:
                json.dump(connections, f, indent=2)
            
            return users, connections
            
        except Exception as e:
            self.logger.error(f"Error fetching data: {e}")
            return {}, []

    def execute_query(self, query: str) -> Dict:
        """Execute a query against the database API."""
        try:
            payload = {
                "task": "database",
                "apikey": self.api_key,
                "query": query
            }
            
            self.logger.info(f"Sending query to API: {query}")
            
            response = requests.post(
                "https://centrala.ag3nts.org/apidb",
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            
            response.raise_for_status()  # Raise an exception for bad status codes
            result = response.json()
            
            self.logger.info(f"API response status: {response.status_code}")
            return result
            
        except Exception as e:
            self.logger.error(f"API query failed: {e}")
            return {"reply": []}

    def setup_neo4j_database(self, users: Dict[int, str], connections: List[tuple[int, int]]):
        """Setup Neo4j database with users and their connections."""
        try:
            self.logger.info("Attempting to connect to Neo4j...")
            
            # Use the default 'neo4j' database
            with self.driver.session(database="neo4j") as session:
                # Test connection
                self.logger.info("Testing connection...")
                result = session.run("RETURN 1 as test")
                self.logger.info(f"Connection test result: {result.single()}")
                
                # Clear existing data
                self.logger.info("Clearing existing data from Neo4j...")
                session.run("MATCH (n) DETACH DELETE n")
                
                # Create users
                self.logger.info(f"Creating {len(users)} users in Neo4j...")
                for user_id, name in users.items():
                    session.run(
                        "CREATE (p:Person {id: $id, name: $name})",
                        id=user_id, name=name
                    )
                
                # Create relationships
                self.logger.info(f"Creating {len(connections)} connections in Neo4j...")
                for source_id, target_id in connections:
                    session.run("""
                        MATCH (a:Person {id: $source_id})
                        MATCH (b:Person {id: $target_id})
                        CREATE (a)-[:KNOWS]->(b)
                    """, source_id=source_id, target_id=target_id)
                    
            self.logger.info("Successfully set up Neo4j database")
                    
        except Exception as e:
            self.logger.error(f"Error setting up Neo4j database: {str(e)}")
            self.logger.error(f"Error type: {type(e)}")
            if hasattr(e, 'message'):
                self.logger.error(f"Error message: {e.message}")
            raise

    def find_shortest_path(self) -> str:
        """Find shortest path from Rafał to Barbara using Neo4j."""
        try:
            with self.driver.session() as session:
                # 1. Check RAFAŁ's network (both who he knows and who knows him)
                rafal_network = session.run("""
                    MATCH (p:Person {name: 'RAFAŁ'})
                    OPTIONAL MATCH (p)-[:KNOWS]->(outgoing:Person)
                    OPTIONAL MATCH (incoming:Person)-[:KNOWS]->(p)
                    RETURN 
                        collect(DISTINCT outgoing.name) as knows_directly,
                        collect(DISTINCT incoming.name) as known_by
                """).single()
                self.logger.info(f"RAFAŁ knows: {rafal_network['knows_directly']}")
                self.logger.info(f"RAFAŁ is known by: {rafal_network['known_by']}")
                
                # 2. Check BARBARA's network
                barbara_network = session.run("""
                    MATCH (p:Person {name: 'BARBARA'})
                    OPTIONAL MATCH (p)-[:KNOWS]->(outgoing:Person)
                    OPTIONAL MATCH (incoming:Person)-[:KNOWS]->(p)
                    RETURN 
                        collect(DISTINCT outgoing.name) as knows_directly,
                        collect(DISTINCT incoming.name) as known_by
                """).single()
                self.logger.info(f"BARBARA knows: {barbara_network['knows_directly']}")
                self.logger.info(f"BARBARA is known by: {barbara_network['known_by']}")
                
                # 3. Look for paths through common connections (up to 2 hops)
                common_connections = session.run("""
                    MATCH (rafal:Person {name: 'RAFAŁ'})
                    MATCH (barbara:Person {name: 'BARBARA'})
                    MATCH path = (rafal)-[:KNOWS*1..2]-(intermediate:Person)-[:KNOWS*1..2]-(barbara)
                    RETURN 
                        intermediate.name as connection,
                        [node in nodes(path) | node.name] as full_path
                    LIMIT 5
                """)
                for record in common_connections:
                    self.logger.info(f"Possible connection through: {record['connection']}")
                    self.logger.info(f"Path: {' -> '.join(record['full_path'])}")
                
                # 4. Try to find any path up to 5 hops
                result = session.run("""
                    MATCH path = shortestPath(
                        (start:Person {name: 'RAFAŁ'})-[:KNOWS*1..5]-(end:Person {name: 'BARBARA'})
                    )
                    RETURN [node in nodes(path) | node.name] as path_names,
                           length(path) as path_length
                """)
                
                path_record = result.single()
                if path_record and path_record["path_names"]:
                    path = path_record["path_names"]
                    length = path_record["path_length"]
                    self.logger.info(f"Found path of length {length}: {' -> '.join(path)}")
                    return ", ".join(path)
                
                self.logger.error("No path found between RAFAŁ and BARBARA")
                return ""
                
        except Exception as e:
            self.logger.error(f"Error finding shortest path: {e}")
            return ""

    def submit_answer(self, path: str) -> dict:
        """Submit the found path to the central system."""
        payload = {
            "task": "connections",
            "apikey": self.api_key,
            "answer": path
        }
        
        try:
            response = requests.post(
                self.report_url,
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Error submitting answer: {e}")
            return {}

    def solve(self):
        """Main solving method."""
        try:
            # Get data from MySQL
            users, connections = self.get_mysql_data()
            if not users or not connections:
                self.logger.error("Failed to get data from MySQL")
                return
            
            # Debug the data before creating the graph
            self.logger.info("Users data sample:")
            sample_users = dict(list(users.items())[:5])
            self.logger.info(f"Sample users: {sample_users}")
            self.logger.info("Connections sample:")
            sample_connections = connections[:5]
            self.logger.info(f"Sample connections: {sample_connections}")
            
            # Setup Neo4j database
            self.setup_neo4j_database(users, connections)
            
            # Verify the graph structure
            self.verify_graph()
            
            # Find shortest path
            path = self.find_shortest_path()
            if not path:
                self.logger.error("Failed to find path between Rafał and Barbara")
                return
            
            # Submit answer
            response = self.submit_answer(path)
            self.logger.info(f"Submit response: {response}")
            
        except Exception as e:
            self.logger.error(f"An error occurred: {str(e)}", exc_info=True)

    def verify_graph(self):
        """Debug the graph structure, especially RAFAŁ."""
        try:
            with self.driver.session() as session:
                # 1. Find RAFAŁ in our users data
                rafal_check = session.run("""
                    MATCH (p:Person)
                    WHERE p.name = 'RAFAŁ'
                    RETURN p.name, p.id
                """).data()
                self.logger.info(f"Found RAFAŁ nodes: {rafal_check}")
                
                # 2. Check all connections for RAFAŁ's ID
                if rafal_check:
                    rafal_id = rafal_check[0]['p.id']
                    connections = session.run("""
                        MATCH (p:Person {id: $id})-[r:KNOWS]->(other:Person)
                        RETURN other.name, other.id
                    """, id=rafal_id).data()
                    self.logger.info(f"Connections for RAFAŁ (ID: {rafal_id}): {connections}")
                
                # 3. Show some sample nodes and connections
                sample = session.run("""
                    MATCH (p:Person)
                    WITH p LIMIT 5
                    RETURN p.name, p.id
                """).data()
                self.logger.info(f"Sample nodes: {sample}")
                
                # 4. Show some sample connections
                sample_connections = session.run("""
                    MATCH (p1:Person)-[r:KNOWS]->(p2:Person)
                    WITH p1, p2 LIMIT 5
                    RETURN p1.name + ' knows ' + p2.name as connection
                """).data()
                self.logger.info(f"Sample connections: {sample_connections}")
                
        except Exception as e:
            self.logger.error(f"Error verifying graph: {e}")

def main():
    finder = PathFinderAI()
    finder.solve()

if __name__ == "__main__":
    main() 