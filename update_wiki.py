#!/usr/bin/env python3
"""
Update GitHub Wiki pages via git.

Clones the Wiki repository, updates pages, and pushes changes.
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

REPO_OWNER = "kiku-jw"
REPO_NAME = "PATAS"
WIKI_REPO_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}.wiki.git"

# Map local files to wiki page names
WIKI_PAGES = {
    "wiki_Performance.md": "Performance.md",
    "wiki_On-Premise-Deployment.md": "On-Premise-Deployment.md",
    "wiki_Incremental-Mining.md": "Incremental-Mining.md",
    "wiki_Roadmap.md": "Roadmap.md",
    "wiki_Horizontal-Scaling_EN.md": "Horizontal-Scaling.md",
    "wiki_Home_Updated.md": "Home.md",
    "wiki_FAQ_EN.md": "FAQ.md",
}

def main():
    """Main function."""
    base_dir = Path(__file__).parent
    wiki_dir = base_dir / "wiki_temp"
    
    # Clean up any existing temp directory
    if wiki_dir.exists():
        shutil.rmtree(wiki_dir)
    
    try:
        # Clone Wiki repository
        print("📥 Cloning Wiki repository...")
        subprocess.run(
            ["git", "clone", WIKI_REPO_URL, str(wiki_dir)],
            check=True,
            capture_output=True
        )
        
        # Check if files exist and copy them
        updated = 0
        missing = 0
        
        for local_file, wiki_file in WIKI_PAGES.items():
            local_path = base_dir / local_file
            wiki_path = wiki_dir / wiki_file
            
            if not local_path.exists():
                print(f"⚠️  Missing: {local_file}")
                missing += 1
                continue
            
            # Copy file
            shutil.copy2(local_path, wiki_path)
            print(f"✅ Copied: {local_file} → {wiki_file}")
            updated += 1
        
        if updated == 0:
            print("❌ No files to update")
            return
        
        # Commit and push
        print("\n📝 Committing changes...")
        subprocess.run(
            ["git", "add", "-A"],
            cwd=wiki_dir,
            check=True,
            capture_output=True
        )
        
        subprocess.run(
            ["git", "commit", "-m", "Update wiki pages: remove platform-specific references"],
            cwd=wiki_dir,
            check=True,
            capture_output=True
        )
        
        print("🚀 Pushing to GitHub...")
        subprocess.run(
            ["git", "push", "origin", "master"],
            cwd=wiki_dir,
            check=True,
            capture_output=True
        )
        
        print(f"\n{'='*50}")
        print(f"✅ Updated: {updated} pages")
        if missing > 0:
            print(f"⚠️  Missing: {missing} files")
        print(f"{'='*50}")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        if e.stderr:
            print(e.stderr.decode())
        sys.exit(1)
    finally:
        # Clean up
        if wiki_dir.exists():
            shutil.rmtree(wiki_dir)
            print("\n🧹 Cleaned up temporary files")

if __name__ == "__main__":
    main()
