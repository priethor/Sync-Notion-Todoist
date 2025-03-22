import requests
import json
import os
import sys
import subprocess
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
NOTION_API_TOKEN = os.getenv('NOTION_API_TOKEN')
NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID')
TODOIST_API_TOKEN = os.getenv('TODOIST_API_TOKEN')

notion_headers = {
    'Authorization': f'Bearer {NOTION_API_TOKEN}',
    'Content-Type': 'application/json',
    'Notion-Version': '2022-06-28'
}

todoist_headers = {
    'Authorization': f'Bearer {TODOIST_API_TOKEN}',
    'Content-Type': 'application/json'
}

# Constants
TASKS_FILE = 'tasks.json'
LAST_SYNCED_FILE = 'last_synced_time.json'

# Function to clear the console
def cls():
    os.system('cls' if os.name == 'nt' else 'clear')

# Function to get tasks from Notion
def get_notion_tasks():
    url = f'https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query'
    response = requests.post(url, headers=notion_headers)
    if response.status_code == 401:
        print("Error: Invalid Notion API token. Please check your NOTION_API_TOKEN environment variable.")
        sys.exit(1)
    if response.status_code == 400:
        print("Error: Invalid Notion Database ID. Please check your NOTION_DATABASE_ID environment variable.")
        sys.exit(2)
    
    response.raise_for_status()
    return response.json().get('results')

# Function to get tasks from Todoist
def get_todoist_tasks():
    url = 'https://api.todoist.com/rest/v2/tasks'
    response = requests.get(url, headers=todoist_headers)
    if response.status_code == 401:
        print("Error: Invalid Todoist API token. Please check your TODOIST_API_TOKEN environment variable.")
        sys.exit(3)
    response.raise_for_status()
    return response.json()

# Function to get completed tasks from Todoist
def get_completed_todoist_tasks():
    url = 'https://api.todoist.com/sync/v9/completed/get_all'
    response = requests.get(url, headers=todoist_headers)
    if response.status_code == 401:
        print("Error: Invalid Todoist API token. Please check your TODOIST_API_TOKEN environment variable.")
        sys.exit(3)
    response.raise_for_status()
    return response.json().get('items', [])

# Function to get last synced time from JSON file
def get_last_synced_time():
    try:
        with open(LAST_SYNCED_FILE, 'r') as file:
            return json.load(file)['last_synced_time']
    except (FileNotFoundError, KeyError):
        return None

# Function to save last synced time to JSON file
def save_last_synced_time():
    data = {'last_synced_time': datetime.now(timezone.utc).isoformat()}
    with open(LAST_SYNCED_FILE, 'w') as file:
        json.dump(data, file)

# Function to save tasks to the JSON file and trigger sync if needed
def save_tasks_to_json(tasks, source="", skip_sync=False):
    try:
        with open(TASKS_FILE, 'r', encoding='utf-8') as file:
            existing_tasks = json.load(file)
    except FileNotFoundError:
        existing_tasks = []

    # Only save if there are actual changes
    if tasks != existing_tasks:
        with open(TASKS_FILE, 'w', encoding='utf-8') as file:
            json.dump(tasks, file, ensure_ascii=False, indent=2, default=str)
        if source:
            print(f"Update from {source}, tasks saved to {TASKS_FILE}.")
            
        # Check if called from main.py (in which case we should skip sync)
        called_from_main = False
        import inspect
        call_stack = inspect.stack()
        for frame in call_stack:
            if frame.filename.endswith('main.py'):
                called_from_main = True
                break
        
        # Skip sync if requested or if called from main.py
        if skip_sync or called_from_main:
            if skip_sync:
                print("Skipping automatic sync as requested.")
            elif called_from_main:
                print("Skipping automatic sync because called from main.py.")
            return True
            
        # Import Sync module here to prevent circular import
        try:
            import Sync
            print("Running synchronization...")
            Sync.sync_local_tasks_to_notion_and_todoist()
        except ImportError:
            print("Warning: Could not import Sync module")
        except Exception as e:
            print(f"Error during synchronization: {str(e)}")
            
        return True
    else:
        if source:
            print(f"No changes detected from {source}")
        return False

# Function to load tasks from the JSON file
def load_tasks_from_json():
    try:
        with open(TASKS_FILE, 'r', encoding='utf-8') as file:
            tasks = json.load(file)
    except FileNotFoundError:
        tasks = []
    
    # Ensure all tasks have the 'deleted' field
    for task in tasks:
        if 'deleted' not in task:
            task['deleted'] = False
    return tasks