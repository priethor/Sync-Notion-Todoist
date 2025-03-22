import json
import os
from datetime import datetime, timezone
from dateutil.parser import parse
import requests
from helper import *

# Function to delete a task in Notion
def delete_notion_task(task_id):
    url = f'https://api.notion.com/v1/pages/{task_id}'
    try:
        response = requests.patch(url, headers=notion_headers, data=json.dumps({"archived": True}))
        response.raise_for_status()
        print(f"Task with ID {task_id} deleted successfully from Notion")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            print(f"Task with ID {task_id} not found in Notion, skipping deletion.")
        else:
            raise

# Function to delete a task in Todoist
def delete_todoist_task(task_id):
    url = f'https://api.todoist.com/rest/v2/tasks/{task_id}'
    try:
        response = requests.delete(url, headers=todoist_headers)
        response.raise_for_status()
        print(f"Task with ID {task_id} deleted successfully from Todoist")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Task with ID {task_id} not found in Todoist, skipping deletion.")
        else:
            raise

# Function to create or update a task in Notion
def sync_notion_task(task):
    # Skip the last_synced_time check since we're now using explicit sync flags
    print(f"  - Syncing task '{task['name']}' to Notion...")

    url = f'https://api.notion.com/v1/pages/{task["notion-id"]}'
    payload = {
        'properties': {
            'Name': {'title': [{'text': {'content': task['name']}}]},
            'Done': {'checkbox': task['completed']},
            'Type': {'multi_select': [{'name': label} for label in task['labels']]}
        }
    }
    if task['due_date']:
        due_date_obj = parse(task['due_date'])
        if due_date_obj.time() != datetime.min.time():
            # If time is present, include it
            payload['properties']['Date'] = {'date': {'start': due_date_obj.isoformat()}}
        else:
            # If only date is present, format without time
            payload['properties']['Date'] = {'date': {'start': due_date_obj.strftime('%Y-%m-%d')}}
    else:
        payload['properties']['Date'] = {'date': None}

    response = requests.patch(url, headers=notion_headers, data=json.dumps(payload))
    response.raise_for_status()
    print(f"Task '{task['name']}' synced successfully to Notion")

# Function to create or update a task in Todoist
def sync_todoist_task(task):
    # Skip the last_synced_time check since we're now using explicit sync flags
    print(f"  - Syncing task '{task['name']}' to Todoist...")

    url = f'https://api.todoist.com/rest/v2/tasks/{task["todoist-id"]}' if task['todoist-id'] else 'https://api.todoist.com/rest/v2/tasks'
    payload = {
        'content': task['name'],
        'labels': task['labels']
    }

    if task['due_date']:
        due_date_obj = parse(task['due_date'])
        if due_date_obj.time() != datetime.min.time():
            # If time is present, include it
            payload['due_string'] = due_date_obj.isoformat()
        else:
            # If only date is present, remove due_string
            payload['due_date'] = due_date_obj.strftime('%Y-%m-%d')
    else:
        payload['due_string'] = "no due date"

    try:
        if task['todoist-id']:
            # Update existing task
            response = requests.post(url, headers=todoist_headers, data=json.dumps(payload))
        else:
            # Create new task
            response = requests.post('https://api.todoist.com/rest/v2/tasks', headers=todoist_headers, data=json.dumps(payload))
        response.raise_for_status()
        print(f"Task '{task['name']}' synced successfully to Todoist")

        # Update the completed status separately
        if task['completed']:
            complete_todoist_task(response.json()['id'])
        else:
            reopen_todoist_task(response.json()['id'])
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Task with ID {task['todoist-id']} not found in Todoist, skipping sync.")
        else:
            raise
        
# Function to mark a task as completed in Todoist
def complete_todoist_task(task_id):
    url = f'https://api.todoist.com/rest/v2/tasks/{task_id}/close'
    try:
        response = requests.post(url, headers=todoist_headers)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Task with ID {task_id} not found in Todoist, skipping completion.")
        else:
            raise

# Function to reopen a task in Todoist
def reopen_todoist_task(task_id):
    url = f'https://api.todoist.com/rest/v2/tasks/{task_id}/reopen'
    try:
        response = requests.post(url, headers=todoist_headers)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Task with ID {task_id} not found in Todoist, skipping reopening.")
        else:
            raise

# Main function to sync tasks from local JSON file to Notion and Todoist
def sync_local_tasks_to_notion_and_todoist(debug_mode=False):
    print("\n=== Starting Local to Notion and Todoist Sync ===\n")
    
    if debug_mode:
        print("DEBUG: Loading tasks from local JSON...")
    
    tasks = load_tasks_from_json()
    tasks_to_keep = []
    changes_made = False

    print(f"Processing {len(tasks)} tasks for syncing")
    
    # Count tasks that need syncing for better debugging
    tasks_to_notion = [t for t in tasks if t.get('sync_to_notion', False)]
    tasks_to_todoist = [t for t in tasks if t.get('sync_to_todoist', False)]
    print(f"Found {len(tasks_to_notion)} tasks to sync to Notion and {len(tasks_to_todoist)} tasks to sync to Todoist")
    
    if debug_mode and (tasks_to_notion or tasks_to_todoist):
        print("\nDEBUG: Tasks marked for sync:")
        
        if tasks_to_notion:
            print("\nTasks to sync to Notion:")
            for i, task in enumerate(tasks_to_notion):
                print(f"  {i+1}. '{task.get('name', 'Unknown')}'")
                print(f"     - Notion ID: {task.get('notion-id', 'None')}")
                print(f"     - Todoist ID: {task.get('todoist-id', 'None')}")
                print(f"     - Completed: {task.get('completed', False)}")
                
        if tasks_to_todoist:
            print("\nTasks to sync to Todoist:")
            for i, task in enumerate(tasks_to_todoist):
                print(f"  {i+1}. '{task.get('name', 'Unknown')}'")
                print(f"     - Notion ID: {task.get('notion-id', 'None')}")
                print(f"     - Todoist ID: {task.get('todoist-id', 'None')}")
                print(f"     - Completed: {task.get('completed', False)}")
        
        print("\nDEBUG: Beginning task processing...")
        print("--------------------------------------------------------------")
    
    # Log all tasks that need syncing
    if tasks_to_notion:
        print("\nTasks to sync to Notion:")
        for i, task in enumerate(tasks_to_notion):
            print(f"  {i+1}. '{task.get('name', 'Unknown')}'")
            print(f"     - Notion ID: {task.get('notion-id', 'None')}")
            print(f"     - Todoist ID: {task.get('todoist-id', 'None')}")
    
    if tasks_to_todoist:
        print("\nTasks to sync to Todoist:")
        for i, task in enumerate(tasks_to_todoist):
            print(f"  {i+1}. '{task.get('name', 'Unknown')}'")
            print(f"     - Notion ID: {task.get('notion-id', 'None')}")
            print(f"     - Todoist ID: {task.get('todoist-id', 'None')}")
    
    for task in tasks:
        if task.get('deleted', False):
            # Delete task from Notion and Todoist if marked as deleted
            print(f"\nDeleting task: '{task.get('name', 'Unknown')}'")
            if 'notion-id' in task:
                delete_notion_task(task['notion-id'])
                changes_made = True
            if 'todoist-id' in task:
                delete_todoist_task(task['todoist-id'])
                changes_made = True
        else:
            # Detailed task sync status logging
            print(f"\nChecking task '{task.get('name', 'Unknown')}' (Notion ID: {task.get('notion-id', 'None')}):")
            print(f"  - sync_needed: {task.get('sync_needed', False)}")
            print(f"  - last_modified_platform: {task.get('last_modified_platform', 'None')}")
            print(f"  - last_modified: {task.get('last_modified', 'None')}")
            
            # Check for specific sync direction flags
            if task.get('sync_to_notion', False) or task.get('sync_to_todoist', False):
                print(f"  - Task '{task.get('name', 'Unknown')}' needs syncing:")
                print(f"    - Sync to Notion: {task.get('sync_to_notion', False)}")
                print(f"    - Sync to Todoist: {task.get('sync_to_todoist', False)}")
                
                # Sync to Notion if needed
                if task.get('sync_to_notion', False):
                    print(f"  - Syncing to Notion")
                    sync_notion_task(task)
                    # Clear the sync flag after syncing
                    task.pop('sync_to_notion', None)
                    changes_made = True
                
                # Sync to Todoist if needed
                if task.get('sync_to_todoist', False):
                    print(f"  - Syncing to Todoist")
                    sync_todoist_task(task)
                    # Clear the sync flag after syncing
                    task.pop('sync_to_todoist', None)
                    changes_made = True
                
                # Also clear the old flag if it exists
                if task.get('sync_needed', False):
                    task.pop('sync_needed', None)
            else:
                print(f"  - No sync needed")
            
            tasks_to_keep.append(task)

    # Always save after sync if changes were made
    if changes_made:
        # Save the updated list of tasks to the local JSON file
        save_tasks_to_json(tasks_to_keep)
        
        # Update the last synced time 
        save_last_synced_time()
        print("Sync completed with changes")
    else:
        print("Sync completed - no changes needed")
        
    # Return the updated task list for testing purposes
    return tasks_to_keep

# Run the sync function when imported as a module
if __name__ == "__main__":
    import sys
    debug_mode = "--debug" in sys.argv
    sync_local_tasks_to_notion_and_todoist(debug_mode)