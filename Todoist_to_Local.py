import json
import os
import subprocess
import pytz
from datetime import datetime, timezone, timedelta
from helper import *

# Define the GMT+8 timezone
GMT_PLUS_8 = pytz.timezone('Etc/GMT-8')

# Function to create a task in Notion
def create_notion_task(task_name, task_description, task_due_date, todoist_task_id, notion_tasks_id_dict, task_labels):
    # Check if a task with the same ID already exists
    if int(todoist_task_id) in notion_tasks_id_dict:
        print(f"Task '{task_name}' already exists in Notion, skipping...")
        return

    url = 'https://api.notion.com/v1/pages'
    payload = {
        'parent': {'database_id': NOTION_DATABASE_ID},
        'properties': {
            'Name': {'title': [{'text': {'content': task_name}}]},
            'Done': {'checkbox': False},
            'ID': {'number': int(todoist_task_id)},
            'Type': {'multi_select': [{'name': label} for label in task_labels]}
        }
    }
    if task_due_date:
        if task_due_date.endswith('Z'):
            due_date_obj = datetime.strptime(task_due_date, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
        else:
            due_date_obj = datetime.fromisoformat(task_due_date)
        
        if due_date_obj.tzinfo is None:
            # Assume the local time is in a specific timezone, e.g., GMT+08:00
            local_tz = GMT_PLUS_8
            due_date_obj = local_tz.localize(due_date_obj)
        task_due_date = due_date_obj.astimezone(GMT_PLUS_8).strftime('%Y-%m-%dT%H:%M:%S%z')
        task_due_date = task_due_date[:-2] + ':' + task_due_date[-2:]
        payload['properties']['Date'] = {'date': {'start': task_due_date}}
    
    response = requests.post(url, headers=notion_headers, data=json.dumps(payload))
    response.raise_for_status()
    print(f"Task '{task_name}' created successfully in Notion")

# Main function
def sync_todoist_to_json(debug_mode=False):
    print("\n=== Starting Todoist to JSON Sync ===\n")
    
    # Log the steps if in debug mode
    if debug_mode:
        print("DEBUG: Loading local tasks from JSON...")
    
    tasks = load_tasks_from_json()
    
    if debug_mode:
        print(f"DEBUG: Loaded {len(tasks)} tasks from local JSON")
        print("DEBUG: Getting tasks from Todoist API...")
    
    todoist_tasks = get_todoist_tasks()
    completed_todoist_tasks = get_completed_todoist_tasks()
    
    if debug_mode:
        print(f"DEBUG: Retrieved {len(todoist_tasks)} active tasks and {len(completed_todoist_tasks)} completed tasks from Todoist")
        print("DEBUG: Getting tasks from Notion API...")
    
    notion_tasks = get_notion_tasks()
    
    if debug_mode:
        print(f"DEBUG: Retrieved {len(notion_tasks)} tasks from Notion")
        print("DEBUG: Creating lookup dictionaries...")

    # Create dictionaries for quick lookups
    tasks_dict = {int(task['todoist-id']): task for task in tasks}
    notion_tasks_id_dict = {task['properties']['ID']['number']: task for task in notion_tasks if 'ID' in task['properties'] and 'number' in task['properties']['ID']}
    todoist_tasks_dict = {int(task['id']): task for task in todoist_tasks}
    completed_todoist_tasks_dict = {int(task['task_id']): task for task in completed_todoist_tasks}

    if debug_mode:
        print(f"DEBUG: Created lookup dictionaries:")
        print(f"  - Local tasks with Todoist IDs: {len(tasks_dict)}")
        print(f"  - Notion tasks with Todoist IDs: {len(notion_tasks_id_dict)}")
        print(f"  - Active Todoist tasks: {len(todoist_tasks_dict)}")
        print(f"  - Completed Todoist tasks: {len(completed_todoist_tasks_dict)}")
        print("\nDEBUG: Beginning task comparison between Todoist and local JSON...")
        print("--------------------------------------------------------------")

    modified = False
    
    # Create new Notion tasks for Todoist tasks that don't exist in Notion
    for todoist_task in todoist_tasks:
        task_name = todoist_task['content']
        task_description = todoist_task.get('description', '')
        todoist_task_id = int(todoist_task['id'])
        todoist_task_labels = todoist_task['labels']
        if todoist_task_id not in notion_tasks_id_dict:
            due = todoist_task.get('due')
            task_due_date = due.get('datetime') if due and 'datetime' in due else due.get('date') if due else ''
            if task_due_date:
                if task_due_date.endswith('Z'):
                    due_date_obj = datetime.strptime(task_due_date, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
                else:
                    due_date_obj = datetime.fromisoformat(task_due_date)
                
                if due_date_obj.tzinfo is None:
                    # Assume the local time is in a specific timezone, e.g., GMT+08:00
                    local_tz = GMT_PLUS_8
                    due_date_obj = local_tz.localize(due_date_obj)
                task_due_date = due_date_obj.astimezone(GMT_PLUS_8).strftime('%Y-%m-%dT%H:%M:%S%z')
                # Adjust the format to include the colon in the timezone offset
                task_due_date = task_due_date[:-2] + ':' + task_due_date[-2:]
            create_notion_task(task_name, task_description, task_due_date, todoist_task_id, notion_tasks_id_dict, todoist_task_labels)
            # This is a new task created in Todoist, no need to set sync_needed flag
            # as it's already being created in Notion by the create_notion_task function
            modified = True

    # Update local JSON file based on Todoist tasks
    for task in tasks:
        todoist_task_id = int(task['todoist-id'])
        task_changed = False
        task_name = task.get('name', 'Unknown')
        
        print(f"Checking task '{task_name}' (Todoist ID: {todoist_task_id}) from Todoist:")
        print(f"  - Current state in local JSON:")
        print(f"    - Name: '{task_name}'")
        print(f"    - Completed: {task.get('completed', False)}")
        print(f"    - Due date: {task.get('due_date', None)}")
        print(f"    - Labels: {task.get('labels', [])}")

        if todoist_task_id in completed_todoist_tasks_dict:
            completed_task = completed_todoist_tasks_dict[todoist_task_id]
            print(f"  - Task found in completed Todoist tasks")
            
            # Ensure boolean comparison for completion status
            local_completed = bool(task.get('completed', False))
            if not local_completed:
                print(f"  - Completion changed: {local_completed} -> True")
                print(f"    - Original value: {task['completed']} (local)")
                task['completed'] = True
                task_changed = True
                
        elif todoist_task_id in todoist_tasks_dict:
            todoist_task = todoist_tasks_dict[todoist_task_id]
            print(f"  - Current state in Todoist:")
            print(f"    - Name: '{todoist_task['content']}'")
            print(f"    - Completed: {False}") # Active tasks are not completed
            print(f"    - Labels: {todoist_task['labels']}")
            
            # Handle completion status (ensure boolean comparison)
            local_completed = bool(task.get('completed', False))
            if local_completed:
                print(f"  - Completion changed: {local_completed} -> False")
                print(f"    - Original value: {task['completed']} (local)")
                task['completed'] = False
                task_changed = True
                
            # Handle name changes
            if task['name'] != todoist_task['content']:
                print(f"  - Name changed: '{task['name']}' -> '{todoist_task['content']}'")
                task['name'] = todoist_task['content']
                task_changed = True
            
            # Handle due date changes
            due_date = None
            if 'due' in todoist_task and todoist_task['due'] is not None:
                due = todoist_task['due']
                due_date_raw = due.get('datetime') if 'datetime' in due else due.get('date', '')
                print(f"    - Due date (raw): {due_date_raw}")
                
                if due_date_raw:
                    if due_date_raw.endswith('Z'):
                        due_date_obj = datetime.strptime(due_date_raw, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
                    else:
                        due_date_obj = datetime.fromisoformat(due_date_raw)
                    
                    if due_date_obj.tzinfo is None:
                        # Assume the local time is in a specific timezone, e.g., GMT+08:00
                        local_tz = GMT_PLUS_8
                        due_date_obj = local_tz.localize(due_date_obj)
                    due_date = due_date_obj.astimezone(GMT_PLUS_8).strftime('%Y-%m-%dT%H:%M:%S%z')
                    # Adjust the format to include the colon in the timezone offset
                    due_date = due_date[:-2] + ':' + due_date[-2:]
                    
            print(f"    - Due date (formatted): {due_date}")
            
            # Check for due date changes, handling None values properly
            due_date_changed = False
            if (task['due_date'] is None and due_date is not None) or \
               (task['due_date'] is not None and due_date is None) or \
               (task['due_date'] != due_date):
                print(f"  - Due date changed: {task['due_date']} -> {due_date}")
                task['due_date'] = due_date
                task_changed = True
                due_date_changed = True
            
            # Handle label changes using set comparison
            labels_changed = False
            if set(task.get('labels', [])) != set(todoist_task['labels']):
                print(f"  - Labels changed: {task.get('labels', [])} -> {todoist_task['labels']}")
                task['labels'] = todoist_task['labels']
                task_changed = True
                labels_changed = True

        # Mark task as deleted if it no longer exists in Todoist
        if todoist_task_id not in todoist_tasks_dict and todoist_task_id not in completed_todoist_tasks_dict:
            print(f"  - Task no longer exists in Todoist")
            if not task.get('deleted', False):
                print(f"  - Marking task as deleted")
                task['deleted'] = True
                task_changed = True

        # Update the sync flags if the task has changed
        if task_changed:
            print(f"  - Task changed in Todoist, marking for sync to Notion")
            
            # Simply mark for sync to Notion
            task['sync_to_notion'] = True
            print(f"  - Task marked for sync to Notion")
            modified = True
        else:
            print(f"  - No changes detected")

    # Only save if there were changes
    if modified:
        save_tasks_to_json(tasks, "Todoist")

# Run the main function
if __name__ == "__main__":
    import sys
    debug_mode = "--debug" in sys.argv
    sync_todoist_to_json(debug_mode)