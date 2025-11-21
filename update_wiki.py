#!/usr/bin/env python3
"""
Update GitHub Wiki pages via API.

Requires GITHUB_TOKEN environment variable with repo scope.
"""
import os
import sys
import json
import requests
from pathlib import Path

REPO_OWNER = "kiku-jw"
REPO_NAME = "PATAS"
WIKI_BASE_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/wiki"

# Map local files to wiki page names
WIKI_PAGES = {
    "wiki_Performance.md": "Performance",
    "wiki_On-Premise-Deployment.md": "On-Premise-Deployment",
    "wiki_Incremental-Mining.md": "Incremental-Mining",
    "wiki_Roadmap.md": "Roadmap",
    "wiki_Horizontal-Scaling_EN.md": "Horizontal-Scaling",
    "wiki_Home_Updated.md": "Home",
    "wiki_FAQ_EN.md": "FAQ",
}

def get_auth_headers():
    """Get authentication headers."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable not set")
        print("Set it with: export GITHUB_TOKEN=your_token")
        sys.exit(1)
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

def get_page_sha(page_name: str, headers: dict) -> str:
    """Get current page SHA."""
    url = f"{WIKI_BASE_URL}/pages/{page_name}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()["sha"]
    elif response.status_code == 404:
        # Page doesn't exist yet, will be created
        return None
    else:
        print(f"Error getting page {page_name}: {response.status_code}")
        print(response.text)
        return None

def update_wiki_page(page_name: str, content: str, headers: dict, sha: str = None):
    """Update or create wiki page."""
    url = f"{WIKI_BASE_URL}/pages/{page_name}"
    data = {
        "title": page_name,
        "body": content,
    }
    if sha:
        data["sha"] = sha
    
    response = requests.put(url, headers=headers, json=data)
    if response.status_code in [200, 201]:
        print(f"✅ Updated: {page_name}")
        return True
    else:
        print(f"❌ Failed to update {page_name}: {response.status_code}")
        print(response.text)
        return False

def main():
    """Main function."""
    headers = get_auth_headers()
    
    # Check if files exist
    base_dir = Path(__file__).parent
    missing_files = []
    for local_file, page_name in WIKI_PAGES.items():
        file_path = base_dir / local_file
        if not file_path.exists():
            missing_files.append(local_file)
    
    if missing_files:
        print(f"Warning: Missing files: {', '.join(missing_files)}")
        print("Skipping missing files...")
    
    # Update pages
    updated = 0
    failed = 0
    
    for local_file, page_name in WIKI_PAGES.items():
        file_path = base_dir / local_file
        if not file_path.exists():
            continue
        
        print(f"\n📄 Processing: {local_file} → {page_name}")
        
        # Read content
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"❌ Error reading {local_file}: {e}")
            failed += 1
            continue
        
        # Get current SHA
        sha = get_page_sha(page_name, headers)
        
        # Update page
        if update_wiki_page(page_name, content, headers, sha):
            updated += 1
        else:
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"✅ Updated: {updated}")
    print(f"❌ Failed: {failed}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()

