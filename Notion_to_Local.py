import json
import os
import sys
import subprocess
from datetime import datetime, timezone, timedelta
from helper import *
from Sync import sync_local_tasks_to_notion_and_todoist

# Define the GMT+8 timezone
GMT_PLUS_8 = timezone(timedelta(hours=8))

# Function to create a task in Todoist
def create_todoist_task(task_name, existing_tasks, completed_tasks):
    for task in existing_tasks:
        if task['content'] == task_name:
            print(f"Task '{task_name}' already exists in Todoist, skipping...")
            return task['id'], False

    for task in completed_tasks:
        if task['content'] == task_name:
            print(f"Task '{task_name}' is already completed in Todoist, skipping...")
            return task['task_id'], True

    url = 'https://api.todoist.com/rest/v2/tasks'
    payload = {
        'content': task_name
    }
    response = requests.post(url, headers=todoist_headers, data=json.dumps(payload))
    response.raise_for_status()
    print(f"Task '{task_name}' created successfully in Todoist")
    return response.json()['id'], False

# Function to update Notion task properties
def update_notion_task_properties(notion_task_id, properties_dict):
    """
    Update multiple properties of a Notion task in a single API call.
    
    Args:
        notion_task_id: The ID of the Notion task to update
        properties_dict: Dictionary of properties to update (e.g. {'ID': 123, 'Done': True})
    """
    url = f'https://api.notion.com/v1/pages/{notion_task_id}'
    
    # Convert the simple properties dictionary to Notion's expected format
    notion_properties = {}
    for key, value in properties_dict.items():
        if key == 'ID':
            notion_properties['ID'] = {'number': int(value)}
        elif key == 'Done':
            notion_properties['Done'] = {'checkbox': value}
        # Add other property types as needed
    
    payload = {
        'properties': notion_properties
    }
    
    response = requests.patch(url, headers=notion_headers, data=json.dumps(payload))
    response.raise_for_status()

# Main function
def sync_notion_to_json():
    notion_tasks = get_notion_tasks()

    if not notion_tasks:
        return

    tasks = load_tasks_from_json()
    tasks_dict = {task['notion-id']: task for task in tasks}
    
    # Get Todoist tasks once at the beginning
    existing_todoist_tasks = get_todoist_tasks()
    completed_todoist_tasks = get_completed_todoist_tasks()

    notion_task_ids = set()
    modified = False

    for task in notion_tasks:
        task_id = task['id']
        notion_task_ids.add(task_id)
        task_name = task['properties']['Name']['title'][0]['text']['content']
        task_completed = task['properties']['Done']['checkbox']
        task_due_date = task['properties']['Date']['date']['start'] if task['properties']['Date']['date'] else None
        task_labels = [label['name'] for label in task['properties']['Type']['multi_select']]

        if task_due_date:
            # Remove milliseconds from the due date and localize to GMT+8
            task_due_date = datetime.fromisoformat(task_due_date).replace(microsecond=0).astimezone(GMT_PLUS_8).isoformat()

        if task_id in tasks_dict:
            # Update existing task in JSON file
            task_data = tasks_dict[task_id]
            task_changed = False

            if task_data['name'] != task_name:
                task_data['name'] = task_name
                task_changed = True

            if task_data['completed'] != task_completed:
                task_data['completed'] = task_completed
                task_changed = True

            if task_data['due_date'] != task_due_date:
                task_data['due_date'] = task_due_date
                task_changed = True

            if set(task_data['labels']) != set(task_labels):
                task_data['labels'] = task_labels
                task_changed = True

            if task_changed:
                task_data['last_modified'] = datetime.now(timezone.utc).astimezone(GMT_PLUS_8).isoformat()
                modified = True

        else:
            # Create a task in Todoist and get the task ID - using the pre-fetched lists
            todoist_task_id, is_completed = create_todoist_task(task_name, existing_todoist_tasks, completed_todoist_tasks)
            
            # Prepare updates for Notion
            updates = {}
            
            if todoist_task_id is None and is_completed:
                task_completed = True
                updates['Done'] = True
            elif todoist_task_id:
                updates['ID'] = todoist_task_id
                
            # If we have any updates, send them in a single API call
            if updates:
                update_notion_task_properties(task_id, updates)

            task_data = {
                'notion-id': task_id,
                'todoist-id': todoist_task_id,
                'name': task_name,
                'completed': task_completed,
                'due_date': task_due_date,
                'labels': task_labels,
                'last_modified': datetime.now(timezone.utc).astimezone(GMT_PLUS_8).isoformat()
            }

            tasks.append(task_data)
            modified = True

    # Mark tasks as deleted if they are not found in the Notion database
    for task in tasks:
        if task['notion-id'] not in notion_task_ids:
            task['deleted'] = True
            task['last_modified'] = datetime.now(timezone.utc).astimezone(GMT_PLUS_8).isoformat()
            modified = True

    # Only save if there were changes
    if modified:
        if save_tasks_to_json(tasks, "Notion"):
            # Only run sync if changes were saved
            sync_local_tasks_to_notion_and_todoist()

# Run the main function
if __name__ == "__main__":
    sync_notion_to_json()