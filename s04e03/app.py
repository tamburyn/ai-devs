import requests
import json
from openai import OpenAI
import os
from dotenv import load_dotenv
from typing import Dict, List
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

# Load environment variables
load_dotenv()

def log_step(step: str, message: str):
    """Helper function for consistent logging"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{timestamp}] {step}")
    print("-" * 50)
    print(message)
    print("-" * 50)

class SoftoAnalyzer:
    def __init__(self):
        self.base_url = "https://centrala.ag3nts.org"
        self.api_key = os.getenv("API_KEY", "95e20ae1-e5a4-4a45-9350-f0b71ec099ce")
        self.questions_url = f"{self.base_url}/data/{self.api_key}/softo.json"
        self.report_url = f"{self.base_url}/report"
        self.website_url = "https://softo.ag3nts.org"
        self.openai_client = OpenAI()
        self.visited_urls = set()
        self.content_cache = {}

    def get_all_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract all links from the page"""
        links = []
        # Lista dozwolonych ścieżek
        allowed_paths = ['', '/', '/uslugi', '/portfolio', '/aktualnosci', '/kontakt', '/blog']
        # Lista dozwolonych prefiksów dla dynamicznych stron
        allowed_prefixes = ['/portfolio_', '/blog/']
        
        for a in soup.find_all('a', href=True):
            url = urljoin(base_url, a['href'])
            if not url.startswith(self.website_url):
                continue
            
            # Wyciągnij ścieżkę z URL
            path = url.replace(self.website_url, '')
            
            # Sprawdź czy ścieżka jest dozwolona
            if path in allowed_paths:
                links.append(url)
                continue
            
            # Sprawdź prefiksy dla stron dynamicznych
            if any(path.startswith(prefix) for prefix in allowed_prefixes):
                # Dodatkowe sprawdzenie dla portfolio - tylko numeryczne ID
                if path.startswith('/portfolio_'):
                    if '_' in path and path.split('_')[1].isdigit():
                        links.append(url)
                else:
                    links.append(url)
        
        return list(set(links))  # Usuń duplikaty

    def scrape_page(self, url: str) -> Dict:
        """Scrape single page content with structured data"""
        if url in self.content_cache:
            return self.content_cache[url]
        
        # Ignoruj strony z pułapkami
        if 'loop' in url or 'czescizamienne' in url:
            return {"text": "", "links": [], "images": [], "forms": {}}

        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script, style elements and navigation
            for element in soup(["script", "style"]):
                element.decompose()
            
            # Structured data extraction
            data = {
                "url": url,
                "text": "",
                "links": [],
                "images": [],
                "forms": {},
                "metadata": {}
            }
            
            # Extract main content
            main_content = soup.find('main') or soup.find(class_='content') or soup
            if main_content:
                # Get text content
                data["text"] = main_content.get_text(separator='\n', strip=True)
                
                # Get all links with their text
                for link in main_content.find_all('a', href=True):
                    full_url = urljoin(url, link['href'])
                    data["links"].append({
                        "url": full_url,
                        "text": link.get_text(strip=True)
                    })
                
                # Get all images with their alt text and src
                for img in main_content.find_all('img'):
                    img_url = urljoin(url, img.get('src', ''))
                    data["images"].append({
                        "url": img_url,
                        "alt": img.get('alt', ''),
                        "title": img.get('title', '')
                    })
                
                # Get form data (especially useful for contact forms)
                for form in main_content.find_all('form'):
                    form_data = {
                        "action": form.get('action', ''),
                        "method": form.get('method', ''),
                        "fields": []
                    }
                    for input_field in form.find_all(['input', 'textarea']):
                        form_data["fields"].append({
                            "type": input_field.get('type', 'text'),
                            "name": input_field.get('name', ''),
                            "placeholder": input_field.get('placeholder', '')
                        })
                    data["forms"][form.get('id', 'form')] = form_data
            
            self.content_cache[url] = data
            return data
            
        except Exception as e:
            log_step("Error", f"Failed to scrape {url}: {str(e)}")
            return {"text": "", "links": [], "images": [], "forms": {}}

    def format_content_for_llm(self, pages_data: List[Dict]) -> str:
        """Format scraped data for LLM analysis"""
        formatted_sections = []
        
        for page in pages_data:
            section = f"\n=== Content from {page['url']} ===\n"
            
            # Add main text content
            if page['text']:
                section += f"\nMain Content:\n{page['text']}\n"
            
            # Add relevant links
            if page['links']:
                section += "\nRelevant Links:\n"
                for link in page['links']:
                    if link['text'] and not any(skip in link['url'] for skip in ['loop', 'czescizamienne']):
                        section += f"- {link['text']}: {link['url']}\n"
            
            # Add form information (especially useful for contact forms)
            if page['forms']:
                section += "\nForms:\n"
                for form_id, form_data in page['forms'].items():
                    section += f"Form ({form_id}):\n"
                    for field in form_data['fields']:
                        section += f"- {field['name']} ({field['type']}): {field['placeholder']}\n"
            
            formatted_sections.append(section)
        
        return "\n\n".join(formatted_sections)

    def get_website_content(self) -> str:
        """Fetch and parse all website content"""
        log_step("Starting Website Crawl", f"Base URL: {self.website_url}")
        
        all_content = []
        urls_to_visit = [self.website_url]
        
        while urls_to_visit and len(self.visited_urls) < 20:  # Limit liczby stron
            url = urls_to_visit.pop(0)
            if url in self.visited_urls:
                continue
                
            self.visited_urls.add(url)
            
            try:
                response = requests.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Get content
                content = self.scrape_page(url)
                if content:
                    all_content.append(f"\n=== Content from {url} ===\n{content}")
                
                # Find new links
                new_links = self.get_all_links(soup, url)
                urls_to_visit.extend([u for u in new_links if u not in self.visited_urls])
                
                # Be nice to the server
                time.sleep(1)
                
            except Exception as e:
                log_step("Error", f"Failed to process {url}: {str(e)}")
        
        full_content = "\n\n".join(all_content)
        
        log_step("Website Crawl Completed", f"""
Total pages scraped: {len(self.visited_urls)}
Total content length: {len(full_content)} characters
Visited URLs:
{json.dumps(list(self.visited_urls), indent=2)}
""")
        
        return full_content

    def get_questions(self) -> Dict:
        """Fetch questions from the API"""
        log_step("Fetching Questions", f"Sending GET request to {self.questions_url}")
        
        try:
            response = requests.get(self.questions_url)
            response.raise_for_status()
            questions = response.json()
            
            log_step("Questions Received", f"""
Status Code: {response.status_code}
Questions:
{json.dumps(questions, indent=2)}
""")
            return questions
            
        except Exception as e:
            log_step("Error", f"Failed to fetch questions: {str(e)}")
            return {}

    def analyze_with_llm(self, content: str, questions: Dict) -> Dict:
        """Analyze website content and generate answers using LLM"""
        system_prompt = """You are a precise data analyzer specialized in extracting information from websites.
Your task is to analyze the provided website content and answer specific questions about the Softo company.

CRITICAL RESPONSE FORMAT RULES:
1. For questions asking about email - look in contact forms and content for email addresses
2. For questions asking about URL/link - look in the 'Relevant Links' sections and ensure URLs are complete
3. For other questions - analyze the main content sections

Guidelines for specific answer types:
- Email: Must be a valid email address format
- URL: Must start with https:// and be a complete, valid URL
- Text: Should be concise and factual

Respond with a JSON object containing exactly three fields: 01, 02, and 03.
Each answer must match the exact format required by its question type."""

        user_prompt = f"""Analyze this website content and answer the questions about Softo company.
Pay special attention to:
- Contact forms and their fields for email addresses
- Link sections for URLs and web interfaces
- Main content for company information

Questions to answer:
{json.dumps(questions, indent=2)}

Website content (structured by sections):
{content}

Return a JSON object with your answers. Make sure:
1. Each answer is in the exact format required (email/URL/text)
2. URLs are complete and start with https://
3. Emails are properly formatted
4. Text answers are concise and specific"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            
            answers = json.loads(response.choices[0].message.content)
            
            # Validate answers format
            for key, value in answers.items():
                if key == "02":
                    # Ensure URL is complete and valid
                    if not value.startswith("https://"):
                        value = f"https://{value}"
                    if not any(value in link['url'] for page in self.content_cache.values() 
                              for link in page.get('links', [])):
                        log_step("Warning", f"URL not found in scraped content: {value}")
                elif key == "01":
                    # Validate email format
                    if not isinstance(value, str) or '@' not in value:
                        log_step("Warning", f"Invalid email format: {value}")
            
            return answers
            
        except Exception as e:
            log_step("Error", f"LLM Analysis failed: {str(e)}")
            return {}

    def save_debug_files(self, content: str, questions: Dict, answers: Dict):
        """Save debug files in the current directory"""
        debug_dir = os.path.join(os.path.dirname(__file__), 'debug')
        os.makedirs(debug_dir, exist_ok=True)
        
        # Save scraped content
        with open(os.path.join(debug_dir, "softo_content.txt"), "w", encoding="utf-8") as f:
            f.write(content)
        
        # Save questions
        with open(os.path.join(debug_dir, "questions.json"), "w", encoding="utf-8") as f:
            json.dump(questions, f, indent=2)
        
        # Save answers
        with open(os.path.join(debug_dir, "answers.json"), "w", encoding="utf-8") as f:
            json.dump(answers, f, indent=2)
        
        log_step("Debug Files Saved", f"""
Files saved in: {debug_dir}
- softo_content.txt
- questions.json
- answers.json
""")

    def send_report(self, answers: Dict) -> Dict:
        """Send report to the central API"""
        payload = {
            "task": "softo",
            "apikey": self.api_key,
            "answer": answers
        }

        log_step("Sending Report", f"""
Sending POST request to {self.report_url}
Payload:
{json.dumps(payload, indent=2)}
""")

        try:
            response = requests.post(
                self.report_url,
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
            log_step("Report Response", f"""
Status Code: {response.status_code}
Response:
{json.dumps(result, indent=2)}
""")
            return result
            
        except Exception as e:
            log_step("Error", f"""
Failed to send report:
Error type: {type(e).__name__}
Error message: {str(e)}
Response status code: {getattr(e.response, 'status_code', 'N/A')}
Response text: {getattr(e.response, 'text', 'N/A')}
""")
            return {}

    def analyze(self):
        """Main analysis method"""
        log_step("Analysis Started", "Beginning the analysis process...")
        
        # Get questions first
        questions = self.get_questions()
        if not questions:
            log_step("Error", "No questions received, stopping analysis")
            return {}
        
        # Get website content
        content = self.get_website_content()
        if not content:
            log_step("Error", "No website content received, stopping analysis")
            return {}
        
        # Analyze with questions
        answers = self.analyze_with_llm(content, questions)
        if not answers:
            log_step("Error", "No answers generated, stopping analysis")
            return {}
        
        # Save debug files
        self.save_debug_files(content, questions, answers)
        
        # Send report
        result = self.send_report(answers)
        
        log_step("Analysis Completed", f"""
Final Results:
Pages Scraped: {len(self.visited_urls)}
Total Content Length: {len(content)}
Questions: {len(questions)}
Answers: {len(answers)}
Report Status: {'Success' if result else 'Failed'}
""")
        
        return answers

def main():
    try:
        analyzer = SoftoAnalyzer()
        analyzer.analyze()
    except Exception as e:
        log_step("Fatal Error", f"Application crashed: {str(e)}")

if __name__ == "__main__":
    main() 