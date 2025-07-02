from dataclasses import dataclass
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
import time
import random
import json
from urllib.parse import quote
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
import pandas as pd
import dateparser
from datetime import datetime

@dataclass
class JobData:
    """Data structure for storing job information."""
    title: str
    company: str
    location: str
    job_link: str
    posted_date: str
    job_id: str
    short_url: str

class ScraperConfig:
    """Configuration for LinkedIn job scraping."""
    BASE_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    JOBS_PER_PAGE = 25
    MIN_DELAY = 2
    MAX_DELAY = 5
    RATE_LIMIT_DELAY = 30
    RATE_LIMIT_THRESHOLD = 10
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "DNT": "1",
        "Cache-Control": "no-cache",
    }

class LinkedInJobsScraper:
    """Scraper for LinkedIn job postings."""
    def __init__(self):
        self.session = self._setup_session()

    def _setup_session(self) -> requests.Session:
        """Set up a requests session with retry logic."""
        session = requests.Session()
        retries = Retry(
            total=5, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504]
        )
        session.mount("https://", HTTPAdapter(max_retries=retries))
        return session

    def _build_search_url(self, keywords: str, location: str, start: int = 0) -> str:
        """Build the LinkedIn job search URL."""
        params = {
            "keywords": keywords,
            "location": location,
            "start": start,
        }
        return f"{ScraperConfig.BASE_URL}?{'&'.join(f'{k}={quote(str(v))}' for k, v in params.items())}"

    def _clean_job_url(self, url: str) -> str:
        """Remove query parameters from job URL."""
        return url.split("?")[0] if "?" in url else url

    def _extract_job_data(self, job_card: BeautifulSoup) -> Optional[JobData]:
        """Extract job data from a job card element."""
        try:
            title = job_card.find("h3", class_="base-search-card__title").text.strip()
            company = job_card.find(
                "h4", class_="base-search-card__subtitle"
            ).text.strip()
            location = job_card.find(
                "span", class_="job-search-card__location"
            ).text.strip()
            job_link = self._clean_job_url(
                job_card.find("a", class_="base-card__full-link")['href']
            )
            posted_date = job_card.find("time", class_="job-search-card__listdate")
            posted_date = dateparser.parse(posted_date.text.strip()).strftime('%Y-%m-%d') if posted_date else None
            job_id = job_link.split("-")[-1]
            short_url = f"https://www.linkedin.com/jobs/view/{job_id}"
            return JobData(
                title=title,
                company=company,
                location=location,
                job_link=job_link,
                posted_date=posted_date,
                job_id=job_id,
                short_url=short_url
            )
        except Exception as e:
            print(f"Failed to extract job data: {str(e)}")
            return None

    def _fetch_job_page(self, url: str) -> BeautifulSoup:
        """Fetch a LinkedIn job search result page."""
        try:
            response = self.session.get(url, headers=ScraperConfig.HEADERS)
            if response.status_code != 200:
                raise RuntimeError(
                    f"Failed to fetch data: Status code {response.status_code}"
                )
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException as e:
            raise RuntimeError(f"Request failed: {str(e)}")

    def scrape_jobs(self, keywords: str, location: str, max_jobs: int = 100) -> List[JobData]:
        """Scrape job postings from LinkedIn based on keywords and location."""
        all_jobs = []
        start = 0
        while len(all_jobs) < max_jobs:
            try:
                url = self._build_search_url(keywords, location, start)
                soup = self._fetch_job_page(url)
                job_cards = soup.find_all("div", class_="base-card")
                if not job_cards:
                    break
                for card in job_cards:
                    job_data = self._extract_job_data(card)
                    if job_data:
                        all_jobs.append(job_data)
                        if len(all_jobs) >= max_jobs:
                            break
                print(f"Scraped {len(all_jobs)} jobs...")
                start += ScraperConfig.JOBS_PER_PAGE
                time.sleep(random.uniform(ScraperConfig.MIN_DELAY, ScraperConfig.MAX_DELAY))
            except Exception as e:
                print(f"Scraping error: {str(e)}")
                break
        return all_jobs[:max_jobs]

    def save_results(self, jobs: List[JobData], filename: str = "data/linkedin_new_jobs.json") -> None:
        """Save scraped jobs to a JSON file."""
        if not jobs:
            return
        with open(filename, "w", encoding="utf-8") as f:
            json.dump([vars(job) for job in jobs], f, indent=2, ensure_ascii=False)
        print(f"Saved {len(jobs)} jobs to {filename}")

class GoogleSheetsConnector:
    """Connector for interacting with Google Sheets."""
    def __init__(self):
        load_dotenv()
        credentials_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
        credentials_dict = json.loads(credentials_json)
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
        gc = gspread.authorize(credentials)
        spreadsheet_url = os.getenv('GSHEETS_TARGET')
        self.spreadsheet = gc.open_by_url(spreadsheet_url)

    def add_new_jobs(self, jobs: List[JobData]):
        """Add new jobs to the 'NewJobs' sheet, avoiding duplicates and jobs already in Links or BlackList."""
        worksheet = self.spreadsheet.worksheet("NewJobs")
        links_ws = self.spreadsheet.worksheet("Links")
        blacklist_ws = self.spreadsheet.worksheet("BlackList")
        existing_ids = set()
        existing_rows = worksheet.get_all_values()
        if existing_rows:
            for row in existing_rows[1:]:
                if len(row) >= 6:
                    existing_ids.add(row[5])
        # Links from Links sheet
        links_rows = links_ws.get_all_values()
        sent_links = set()
        if links_rows:
            for row in links_rows[1:]:
                if row and row[0]:
                    sent_links.add(row[0].strip())
        # Links from BlackList sheet
        blacklist_rows = blacklist_ws.get_all_values()
        blacklist_links = set()
        if blacklist_rows:
            for row in blacklist_rows[1:]:
                if row and row[0]:
                    blacklist_links.add(row[0].strip())
        all_excluded_links = sent_links.union(blacklist_links)
        new_jobs = [
            [
                job.title,
                job.company,
                job.location,
                job.job_link,
                job.posted_date,
                job.job_id,
                job.short_url
            ]
            for job in jobs
            if job.job_id not in existing_ids and job.job_link not in all_excluded_links and job.short_url not in all_excluded_links
        ]
        if new_jobs:
            worksheet.append_rows(new_jobs, value_input_option="USER_ENTERED")
            print(f"Se añadieron {len(new_jobs)} trabajos nuevos a Google Sheets.")
        else:
            print("No hay trabajos nuevos para añadir.")

    def scrape_job_details(self, url_list: List[JobData]):
        """Scrape job details for jobs in the provided list and append to the 'Control' sheet, avoiding duplicates by ID."""
        worksheet_control = self.spreadsheet.worksheet("Control")
        existing_rows = worksheet_control.get_all_values()
        existing_ids = set()
        if existing_rows:
            for row in existing_rows[1:]:
                if row and row[0]:
                    existing_ids.add(row[0])
        jobs_to_scrape = [job for job in url_list if job.job_id not in existing_ids]
        results = []
        for job in jobs_to_scrape:
            url = job.short_url
            try:
                response = requests.get(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
                })
                soup = BeautifulSoup(response.text, 'html.parser')
                title = soup.title.string if soup.title else None
                company_a = soup.find('a', class_=lambda x: x and 'topcard__org-name-link' in x)
                company = company_a.text.strip() if company_a else None
                date_posted_span = soup.find('span', class_='posted-time-ago__text topcard__flavor--metadata')
                date_posted_text = date_posted_span.text.strip() if date_posted_span else None
                date_posted = dateparser.parse(date_posted_text).strftime('%Y-%m-%d') if date_posted_text else None
                date_applied = datetime.today().strftime('%Y-%m-%d')
                role_h1 = soup.find('h1', class_=lambda x: x and 'topcard__title' in x)
                role = role_h1.text.strip() if role_h1 else None
                location_span = soup.find('span', class_=lambda x: x and 'main-job-card__location' in x)
                location = location_span.text.strip() if location_span else None
                job_id = job.job_id
                # Campos manuales o no disponibles
                industry = ''
                connections = ''
                cover_letter = ''
                resume_upload = ''
                resume_form = ''
                salary_range = ''
                notes = ''
                status = ''
                latest_word = ''
                contact_1 = ''
                shade = ''
                results.append({
                    'ID': job_id,
                    'Position': role,
                    'Company': company,
                    'Industry': industry,
                    'Role': role,
                    'Location': location,
                    'Date Posted': date_posted,
                    'Date Applied': date_applied,
                    'Connections?': connections,
                    'Cover Letter': cover_letter,
                    'Résumé upload?': resume_upload,
                    'Résumé Form?': resume_form,
                    'Salary Range': salary_range,
                    'Notes': notes,
                    'Status': status,
                    'Latest word': latest_word,
                    'contact 1': contact_1,
                    'SHADE': shade
                })
            except Exception as e:
                job_id = job.job_id
                results.append({'ID': job_id, 'Position': '', 'Company': '', 'Industry': '', 'Role': '', 'Location': '', 'Date Posted': '', 'Date Applied': '', 'Connections?': '', 'Cover Letter': '', 'Résumé upload?': '', 'Résumé Form?': '', 'Salary Range': '', 'Notes': '', 'Status': '', 'Latest word': '', 'contact 1': '', 'SHADE': '', 'error': str(e)})
        scraped_df = pd.DataFrame(results)
        data_to_append = scraped_df.values.tolist()
        if data_to_append:
            worksheet_control.append_rows(data_to_append)
            print(f"Se agregaron {len(data_to_append)} filas a la hoja Control")
        else:
            print("No hay datos nuevos para agregar")

    def get_links_jobs(self) -> List[JobData]:
        """Get jobs from the 'Links' sheet as JobData objects (minimal fields)."""
        links_ws = self.spreadsheet.worksheet("Links")
        links_rows = links_ws.get_all_values()
        jobs = []
        for row in links_rows[1:]:
            if row and row[0]:
                job_id = row[0].rstrip('/').split("/")[-1]
                jobs.append(JobData(
                    title="",
                    company="",
                    location="",
                    job_link=row[0],
                    posted_date="",
                    job_id=job_id,
                    short_url=row[0]
                ))
        return jobs

    def clean_new_jobs(self):
        """Remove from 'NewJobs' all jobs whose short_url is present in 'Links' or 'BlackList'."""
        worksheet = self.spreadsheet.worksheet("NewJobs")
        links_ws = self.spreadsheet.worksheet("Links")
        blacklist_ws = self.spreadsheet.worksheet("BlackList")
        all_rows = worksheet.get_all_values()
        header = all_rows[0] if all_rows else []
        data_rows = all_rows[1:] if all_rows else []
        # Links from Links sheet
        links_rows = links_ws.get_all_values()
        sent_links = set()
        if links_rows:
            for row in links_rows[1:]:
                if row and row[0]:
                    sent_links.add(row[0].strip())
        # Links from BlackList sheet
        blacklist_rows = blacklist_ws.get_all_values()
        blacklist_links = set()
        if blacklist_rows:
            for row in blacklist_rows[1:]:
                if row and row[0]:
                    blacklist_links.add(row[0].strip())
        all_excluded_links = sent_links.union(blacklist_links)
        filtered_rows = [row for row in data_rows if len(row) < 7 or row[6] not in all_excluded_links]
        worksheet.clear()
        if header:
            worksheet.append_row(header)
        if filtered_rows:
            worksheet.append_rows(filtered_rows)
        print(f"Se eliminaron {len(data_rows) - len(filtered_rows)} filas de NewJobs que ya estaban en Links o BlackList.")

def main():
    """Main execution: scrape jobs, save results, update Google Sheets, and clean new jobs."""
    params = {"keywords": "Data Scientist Remote", "location": "Mexico", "max_jobs": 100}
    scraper = LinkedInJobsScraper()
    jobs = scraper.scrape_jobs(**params)
    scraper.save_results(jobs)
    gsheets = GoogleSheetsConnector()
    gsheets.add_new_jobs(jobs)
    links_jobs = gsheets.get_links_jobs()
    gsheets.scrape_job_details(links_jobs)
    gsheets.clean_new_jobs()

if __name__ == "__main__":
    main()