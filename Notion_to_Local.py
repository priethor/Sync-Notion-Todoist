import json
import os
import sys
import subprocess
from datetime import datetime, timezone, timedelta
from helper import *

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
    print(f"Updated Notion task {notion_task_id} with properties: {properties_dict}")

# Main function
def sync_notion_to_json(debug_mode=False):
    print("\n=== Starting Notion to JSON Sync ===\n")
    
    # Log the steps if in debug mode
    if debug_mode:
        print("DEBUG: Getting tasks from Notion API...")
    
    notion_tasks = get_notion_tasks()

    if not notion_tasks:
        print("No tasks found in Notion")
        return

    if debug_mode:
        print(f"DEBUG: Retrieved {len(notion_tasks)} tasks from Notion")
        print("DEBUG: Loading local tasks from JSON...")
    
    tasks = load_tasks_from_json()
    
    if debug_mode:
        print(f"DEBUG: Loaded {len(tasks)} tasks from local JSON")
        print("DEBUG: Creating lookup dictionary for local tasks...")
    
    tasks_dict = {task['notion-id']: task for task in tasks}
    
    # Get Todoist tasks once at the beginning
    if debug_mode:
        print("DEBUG: Getting tasks from Todoist API...")
    
    existing_todoist_tasks = get_todoist_tasks()
    completed_todoist_tasks = get_completed_todoist_tasks()
    
    if debug_mode:
        print(f"DEBUG: Retrieved {len(existing_todoist_tasks)} active tasks and {len(completed_todoist_tasks)} completed tasks from Todoist")

    notion_task_ids = set()
    modified = False
    
    if debug_mode:
        print("\nDEBUG: Beginning task comparison between Notion and local JSON...")
        print("--------------------------------------------------------------")

    for task in notion_tasks:
        try:
            task_id = task['id']
            notion_task_ids.add(task_id)
            
            # Safely extract task name with error handling
            if 'Name' in task['properties'] and task['properties']['Name']['title'] and len(task['properties']['Name']['title']) > 0:
                task_name = task['properties']['Name']['title'][0]['text']['content']
            else:
                task_name = f"Unnamed Task ({task_id[-8:]})"
                print(f"Warning: Task {task_id} has no title, using placeholder name")
            
            # Safely extract completion status
            if 'Done' in task['properties'] and 'checkbox' in task['properties']['Done']:
                task_completed = task['properties']['Done']['checkbox']
            else:
                task_completed = False
                print(f"Warning: Task {task_id} has no completion status, defaulting to False")
            
            # Safely extract due date
            if 'Date' in task['properties'] and task['properties']['Date']['date']:
                task_due_date = task['properties']['Date']['date']['start']
            else:
                task_due_date = None
            
            # Safely extract labels
            if 'Type' in task['properties'] and 'multi_select' in task['properties']['Type']:
                task_labels = [label['name'] for label in task['properties']['Type']['multi_select']]
            else:
                task_labels = []
                print(f"Warning: Task {task_id} has no labels property, defaulting to empty list")
        
        except Exception as e:
            print(f"Error processing Notion task {task.get('id', 'unknown')}: {str(e)}")
            print(f"Task properties: {task.get('properties', {})}")
            continue

        if task_due_date:
            # Remove milliseconds from the due date and localize to GMT+8
            task_due_date = datetime.fromisoformat(task_due_date).replace(microsecond=0).astimezone(GMT_PLUS_8).isoformat()

        if task_id in tasks_dict:
            # Update existing task in JSON file
            task_data = tasks_dict[task_id]
            task_changed = False
            
            # Debug output with more details
            print(f"Checking task '{task_name}' (ID: {task_id}) from Notion:")
            print(f"  - Current state in local JSON:")
            print(f"    - Name: '{task_data['name']}'")
            print(f"    - Completed: {task_data['completed']}")
            print(f"    - Due date: {task_data['due_date']}")
            print(f"    - Labels: {task_data['labels']}")
            print(f"  - Current state in Notion:")
            print(f"    - Name: '{task_name}'")
            print(f"    - Completed: {task_completed}")
            print(f"    - Due date: {task_due_date}")
            print(f"    - Labels: {task_labels}")

            # Check for name changes
            if task_data['name'] != task_name:
                print(f"  - Name changed: '{task_data['name']}' -> '{task_name}'")
                task_data['name'] = task_name
                task_changed = True

            # Check for completion changes (ensure boolean comparison)
            local_completed = bool(task_data.get('completed', False))
            notion_completed = bool(task_completed)
            
            if local_completed != notion_completed:
                print(f"  - Completion changed: {local_completed} -> {notion_completed}")
                print(f"    - Original values: {task_data['completed']} (local) vs {task_completed} (Notion)")
                task_data['completed'] = notion_completed
                task_changed = True

            # Check for due date changes, handling None values properly
            due_date_changed = False
            if (task_data['due_date'] is None and task_due_date is not None) or \
               (task_data['due_date'] is not None and task_due_date is None) or \
               (task_data['due_date'] != task_due_date):
                print(f"  - Due date changed: {task_data['due_date']} -> {task_due_date}")
                task_data['due_date'] = task_due_date
                task_changed = True
                due_date_changed = True

            # Check for label changes using set comparison
            labels_changed = False
            if set(task_data.get('labels', [])) != set(task_labels):
                print(f"  - Labels changed: {task_data.get('labels', [])} -> {task_labels}")
                task_data['labels'] = task_labels
                task_changed = True
                labels_changed = True

            # Update sync flags if changes were detected
            if task_changed:
                print(f"  - Task changed in Notion, marking for sync to Todoist")
                
                # Simply mark for sync to Todoist
                task_data['sync_to_todoist'] = True
                print(f"  - Task marked for sync to Todoist")
                modified = True
            else:
                print(f"  - No changes detected")

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
                
            # This is a new task created in Notion, no special sync flag needed
            # as we're already creating it in Todoist with create_todoist_task

            task_data = {
                'notion-id': task_id,
                'todoist-id': todoist_task_id,
                'name': task_name,
                'completed': task_completed,
                'due_date': task_due_date,
                'labels': task_labels,
                'last_modified': datetime.now(timezone.utc).astimezone(GMT_PLUS_8).isoformat(),
                'last_modified_platform': 'notion',
                'sync_needed': True
            }

            tasks.append(task_data)
            modified = True

    # Mark tasks as deleted if they are not found in the Notion database
    for task in tasks:
        if task['notion-id'] not in notion_task_ids:
            task['deleted'] = True
            task['last_modified'] = datetime.now(timezone.utc).astimezone(GMT_PLUS_8).isoformat()
            task['last_modified_platform'] = 'notion'
            task['sync_needed'] = True
            modified = True

    # Only save if there were changes
    if modified:
        save_tasks_to_json(tasks, "Notion")

# Run the main function
if __name__ == "__main__":
    import sys
    debug_mode = "--debug" in sys.argv
    sync_notion_to_json(debug_mode)