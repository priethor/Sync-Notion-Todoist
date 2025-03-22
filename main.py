import time
import importlib
import sys
import traceback

def run_module(module_name, debug_mode=False):
    """Run a Python module by importing it and handling any errors."""
    try:
        # Import the module dynamically
        module = importlib.import_module(module_name)
        
        # Explicitly run the appropriate function based on the module
        if module_name == "Sync":
            print(f"Running {module_name}.sync_local_tasks_to_notion_and_todoist()...")
            module.sync_local_tasks_to_notion_and_todoist(debug_mode)
        elif module_name == "Notion_to_Local":
            print(f"Running {module_name}.sync_notion_to_json()...")
            # Pass the skip_sync=True parameter to prevent automatic sync
            if hasattr(module, 'sync_notion_to_json'):
                module.sync_notion_to_json(debug_mode)
            else:
                print(f"Error: {module_name} does not have sync_notion_to_json() function")
                return False
        elif module_name == "Todoist_to_Local":
            print(f"Running {module_name}.sync_todoist_to_json()...")
            # Pass the skip_sync=True parameter to prevent automatic sync
            if hasattr(module, 'sync_todoist_to_json'):
                module.sync_todoist_to_json(debug_mode)
            else:
                print(f"Error: {module_name} does not have sync_todoist_to_json() function")
                return False
        else:
            print(f"Warning: No specific function call for {module_name}")
            
        print(f"Successfully executed {module_name}")
        return True
    except Exception as e:
        print(f"Error executing {module_name}: {str(e)}")
        traceback.print_exc()
        
        if isinstance(e, SystemExit):
            if e.code == 1:
                print("Error: Invalid Notion API token. Please check your NOTION_API_TOKEN environment variable.")
            elif e.code == 2:
                print("Error: Invalid Notion Database ID. Please check your NOTION_DATABASE_ID environment variable.")
            elif e.code == 3:
                print("Error: Invalid Todoist API token. Please check your TODOIST_API_TOKEN environment variable.")
            
        return False

def main():
    # Check for debug mode
    debug_mode = "--debug" in sys.argv
    
    if debug_mode:
        print("Running in DEBUG mode - detailed logging enabled")
    
    # Don't use importlib.reload to ensure module imports are fresh
    sys.modules.pop("Notion_to_Local", None)
    sys.modules.pop("Todoist_to_Local", None)
    sys.modules.pop("Sync", None)
    
    try:
        while True:
            # Improved sync flow: check A → update B → check B → update A
            
            # Step 1: Get changes from Notion and mark for sync
            print("\n===== STEP 1: Checking for changes in Notion =====")
            if not run_module("Notion_to_Local", debug_mode):
                print("Error checking Notion changes - stopping")
                break
            
            # Step 2: Sync Notion changes to Todoist
            print("\n===== STEP 2: Syncing Notion changes to Todoist =====")
            if not run_module("Sync", debug_mode):
                print("Error syncing to Todoist - stopping")
                break
                
            # Step 3: Get changes from Todoist
            print("\n===== STEP 3: Checking for changes in Todoist =====")
            if not run_module("Todoist_to_Local", debug_mode):
                print("Error checking Todoist changes - stopping")
                break
                
            # Step 4: Sync Todoist changes to Notion
            print("\n===== STEP 4: Syncing Todoist changes to Notion =====")
            if not run_module("Sync", debug_mode):
                print("Error syncing to Notion - stopping")
                break
            
            print(f"\nSync cycle completed. Waiting for next cycle...")
            time.sleep(4)
            
    except KeyboardInterrupt:
        print("\nExiting gracefully...")

if __name__ == "__main__":
    main()