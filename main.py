import time
import importlib
import sys
import traceback

def run_module(module_name):
    """Run a Python module by importing it and handling any errors."""
    try:
        # Import the module dynamically
        module = importlib.import_module(module_name)
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
    try:
        while True:
            # Run Notion_to_Local directly
            print("\nSyncing from Notion to local...")
            if not run_module("Notion_to_Local"):
                break
            time.sleep(4)
            
            # Run Todoist_to_Local directly
            print("\nSyncing from Todoist to local...")
            if not run_module("Todoist_to_Local"):
                break
            time.sleep(4)
            
    except KeyboardInterrupt:
        print("\nExiting gracefully...")

if __name__ == "__main__":
    main()